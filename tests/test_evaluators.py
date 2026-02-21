"""Tests for evaluators.material and evaluators.positional."""
import pytest

from engine.board import Board
from engine.constants import Color, PieceType, sq
from engine.game import GameState
from evaluators.material import SimpleMaterialEvaluator
from evaluators.positional import PositionalEvaluator


def _bare_game(white_pieces, black_pieces):
    """Helper: create a GameState with only specified pieces."""
    g = GameState.__new__(GameState)
    g.board = Board()
    g.board.squares = [None] * 64
    for s, pt in white_pieces:
        g.board.squares[s] = (Color.WHITE, pt)
    for s, pt in black_pieces:
        g.board.squares[s] = (Color.BLACK, pt)
    g.board.turn = Color.WHITE
    g.board.castling_rights = {'K': False, 'Q': False, 'k': False, 'q': False}
    g.board.ep_square = None
    g.board.halfmove_clock = 0
    g.board.fullmove_number = 1
    g.board._history = []
    from engine.zobrist import ZobristHasher
    g._hasher = ZobristHasher()
    g._position_counts = {}
    g._move_history = []
    g._cached_legal = None
    from engine.game import GameResult
    g.result = GameResult.ONGOING
    g.draw_reason = None
    g.resignation = None
    return g


# ---------------------------------------------------------------------------
# SimpleMaterialEvaluator
# ---------------------------------------------------------------------------

class TestSimpleMaterialEvaluator:
    def setup_method(self):
        self.ev = SimpleMaterialEvaluator()

    def test_equal_material_is_zero(self):
        g = GameState()
        assert self.ev.evaluate(g) == 0

    def test_white_queen_up(self):
        g = _bare_game(
            [(sq(7,4), PieceType.KING), (sq(4,4), PieceType.QUEEN)],
            [(sq(0,4), PieceType.KING)],
        )
        score = self.ev.evaluate(g)
        assert score == 900  # queen value

    def test_black_rook_up(self):
        g = _bare_game(
            [(sq(7,4), PieceType.KING)],
            [(sq(0,4), PieceType.KING), (sq(3,3), PieceType.ROOK)],
        )
        score = self.ev.evaluate(g)
        assert score == -500  # rook value for black

    def test_equal_material_after_capture(self):
        g = _bare_game(
            [(sq(7,4), PieceType.KING), (sq(4,4), PieceType.PAWN)],
            [(sq(0,4), PieceType.KING), (sq(3,3), PieceType.PAWN)],
        )
        assert self.ev.evaluate(g) == 0

    def test_piece_value_overridable(self):
        class DoubledPawns(SimpleMaterialEvaluator):
            def piece_value(self, pt):
                base = super().piece_value(pt)
                return base * 2 if pt == PieceType.PAWN else base

        ev2 = DoubledPawns()
        g = _bare_game(
            [(sq(7,4), PieceType.KING), (sq(4,4), PieceType.PAWN)],
            [(sq(0,4), PieceType.KING)],
        )
        assert ev2.evaluate(g) == 200  # pawn doubled to 200


# ---------------------------------------------------------------------------
# PositionalEvaluator
# ---------------------------------------------------------------------------

class TestPositionalEvaluator:
    def setup_method(self):
        self.ev = PositionalEvaluator()

    def test_starting_position_near_zero(self):
        """Starting position should be symmetric (roughly 0 or small positive for White)."""
        g = GameState()
        score = self.ev.evaluate(g)
        # Symmetric board: score should be exactly 0 due to PST symmetry
        assert score == 0

    def test_central_pawn_better_than_edge(self):
        """A pawn on e4 should score higher than a pawn on a2 for White."""
        g_center = _bare_game(
            [(sq(7,4), PieceType.KING), (sq(4,4), PieceType.PAWN)],
            [(sq(0,4), PieceType.KING)],
        )
        g_edge = _bare_game(
            [(sq(7,4), PieceType.KING), (sq(6,0), PieceType.PAWN)],
            [(sq(0,4), PieceType.KING)],
        )
        assert self.ev.evaluate(g_center) > self.ev.evaluate(g_edge)

    def test_name(self):
        assert self.ev.name == 'positional'

    def test_material_name(self):
        assert SimpleMaterialEvaluator().name == 'material'
