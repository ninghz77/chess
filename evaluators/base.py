"""Abstract base class for all chess position evaluators."""
import abc
from typing import TYPE_CHECKING

from engine.constants import PieceType

if TYPE_CHECKING:
    from engine.game import GameState

STANDARD_VALUES: dict[PieceType, int] = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20000,
}


class EvaluatorBase(abc.ABC):
    """
    Extension point for position evaluation.

    Subclass this, implement ``evaluate()``, register in
    ``api/session.py::EVALUATOR_REGISTRY``, and it becomes selectable
    through the API and the frontend difficulty dropdown.
    """

    #: Short identifier used in the API and registry.
    name: str = 'base'

    @abc.abstractmethod
    def evaluate(self, game_state: 'GameState') -> int:
        """
        Return a centipawn score from **White's perspective**.

        Positive  → White is better.
        Negative  → Black is better.
        0         → Equal / draw.

        **Must not call** ``board.make_move`` / ``board.undo_move``.
        """

    def piece_value(self, piece_type: PieceType) -> int:
        """Standard centipawn value for a piece type (overridable)."""
        return STANDARD_VALUES.get(piece_type, 0)
