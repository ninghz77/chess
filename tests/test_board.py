"""Tests for engine.board — setup, make_move, undo_move."""
import pytest

from engine.board import Board
from engine.constants import Color, PieceType, sq
from engine.move import Move


@pytest.fixture()
def board():
    b = Board()
    b.setup_start_position()
    return b


# ---------------------------------------------------------------------------
# Starting position
# ---------------------------------------------------------------------------

def test_starting_position_piece_count(board):
    pieces = [p for p in board.squares if p is not None]
    assert len(pieces) == 32


def test_white_pawns_on_rank_2(board):
    for col in range(8):
        p = board.squares[sq(6, col)]
        assert p == (Color.WHITE, PieceType.PAWN)


def test_black_pawns_on_rank_7(board):
    for col in range(8):
        p = board.squares[sq(1, col)]
        assert p == (Color.BLACK, PieceType.PAWN)


def test_white_back_rank(board):
    back = [PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK]
    for col, pt in enumerate(back):
        assert board.squares[sq(7, col)] == (Color.WHITE, pt)


def test_empty_ranks(board):
    for row in range(2, 6):
        for col in range(8):
            assert board.squares[sq(row, col)] is None


def test_initial_turn_is_white(board):
    assert board.turn == Color.WHITE


def test_castling_rights_all_true(board):
    assert all(board.castling_rights.values())


# ---------------------------------------------------------------------------
# make_move / undo_move round-trip
# ---------------------------------------------------------------------------

def test_pawn_push_and_undo(board):
    move = Move(sq(6, 4), sq(4, 4))  # e2-e4
    board.make_move(move)
    assert board.squares[sq(4, 4)] == (Color.WHITE, PieceType.PAWN)
    assert board.squares[sq(6, 4)] is None
    assert board.turn == Color.BLACK

    board.undo_move()
    assert board.squares[sq(6, 4)] == (Color.WHITE, PieceType.PAWN)
    assert board.squares[sq(4, 4)] is None
    assert board.turn == Color.WHITE


def test_double_pawn_push_sets_ep(board):
    move = Move(sq(6, 4), sq(4, 4))
    board.make_move(move)
    assert board.ep_square == sq(5, 4)


def test_undo_restores_ep(board):
    board.make_move(Move(sq(6, 4), sq(4, 4)))
    ep_before = board.ep_square
    board.make_move(Move(sq(1, 4), sq(3, 4)))
    board.undo_move()
    assert board.ep_square == ep_before


def test_halfmove_clock_resets_on_pawn_move(board):
    board.halfmove_clock = 5
    board.make_move(Move(sq(6, 4), sq(4, 4)))
    assert board.halfmove_clock == 0


def test_halfmove_clock_increments_on_quiet_move(board):
    # Move a knight — quiet, no pawn, no capture
    board.make_move(Move(sq(6, 4), sq(5, 4)))  # e2-e3 (pawn, resets)
    board.make_move(Move(sq(1, 4), sq(2, 4)))  # e7-e6
    board.halfmove_clock = 0  # reset manually to test knight
    board.make_move(Move(sq(7, 1), sq(5, 2)))  # Nb1-c3
    assert board.halfmove_clock == 1


def test_fullmove_increments_after_black(board):
    assert board.fullmove_number == 1
    board.make_move(Move(sq(6, 4), sq(4, 4)))
    assert board.fullmove_number == 1  # still 1 after White
    board.make_move(Move(sq(1, 4), sq(3, 4)))
    assert board.fullmove_number == 2  # 2 after Black


def test_castling_rights_lost_on_king_move(board):
    # Clear path for White king to move
    board.squares[sq(7, 5)] = None
    board.squares[sq(7, 6)] = None
    board.make_move(Move(sq(7, 4), sq(7, 5)))
    assert not board.castling_rights['K']
    assert not board.castling_rights['Q']


def test_castling_rights_restored_on_undo(board):
    board.squares[sq(7, 5)] = None
    board.squares[sq(7, 6)] = None
    board.make_move(Move(sq(7, 4), sq(7, 5)))
    board.undo_move()
    assert board.castling_rights['K']
    assert board.castling_rights['Q']


def test_promotion(board):
    # Place a white pawn one step from promotion
    board.squares = [None] * 64
    board.squares[sq(1, 0)] = (Color.WHITE, PieceType.PAWN)
    board.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    board.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    board.make_move(Move(sq(1, 0), sq(0, 0), promotion=PieceType.QUEEN))
    assert board.squares[sq(0, 0)] == (Color.WHITE, PieceType.QUEEN)


def test_promotion_undo(board):
    board.squares = [None] * 64
    board.squares[sq(1, 0)] = (Color.WHITE, PieceType.PAWN)
    board.squares[sq(7, 4)] = (Color.WHITE, PieceType.KING)
    board.squares[sq(0, 4)] = (Color.BLACK, PieceType.KING)
    board.make_move(Move(sq(1, 0), sq(0, 0), promotion=PieceType.QUEEN))
    board.undo_move()
    assert board.squares[sq(1, 0)] == (Color.WHITE, PieceType.PAWN)
    assert board.squares[sq(0, 0)] is None
