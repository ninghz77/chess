"""Tests for engine.game — GameState, result detection, serialisation."""
import pytest

from engine.board import Board
from engine.constants import Color, PieceType, sq
from engine.game import GameState, GameResult, DrawReason
from engine.move import Move


def make_game():
    return GameState()


# ---------------------------------------------------------------------------
# Basic operation
# ---------------------------------------------------------------------------

def test_initial_state_ongoing():
    g = make_game()
    assert g.result == GameResult.ONGOING


def test_make_move_returns_true_for_legal():
    g = make_game()
    assert g.make_move(Move(sq(6, 4), sq(4, 4)))


def test_make_move_returns_false_for_illegal():
    g = make_game()
    assert not g.make_move(Move(sq(4, 4), sq(3, 4)))  # empty square


def test_make_move_returns_false_when_game_over():
    g = make_game()
    g.resign(Color.WHITE)
    assert not g.make_move(Move(sq(6, 4), sq(4, 4)))


def test_legal_moves_cached():
    g = make_game()
    first  = g.legal_moves
    second = g.legal_moves
    assert first is second  # same list object


def test_legal_moves_invalidated_after_move():
    g = make_game()
    before = g.legal_moves
    g.make_move(Move(sq(6, 4), sq(4, 4)))
    after = g.legal_moves
    assert before is not after


# ---------------------------------------------------------------------------
# Resignation
# ---------------------------------------------------------------------------

def test_white_resigns_black_wins():
    g = make_game()
    g.resign(Color.WHITE)
    assert g.result == GameResult.BLACK_WINS
    assert g.resignation == Color.WHITE


def test_black_resigns_white_wins():
    g = make_game()
    g.resign(Color.BLACK)
    assert g.result == GameResult.WHITE_WINS


def test_double_resign_ignored():
    g = make_game()
    g.resign(Color.WHITE)
    g.resign(Color.BLACK)  # should be ignored
    assert g.result == GameResult.BLACK_WINS


# ---------------------------------------------------------------------------
# Checkmate (Scholar's mate)
# ---------------------------------------------------------------------------

def test_scholars_mate():
    """1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6?? 4.Qxf7#"""
    g = make_game()
    moves_uci = ['e2e4', 'e7e5', 'f1c4', 'b8c6', 'd1h5', 'g8f6', 'h5f7']
    for uci in moves_uci:
        m = Move.from_uci(uci)
        ok = g.make_move(m)
        assert ok, f'Move {uci} rejected'
    assert g.result == GameResult.WHITE_WINS


# ---------------------------------------------------------------------------
# Stalemate
# ---------------------------------------------------------------------------

def test_stalemate_detected():
    """Set up a stalemate position manually."""
    g = GameState.__new__(GameState)
    g.board = Board()
    g.board.squares = [None] * 64
    # Black king cornered, no legal moves, not in check
    g.board.squares[sq(0, 0)] = (Color.BLACK, PieceType.KING)
    g.board.squares[sq(2, 1)] = (Color.WHITE, PieceType.QUEEN)  # covers b8,a7
    g.board.squares[sq(7, 7)] = (Color.WHITE, PieceType.KING)
    g.board.turn = Color.BLACK
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
    g.result = GameResult.ONGOING
    g.draw_reason = None
    g.resignation = None
    g._record_position()
    g._update_result()
    assert g.result == GameResult.DRAW
    assert g.draw_reason == DrawReason.STALEMATE


# ---------------------------------------------------------------------------
# 50-move rule
# ---------------------------------------------------------------------------

def test_fifty_move_rule():
    g = make_game()
    g.board.halfmove_clock = 99
    # Make a quiet move that increments the clock to 100
    # Move the white king sideways to a free square — need to clear path
    g.board.squares[sq(7, 5)] = None
    g.board.squares[sq(7, 6)] = None
    g.board.squares[sq(6, 4)] = None  # remove pawn so e-file clear
    # Make knight move (quiet)
    g.board.squares[sq(7, 1)] = None  # remove Nb1
    g.board.squares[sq(5, 2)] = (Color.WHITE, PieceType.KNIGHT)  # knight at c3
    g._cached_legal = None
    ok = g.make_move(Move(sq(5, 2), sq(3, 3)))
    # halfmove clock should now be 100 → draw
    assert g.result == GameResult.DRAW
    assert g.draw_reason == DrawReason.FIFTY_MOVE


# ---------------------------------------------------------------------------
# Threefold repetition
# ---------------------------------------------------------------------------

def test_threefold_repetition():
    g = make_game()
    # Shuffle knights back and forth.
    # Starting position is recorded once at init.
    # Each round-trip (4 moves) adds one more occurrence of the start position.
    # After 2 complete cycles (8 moves) the start position has been recorded 3 times → draw.
    knight_out  = Move(sq(7, 1), sq(5, 2))  # Nb1-c3
    knight_back = Move(sq(5, 2), sq(7, 1))  # Nc3-b1
    n_out2  = Move(sq(0, 1), sq(2, 2))      # Nb8-c6
    n_back2 = Move(sq(2, 2), sq(0, 1))      # Nc6-b8

    # First cycle: start position count goes 1 → 2
    assert g.make_move(knight_out)
    assert g.make_move(n_out2)
    assert g.make_move(knight_back)
    assert g.make_move(n_back2)
    assert g.result == GameResult.ONGOING  # only 2nd occurrence so far

    # Second cycle: start position count goes 2 → 3 → threefold draw
    assert g.make_move(knight_out)
    assert g.make_move(n_out2)
    assert g.make_move(knight_back)
    assert g.make_move(n_back2)
    assert g.result == GameResult.DRAW
    assert g.draw_reason == DrawReason.THREEFOLD


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

def test_to_dict_structure():
    g = make_game()
    d = g.to_dict()
    assert 'board' in d
    assert 'turn' in d
    assert 'legal_moves' in d
    assert 'result' in d
    assert 'in_check' in d
    assert d['turn'] == 'WHITE'
    assert d['result'] == 'ongoing'
    assert len(d['board']) == 32
