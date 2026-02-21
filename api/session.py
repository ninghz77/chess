"""Session management and the evaluator registry."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from engine.constants import Color, PieceType
from engine.game import GameState
from engine.move import Move
from evaluators.material import SimpleMaterialEvaluator
from evaluators.positional import PositionalEvaluator
from search.minimax import MinimaxSearcher

# ---------------------------------------------------------------------------
# Evaluator registry
# ---------------------------------------------------------------------------
# To add a new evaluator:
#   1. Subclass EvaluatorBase and implement evaluate().
#   2. Import it here and add an entry below.
#   3. Done — it appears in GET /api/evaluators and the frontend dropdown.

EVALUATOR_REGISTRY: dict[str, type] = {
    'material':   SimpleMaterialEvaluator,
    'positional': PositionalEvaluator,
}

# Shared thread-pool for blocking AI computation
_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------

class GameSession:
    def __init__(
        self,
        session_id: str,
        mode: str,
        white_evaluator_name: Optional[str],
        black_evaluator_name: Optional[str],
        white_depth: int = 3,
        black_depth: int = 3,
    ) -> None:
        self.session_id = session_id
        self.mode = mode
        self.game = GameState()
        self.websocket = None  # set by the WS route

        self.white_searcher: Optional[MinimaxSearcher] = None
        self.black_searcher: Optional[MinimaxSearcher] = None

        if white_evaluator_name and white_evaluator_name in EVALUATOR_REGISTRY:
            ev = EVALUATOR_REGISTRY[white_evaluator_name]()
            self.white_searcher = MinimaxSearcher(ev, white_depth)

        if black_evaluator_name and black_evaluator_name in EVALUATOR_REGISTRY:
            ev = EVALUATOR_REGISTRY[black_evaluator_name]()
            self.black_searcher = MinimaxSearcher(ev, black_depth)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def current_searcher(self) -> Optional[MinimaxSearcher]:
        """Return the searcher for the side that is currently to move."""
        return self.white_searcher if self.game.board.turn == Color.WHITE else self.black_searcher

    def is_human_turn(self) -> bool:
        """True when no AI is configured for the side to move."""
        return self.current_searcher() is None

    def make_move(
        self,
        from_sq: int,
        to_sq: int,
        promotion: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Try to play a move by square indices.  Returns (ok, error_message).
        The *is_castle* / *is_en_passant* flags are resolved by matching
        against the legal-move list.
        """
        promo_pt: Optional[PieceType] = None
        if promotion:
            promo_map = {
                'QUEEN':  PieceType.QUEEN,
                'ROOK':   PieceType.ROOK,
                'BISHOP': PieceType.BISHOP,
                'KNIGHT': PieceType.KNIGHT,
            }
            promo_pt = promo_map.get(promotion.upper())

        matched: Optional[Move] = None
        for lm in self.game.legal_moves:
            if lm.from_sq == from_sq and lm.to_sq == to_sq and lm.promotion == promo_pt:
                matched = lm
                break

        if matched is None:
            return False, 'Illegal move'

        ok = self.game.make_move(matched)
        return ok, ''

    def compute_ai_move(self) -> Optional[Move]:
        """Compute the best move for the AI side (blocking — run in executor)."""
        searcher = self.current_searcher()
        if searcher is None:
            return None
        return searcher.best_move(self.game)


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}

    def create_session(
        self,
        mode: str,
        white_evaluator: Optional[str] = None,
        black_evaluator: Optional[str] = None,
        white_depth: int = 3,
        black_depth: int = 3,
    ) -> GameSession:
        session_id = str(uuid.uuid4())
        session = GameSession(
            session_id, mode,
            white_evaluator, black_evaluator,
            white_depth, black_depth,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[GameSession]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# Singleton used by both REST and WS routes
session_manager = SessionManager()
