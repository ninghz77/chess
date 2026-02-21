"""Simple material-count evaluator."""
from engine.constants import Color
from evaluators.base import EvaluatorBase


class SimpleMaterialEvaluator(EvaluatorBase):
    """
    Evaluate a position purely by summing piece values.

    White pieces add to the score; Black pieces subtract.
    Kings are included so checkmate (king captured conceptually) is
    reflected in deeply-searched positions, but in practice the search
    terminates at checkmate before king capture.
    """

    name = 'material'

    def evaluate(self, game_state) -> int:
        score = 0
        for s in range(64):
            piece = game_state.board.squares[s]
            if piece is not None:
                color, pt = piece
                val = self.piece_value(pt)
                score += val if color == Color.WHITE else -val
        return score
