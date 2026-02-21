"""WebSocket endpoint — full message protocol."""
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.session import session_manager
from engine.constants import Color
from engine.game import GameResult

log = logging.getLogger(__name__)
router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.websocket('/ws/{session_id}')
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    session = session_manager.get(session_id)
    if session is None:
        await websocket.close(code=4004, reason='Session not found')
        return

    await websocket.accept()
    session.websocket = websocket
    log.info('WS connected: %s', session_id)

    # Send initial board state
    await _send_state(websocket, session)

    # For CvC start the AI game loop in the background
    cvc_task = None
    if session.mode == 'cvc':
        cvc_task = asyncio.create_task(_cvc_loop(session, websocket))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({'type': 'error', 'message': 'Invalid JSON'})
                continue
            await _handle(msg, session, websocket)
    except WebSocketDisconnect:
        log.info('WS disconnected: %s', session_id)
    finally:
        session.websocket = None
        if cvc_task:
            cvc_task.cancel()


# ---------------------------------------------------------------------------
# Message dispatcher
# ---------------------------------------------------------------------------

async def _handle(msg: dict, session, websocket: WebSocket) -> None:
    msg_type = msg.get('type')

    if msg_type == 'ping':
        await websocket.send_json({'type': 'pong'})
        return

    if msg_type == 'resign':
        color_str = msg.get('color', 'white')
        color = Color.WHITE if color_str == 'white' else Color.BLACK
        session.game.resign(color)
        await _send_state(websocket, session)
        await _maybe_game_over(websocket, session)
        return

    if msg_type == 'move':
        if session.game.result != GameResult.ONGOING:
            await websocket.send_json({'type': 'error', 'message': 'Game is over'})
            return

        if not session.is_human_turn():
            await websocket.send_json({'type': 'error', 'message': 'Not a human turn'})
            return

        from_sq = msg.get('from_sq')
        to_sq = msg.get('to_sq')
        promotion = msg.get('promotion')

        if from_sq is None or to_sq is None:
            await websocket.send_json({'type': 'error', 'message': 'Missing from_sq/to_sq'})
            return

        ok, err = session.make_move(int(from_sq), int(to_sq), promotion)
        if not ok:
            await websocket.send_json({'type': 'error', 'message': err})
            return

        await _send_state(websocket, session)

        if session.game.result != GameResult.ONGOING:
            await _maybe_game_over(websocket, session)
            return

        # Trigger AI response for HvC
        if session.mode == 'hvc' and not session.is_human_turn():
            await _run_ai_move(session, websocket)
        return

    await websocket.send_json({'type': 'error', 'message': f'Unknown message type: {msg_type!r}'})


# ---------------------------------------------------------------------------
# AI move helpers
# ---------------------------------------------------------------------------

async def _run_ai_move(session, websocket: WebSocket) -> None:
    """Compute one AI move in the executor and broadcast it."""
    await websocket.send_json({'type': 'ai_thinking'})
    loop = asyncio.get_event_loop()
    try:
        move = await loop.run_in_executor(_executor, session.compute_ai_move)
    except Exception as exc:
        log.exception('AI error: %s', exc)
        await websocket.send_json({'type': 'error', 'message': 'AI computation failed'})
        return

    if move is None:
        return

    session.game.make_move(move)
    await websocket.send_json({
        'type': 'ai_move',
        'from_sq': move.from_sq,
        'to_sq': move.to_sq,
        'promotion': move.promotion.name if move.promotion else None,
        'uci': move.uci(),
    })
    await _send_state(websocket, session)
    await _maybe_game_over(websocket, session)


async def _cvc_loop(session, websocket: WebSocket) -> None:
    """Drive a Computer-vs-Computer game; server pushes each move."""
    await asyncio.sleep(0.3)
    while session.game.result == GameResult.ONGOING:
        if websocket.client_state.value != 1:  # CONNECTED
            break
        await _run_ai_move(session, websocket)
        await asyncio.sleep(0.5)


# ---------------------------------------------------------------------------
# Utility senders
# ---------------------------------------------------------------------------

async def _send_state(websocket: WebSocket, session) -> None:
    await websocket.send_json({
        'type': 'state',
        'session_id': session.session_id,
        'state': session.game.to_dict(),
    })


async def _maybe_game_over(websocket: WebSocket, session) -> None:
    if session.game.result != GameResult.ONGOING:
        await websocket.send_json({
            'type': 'game_over',
            'result': session.game.result,
            'reason': session.game.draw_reason,
        })
