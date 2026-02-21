"""Tests for engine.move_generator — legal move generation."""
import pytest

from engine.board import Board
from engine.constants import Color, PieceType, sq
from engine.move import Move
from engine.move_generator import generate_legal_moves, is_in_check, is_square_attacked


@pytest.fixture()
def start_board():
    b = Board()
    b.setup_start_position()
    return b


# ---------------------------------------------------------------------------
# Starting position
# ---------------------------------------------------------------------------

def test_starting_position_20_moves(start_board):
    moves = generate_legal_moves(start_board)
    assert len(moves) == 20  # 16 pawn moves + 4 knight moves


def test_starting_position_black_20_moves(start_board):
    start_board.make_move(Move(sq(6, 4), sq(4, 4)))  # 1. e4
    moves = generate_legal_moves(start_board)
    assert len(moves) == 20


# ---------------------------------------------------------------------------
# Pawn moves
# ---------------------------------------------------------------------------

def test_pawn_double_push_only_from_start(start_board):
    start_board.make_move(Move(sq(6, 4), sq(4, 4)))  # e2-e4
    start_board.make_move(Move(sq(1, 0), sq(2, 0)))  # a7-a6
    # Pawn now on e4 — can only push one square
    e4_moves = [m for m in generate_legal_moves(start_board) if m.from_sq == sq(4, 4)]
    assert all(m.to_sq == sq(3, 4) for m in e4_moves)


def test_en_passant_generated(start_board):
    # 1.e4 e5 2.e5-e4 d5 — set up en passant
    start_board.make_move(Move(sq(6, 4), sq(4, 4)))  # e2-e4
    start_board.make_move(Move(sq(1, 3), sq(3, 3)))  # d7-d5
    start_board.make_move(Move(sq(4, 4), sq(3, 4)))  # e4-e5  (not real)
    # Actually properly: e4, then d5 by black, then e4-e5 doesn't exist. Let's just set up manually.
    b = Board()
    b.setup_start_position()
    b.make_move(Move(sq(6, 4), sq(4, 4)))  # e2-e4
    b.make_move(Move(sq(1, 3), sq(3, 3)))  # d7-d5
    # White e4 pawn can capture en passant on d3? No — black pawn moved to d5.
    # Now move white pawn to e5
    b.make_move(Move(sq(4, 4), sq(3, 4)))  # e4-e5
    # Black d5 is adjacent; white e-pawn is on e5.
    # White ep_square is d6 (sq(2,3))
    # Move black pawn to d5 and give white pawn chance
    # Easier: set up manually
    b2 = Board()
    b2.squares[sq(3, 4)] = (Color.WHITE, PieceType.PAWN)  # e5
    b2.squares[sq(3, 3)] = (Color.BLACK, PieceType.PAWN)  # d5
    b2.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b2.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b2.ep_square = sq(2, 3)  # d6
    b2.turn = Color.WHITE
    ep_moves = [m for m in generate_legal_moves(b2) if m.is_en_passant]
    assert len(ep_moves) == 1
    assert ep_moves[0].to_sq == sq(2, 3)


def test_promotion_moves_generated():
    b = Board()
    b.squares[sq(1, 0)] = (Color.WHITE, PieceType.PAWN)
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    promo_moves = [m for m in moves if m.from_sq == sq(1, 0) and m.promotion is not None]
    assert len(promo_moves) == 4
    promo_types = {m.promotion for m in promo_moves}
    assert PieceType.QUEEN in promo_types
    assert PieceType.ROOK  in promo_types
    assert PieceType.BISHOP in promo_types
    assert PieceType.KNIGHT in promo_types


# ---------------------------------------------------------------------------
# Castling
# ---------------------------------------------------------------------------

def test_white_kingside_castling():
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(7, 7)] = (Color.WHITE, PieceType.ROOK)
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    castle = [m for m in moves if m.is_castle and m.to_sq == sq(7, 6)]
    assert len(castle) == 1


def test_white_queenside_castling():
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(7, 0)] = (Color.WHITE, PieceType.ROOK)
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    castle = [m for m in moves if m.is_castle and m.to_sq == sq(7, 2)]
    assert len(castle) == 1


def test_castling_blocked_by_piece():
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(7, 7)] = (Color.WHITE, PieceType.ROOK)
    b.squares[sq(7, 6)] = (Color.WHITE, PieceType.KNIGHT)  # blocks kingside
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    castle = [m for m in moves if m.is_castle]
    assert len(castle) == 0


def test_cannot_castle_through_check():
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(7, 7)] = (Color.WHITE, PieceType.ROOK)
    b.squares[sq(0, 5)] = (Color.BLACK, PieceType.ROOK)  # attacks f1 = sq(7,5)
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    castle = [m for m in moves if m.is_castle]
    assert len(castle) == 0


# ---------------------------------------------------------------------------
# Check detection
# ---------------------------------------------------------------------------

def test_is_in_check_no(start_board):
    assert not is_in_check(start_board, Color.WHITE)


def test_is_in_check_yes():
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(5, 4)] = (Color.BLACK, PieceType.ROOK)  # attacks king
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    assert is_in_check(b, Color.WHITE)


def test_pinned_piece_cannot_move():
    """A piece that would expose the king cannot move."""
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(5, 4)] = (Color.WHITE, PieceType.ROOK)  # on same file — pinned
    b.squares[sq(3, 4)] = (Color.BLACK, PieceType.ROOK)  # pins the rook
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    rook_moves = [m for m in moves if m.from_sq == sq(5, 4)]
    # Rook can only move along the pin-file (to capture the attacker or stay on file)
    off_file = [m for m in rook_moves if m.to_sq % 8 != 4]
    assert len(off_file) == 0


def test_only_legal_moves_in_check():
    """When in check only moves that remove check are legal."""
    b = Board()
    b.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    b.squares[sq(5, 4)] = (Color.BLACK, PieceType.ROOK)
    b.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    b.turn = Color.WHITE
    moves = generate_legal_moves(b)
    # All legal moves must leave White king not in check
    for move in moves:
        b.make_move(move)
        assert not is_in_check(b, Color.WHITE), f'Move {move} left king in check'
        b.undo_move()


# ---------------------------------------------------------------------------
# is_square_attacked
# ---------------------------------------------------------------------------

def test_square_attacked_by_pawn():
    b = Board()
    b.squares[sq(3, 4)] = (Color.BLACK, PieceType.PAWN)
    assert is_square_attacked(b, sq(4, 3), Color.BLACK)
    assert is_square_attacked(b, sq(4, 5), Color.BLACK)
    assert not is_square_attacked(b, sq(4, 4), Color.BLACK)


def test_square_attacked_by_knight():
    b = Board()
    b.squares[sq(4, 4)] = (Color.WHITE, PieceType.KNIGHT)
    attacked = {sq(2,3), sq(2,5), sq(3,2), sq(3,6), sq(5,2), sq(5,6), sq(6,3), sq(6,5)}
    for s in attacked:
        assert is_square_attacked(b, s, Color.WHITE), f'sq {s} should be attacked'
