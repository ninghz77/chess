"""Legal move generation for a chess Board."""
from typing import TYPE_CHECKING

from engine.constants import Color, PieceType, sq, row_col
from engine.move import Move

if TYPE_CHECKING:
    from engine.board import Board


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_legal_moves(board: 'Board') -> list[Move]:
    """Return all legal moves for the side whose turn it is."""
    color = board.turn
    pseudo = _pseudo_legal(board, color) + _castling_moves(board, color)
    opponent = Color.BLACK if color == Color.WHITE else Color.WHITE
    legal: list[Move] = []
    for move in pseudo:
        board.make_move(move)
        if not _is_attacked(board, board.find_king(color), opponent):  # type: ignore[arg-type]
            legal.append(move)
        board.undo_move()
    return legal


def is_in_check(board: 'Board', color: Color) -> bool:
    """Return True if *color*'s king is currently in check."""
    king_sq = board.find_king(color)
    if king_sq is None:
        return False
    opponent = Color.BLACK if color == Color.WHITE else Color.WHITE
    return _is_attacked(board, king_sq, opponent)


def is_square_attacked(board: 'Board', square: int, by_color: Color) -> bool:
    """Return True if *square* is attacked by any piece of *by_color*."""
    return _is_attacked(board, square, by_color)


# ---------------------------------------------------------------------------
# Pseudo-legal generation
# ---------------------------------------------------------------------------

def _pseudo_legal(board: 'Board', color: Color) -> list[Move]:
    moves: list[Move] = []
    for s in range(64):
        piece = board.squares[s]
        if piece is None or piece[0] != color:
            continue
        pt = piece[1]
        if pt == PieceType.PAWN:
            moves.extend(_pawn_moves(board, s, color))
        elif pt == PieceType.KNIGHT:
            moves.extend(_knight_moves(board, s, color))
        elif pt == PieceType.BISHOP:
            moves.extend(_sliding(board, s, color, _DIAG))
        elif pt == PieceType.ROOK:
            moves.extend(_sliding(board, s, color, _ORTH))
        elif pt == PieceType.QUEEN:
            moves.extend(_sliding(board, s, color, _DIAG + _ORTH))
        elif pt == PieceType.KING:
            moves.extend(_king_moves(board, s, color))
    return moves


_DIAG = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_ORTH = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_KNIGHT_DELTAS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
_KING_DELTAS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _pawn_moves(board: 'Board', s: int, color: Color) -> list[Move]:
    moves: list[Move] = []
    row, col = row_col(s)
    direction = -1 if color == Color.WHITE else 1
    start_row = 6 if color == Color.WHITE else 1
    promo_row = 0 if color == Color.WHITE else 7

    # Single push
    nr = row + direction
    if 0 <= nr <= 7:
        fwd = sq(nr, col)
        if board.squares[fwd] is None:
            if nr == promo_row:
                for pt in (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT):
                    moves.append(Move(s, fwd, promotion=pt))
            else:
                moves.append(Move(s, fwd))
                # Double push
                if row == start_row:
                    dbl = sq(row + 2 * direction, col)
                    if board.squares[dbl] is None:
                        moves.append(Move(s, dbl))

        # Captures
        for dc in (-1, 1):
            nc = col + dc
            if 0 <= nc <= 7:
                cap_sq = sq(nr, nc)
                target = board.squares[cap_sq]
                if target is not None and target[0] != color:
                    if nr == promo_row:
                        for pt in (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT):
                            moves.append(Move(s, cap_sq, promotion=pt))
                    else:
                        moves.append(Move(s, cap_sq))
                elif board.ep_square == cap_sq:
                    moves.append(Move(s, cap_sq, is_en_passant=True))

    return moves


def _knight_moves(board: 'Board', s: int, color: Color) -> list[Move]:
    moves: list[Move] = []
    row, col = row_col(s)
    for dr, dc in _KNIGHT_DELTAS:
        nr, nc = row + dr, col + dc
        if 0 <= nr <= 7 and 0 <= nc <= 7:
            ts = sq(nr, nc)
            t = board.squares[ts]
            if t is None or t[0] != color:
                moves.append(Move(s, ts))
    return moves


def _sliding(board: 'Board', s: int, color: Color, directions: list) -> list[Move]:
    moves: list[Move] = []
    row, col = row_col(s)
    for dr, dc in directions:
        r, c = row + dr, col + dc
        while 0 <= r <= 7 and 0 <= c <= 7:
            ts = sq(r, c)
            t = board.squares[ts]
            if t is None:
                moves.append(Move(s, ts))
            elif t[0] != color:
                moves.append(Move(s, ts))
                break
            else:
                break
            r += dr
            c += dc
    return moves


def _king_moves(board: 'Board', s: int, color: Color) -> list[Move]:
    moves: list[Move] = []
    row, col = row_col(s)
    for dr, dc in _KING_DELTAS:
        nr, nc = row + dr, col + dc
        if 0 <= nr <= 7 and 0 <= nc <= 7:
            ts = sq(nr, nc)
            t = board.squares[ts]
            if t is None or t[0] != color:
                moves.append(Move(s, ts))
    return moves


# ---------------------------------------------------------------------------
# Castling
# ---------------------------------------------------------------------------

def _castling_moves(board: 'Board', color: Color) -> list[Move]:
    moves: list[Move] = []
    opponent = Color.BLACK if color == Color.WHITE else Color.WHITE

    if color == Color.WHITE:
        king_sq = sq(7, 4)
        if board.squares[king_sq] != (Color.WHITE, PieceType.KING):
            return moves
        # Kingside
        if (board.castling_rights.get('K')
                and board.squares[sq(7, 7)] == (Color.WHITE, PieceType.ROOK)
                and board.squares[sq(7, 5)] is None
                and board.squares[sq(7, 6)] is None
                and not _is_attacked(board, sq(7, 4), opponent)
                and not _is_attacked(board, sq(7, 5), opponent)
                and not _is_attacked(board, sq(7, 6), opponent)):
            moves.append(Move(king_sq, sq(7, 6), is_castle=True))
        # Queenside
        if (board.castling_rights.get('Q')
                and board.squares[sq(7, 0)] == (Color.WHITE, PieceType.ROOK)
                and board.squares[sq(7, 3)] is None
                and board.squares[sq(7, 2)] is None
                and board.squares[sq(7, 1)] is None
                and not _is_attacked(board, sq(7, 4), opponent)
                and not _is_attacked(board, sq(7, 3), opponent)
                and not _is_attacked(board, sq(7, 2), opponent)):
            moves.append(Move(king_sq, sq(7, 2), is_castle=True))
    else:
        king_sq = sq(0, 4)
        if board.squares[king_sq] != (Color.BLACK, PieceType.KING):
            return moves
        # Kingside
        if (board.castling_rights.get('k')
                and board.squares[sq(0, 7)] == (Color.BLACK, PieceType.ROOK)
                and board.squares[sq(0, 5)] is None
                and board.squares[sq(0, 6)] is None
                and not _is_attacked(board, sq(0, 4), opponent)
                and not _is_attacked(board, sq(0, 5), opponent)
                and not _is_attacked(board, sq(0, 6), opponent)):
            moves.append(Move(king_sq, sq(0, 6), is_castle=True))
        # Queenside
        if (board.castling_rights.get('q')
                and board.squares[sq(0, 0)] == (Color.BLACK, PieceType.ROOK)
                and board.squares[sq(0, 3)] is None
                and board.squares[sq(0, 2)] is None
                and board.squares[sq(0, 1)] is None
                and not _is_attacked(board, sq(0, 4), opponent)
                and not _is_attacked(board, sq(0, 3), opponent)
                and not _is_attacked(board, sq(0, 2), opponent)):
            moves.append(Move(king_sq, sq(0, 2), is_castle=True))

    return moves


# ---------------------------------------------------------------------------
# Attack detection
# ---------------------------------------------------------------------------

def _is_attacked(board: 'Board', square: int, by_color: Color) -> bool:
    """Return True if *square* is attacked by *by_color*."""
    row, col = row_col(square)

    # Pawn attacks: pawns of by_color attack *from* the row in front of them
    pawn_from_row = row + (1 if by_color == Color.WHITE else -1)
    if 0 <= pawn_from_row <= 7:
        for dc in (-1, 1):
            pc = col + dc
            if 0 <= pc <= 7:
                p = board.squares[sq(pawn_from_row, pc)]
                if p and p[0] == by_color and p[1] == PieceType.PAWN:
                    return True

    # Knight attacks
    for dr, dc in _KNIGHT_DELTAS:
        nr, nc = row + dr, col + dc
        if 0 <= nr <= 7 and 0 <= nc <= 7:
            p = board.squares[sq(nr, nc)]
            if p and p[0] == by_color and p[1] == PieceType.KNIGHT:
                return True

    # Orthogonal sliders (rook, queen)
    for dr, dc in _ORTH:
        r, c = row + dr, col + dc
        while 0 <= r <= 7 and 0 <= c <= 7:
            p = board.squares[sq(r, c)]
            if p:
                if p[0] == by_color and p[1] in (PieceType.ROOK, PieceType.QUEEN):
                    return True
                break
            r += dr
            c += dc

    # Diagonal sliders (bishop, queen)
    for dr, dc in _DIAG:
        r, c = row + dr, col + dc
        while 0 <= r <= 7 and 0 <= c <= 7:
            p = board.squares[sq(r, c)]
            if p:
                if p[0] == by_color and p[1] in (PieceType.BISHOP, PieceType.QUEEN):
                    return True
                break
            r += dr
            c += dc

    # King attacks
    for dr, dc in _KING_DELTAS:
        nr, nc = row + dr, col + dc
        if 0 <= nr <= 7 and 0 <= nc <= 7:
            p = board.squares[sq(nr, nc)]
            if p and p[0] == by_color and p[1] == PieceType.KING:
                return True

    return False
