"""REST endpoints."""
from fastapi import APIRouter, HTTPException

from api.schemas import NewGameRequest, NewGameResponse, GameStateResponse, ResignRequest
from api.session import session_manager, EVALUATOR_REGISTRY
from engine.constants import Color

router = APIRouter(prefix='/api')


@router.post('/new_game', response_model=NewGameResponse)
def new_game(req: NewGameRequest):
    """Create a new game session and return its ID."""
    if req.white_evaluator and req.white_evaluator not in EVALUATOR_REGISTRY:
        raise HTTPException(400, f'Unknown evaluator: {req.white_evaluator!r}')
    if req.black_evaluator and req.black_evaluator not in EVALUATOR_REGISTRY:
        raise HTTPException(400, f'Unknown evaluator: {req.black_evaluator!r}')

    white_ev = req.white_evaluator
    black_ev = req.black_evaluator

    if req.mode == 'hvh':
        white_ev = None
        black_ev = None
    elif req.mode == 'hvc':
        white_ev = None
        black_ev = black_ev or 'positional'
    elif req.mode == 'cvc':
        white_ev = white_ev or 'positional'
        black_ev = black_ev or 'material'

    session = session_manager.create_session(
        req.mode,
        white_ev,
        black_ev,
        req.white_depth,
        req.black_depth,
    )
    return NewGameResponse(session_id=session.session_id, mode=req.mode)


@router.get('/state/{session_id}', response_model=GameStateResponse)
def get_state(session_id: str):
    """Return the full serialised game state."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, 'Session not found')
    return GameStateResponse(session_id=session_id, state=session.game.to_dict())


@router.post('/resign/{session_id}')
def resign(session_id: str, req: ResignRequest):
    """Resign the game for one side."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, 'Session not found')
    color = Color.WHITE if req.color == 'white' else Color.BLACK
    session.game.resign(color)
    return {'result': session.game.result}


@router.get('/evaluators')
def list_evaluators():
    """Return the names of all registered evaluators."""
    return {'evaluators': sorted(EVALUATOR_REGISTRY.keys())}
