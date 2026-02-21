# Chess Web App — Developer Notes

## Project Overview

A chess game with a from-scratch Python engine, pluggable evaluator/scorer system, three game modes (HvH, HvC, CvC), FastAPI + WebSocket backend, and Vanilla JS frontend.

## Key Commands

```bash
# Install
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Run dev server
uvicorn api.main:app --reload --port 8080

# Tests
python -m pytest tests/ -v                          # all tests
python -m pytest tests/test_move_generator.py -v    # single file

# Docker
docker build -t chess-web .
docker run -p 8080:8080 chess-web

# Deploy to Cloud Run
gcloud run deploy chess-web --source . \
  --region us-central1 --allow-unauthenticated \
  --max-instances 1 --memory 512Mi --timeout 3600
```

> `--max-instances 1` required while sessions are stored in-process memory.

## Architecture

### Engine (`engine/`)
Pure Python; zero web dependencies.

- `constants.py` — Color/PieceType enums, square helpers, centipawn values
- `move.py` — Move dataclass, UCI helpers
- `board.py` — 8x8 board state, make_move/undo_move, castling rights, ep square
- `move_generator.py` — Legal move generation (castling, en passant, promotion, check filter)
- `game.py` — GameState: history, 50-move, threefold-rep, result detection
- `zobrist.py` — Zobrist hashing for threefold repetition detection

### Pluggable Evaluators (`evaluators/`)

`evaluators/base.py` defines the single extension point:

```python
class EvaluatorBase(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def evaluate(self, game_state: GameState) -> int:
        """Centipawns, White-positive. Must not call make_move/undo_move."""
```

**To add a custom evaluator:**
1. Subclass `EvaluatorBase`, implement `evaluate()`.
2. Add one entry to `EVALUATOR_REGISTRY` in `api/session.py`.
3. It becomes selectable via the API and the frontend difficulty dropdown.

Built-in evaluators:
- `material` — SimpleMaterialEvaluator (centipawn material count)
- `positional` — PositionalEvaluator (material + piece-square tables)

### Search (`search/`)

`MinimaxSearcher(evaluator, depth)` — alpha-beta pruning. Accepts any `EvaluatorBase` instance; no concrete evaluator is imported by `search/minimax.py`.

### API (`api/`)

FastAPI backend with REST and WebSocket routes.

**REST endpoints:**
- `POST /api/new_game` — Create a game session
- `GET /api/state/{id}` — Get current game state
- `POST /api/resign/{id}` — Resign
- `GET /api/evaluators` — List available evaluators

**WebSocket:** `ws://{host}/ws/{session_id}`

Client → Server messages: `move`, `resign`, `ping`
Server → Client messages: `state`, `ai_thinking`, `ai_move`, `game_over`, `error`, `pong`

### Game Modes

| mode | white_searcher | black_searcher | notes |
|------|---------------|---------------|-------|
| `hvh` | None | None | REST-only; no AI computation |
| `hvc` | None | AI | AI runs in ThreadPoolExecutor after each human move |
| `cvc` | AI | AI | Server drives async loop; client receives stream of `ai_move` messages |

## Notes

- Sessions are stored in-process memory — single instance only.
- Board square indexing: row 0 = rank 8 (black's back rank), square = row*8+col.
- Evaluator scores are centipawns from White's perspective (positive = White advantage).
