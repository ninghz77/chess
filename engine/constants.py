import enum


class Color(enum.IntEnum):
    WHITE = 0
    BLACK = 1


class PieceType(enum.IntEnum):
    PAWN = 0
    KNIGHT = 1
    BISHOP = 2
    ROOK = 3
    QUEEN = 4
    KING = 5


PIECE_VALUES = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20000,
}

PIECE_LETTERS = {
    PieceType.PAWN: 'p',
    PieceType.KNIGHT: 'n',
    PieceType.BISHOP: 'b',
    PieceType.ROOK: 'r',
    PieceType.QUEEN: 'q',
    PieceType.KING: 'k',
}


def sq(row: int, col: int) -> int:
    """Convert (row, col) to square index 0-63. row 0 = rank 8 (black's back rank)."""
    return row * 8 + col


def row_col(square: int) -> tuple[int, int]:
    """Convert square index to (row, col)."""
    return square // 8, square % 8


def square_name(square: int) -> str:
    """Convert square index to algebraic notation (e.g. 0 -> a8, 63 -> h1)."""
    row, col = row_col(square)
    return chr(ord('a') + col) + str(8 - row)


def square_from_name(name: str) -> int:
    """Convert algebraic notation to square index (e.g. 'e4' -> 36)."""
    col = ord(name[0]) - ord('a')
    row = 8 - int(name[1])
    return sq(row, col)
