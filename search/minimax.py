"""
Minimax search with alpha-beta pruning.

MinimaxSearcher is evaluator-agnostic: it accepts any EvaluatorBase
instance at construction time and never imports a concrete evaluator.
"""
from typing import Optional, TYPE_CHECKING

from engine.constants import Color
from engine.move import Move
from engine.move_generator import generate_legal_moves, is_in_check

if TYPE_CHECKING:
    from evaluators.base import EvaluatorBase
    from engine.game import GameState

_INF = 100_000_000


class MinimaxSearcher:
    """
    Fixed-depth minimax with alpha-beta pruning and simple move ordering.

    Parameters
    ----------
    evaluator:
        Any EvaluatorBase subclass.  Positive scores favour White.
    depth:
        Half-moves (plies) to search.  Depth 1 = look one move ahead.
    """

    def __init__(self, evaluator: 'EvaluatorBase', depth: int = 3) -> None:
        self.evaluator = evaluator
        self.depth = depth
        self.nodes_searched: int = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def best_move(self, game_state: 'GameState') -> Optional[Move]:
        """Return the best move for the side to move, or None if no moves."""
        self.nodes_searched = 0
        color = game_state.board.turn
        maximizing = color == Color.WHITE

        legal_moves = generate_legal_moves(game_state.board)
        if not legal_moves:
            return None

        _order_moves(game_state, legal_moves)

        best: Optional[Move] = None
        best_score = -_INF if maximizing else _INF
        alpha, beta = -_INF, _INF

        for move in legal_moves:
            game_state.board.make_move(move)
            score = self._search(game_state, self.depth - 1, alpha, beta, not maximizing)
            game_state.board.undo_move()

            if maximizing:
                if score > best_score:
                    best_score = score
                    best = move
                alpha = max(alpha, score)
            else:
                if score < best_score:
                    best_score = score
                    best = move
                beta = min(beta, score)

        return best

    # ------------------------------------------------------------------
    # Recursive search
    # ------------------------------------------------------------------

    def _search(
        self,
        game_state: 'GameState',
        depth: int,
        alpha: int,
        beta: int,
        maximizing: bool,
    ) -> int:
        self.nodes_searched += 1

        legal_moves = generate_legal_moves(game_state.board)
        current = game_state.board.turn

        if not legal_moves:
            if is_in_check(game_state.board, current):
                # Checkmate: the caller (opponent) wins
                return _INF if maximizing else -_INF
            return 0  # Stalemate

        if depth == 0:
            return self.evaluator.evaluate(game_state)

        _order_moves(game_state, legal_moves)

        if maximizing:
            value = -_INF
            for move in legal_moves:
                game_state.board.make_move(move)
                value = max(value, self._search(game_state, depth - 1, alpha, beta, False))
                game_state.board.undo_move()
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value
        else:
            value = _INF
            for move in legal_moves:
                game_state.board.make_move(move)
                value = min(value, self._search(game_state, depth - 1, alpha, beta, True))
                game_state.board.undo_move()
                beta = min(beta, value)
                if beta <= alpha:
                    break
            return value


# ---------------------------------------------------------------------------
# Move ordering helper
# ---------------------------------------------------------------------------

from engine.constants import PieceType as _PT

_PIECE_SORT_VALUE: dict[_PT, int] = {
    _PT.PAWN:   1,
    _PT.KNIGHT: 3,
    _PT.BISHOP: 3,
    _PT.ROOK:   5,
    _PT.QUEEN:  9,
    _PT.KING:   100,
}


def _order_moves(game_state: 'GameState', moves: list[Move]) -> None:
    """
    In-place sort: captures first (MVV-LVA approximation), then quiet moves.
    Improves alpha-beta cut-off rate significantly.
    """

    def _score(move: Move) -> int:
        target = game_state.board.squares[move.to_sq]
        if target is not None:
            victim_value = _PIECE_SORT_VALUE.get(target[1], 0)
            attacker = game_state.board.squares[move.from_sq]
            attacker_value = _PIECE_SORT_VALUE.get(attacker[1], 0) if attacker else 0
            return -(victim_value * 10 - attacker_value)
        return 0

    moves.sort(key=_score)
