from typing import Optional

from engine.constants import Color, PieceType, sq, row_col
from engine.move import Move

# (Color, PieceType) tuple
Piece = tuple[Color, PieceType]

_BACK_RANK: list[PieceType] = [
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
]


class Board:
    """
    Mutable 8x8 board state.

    Squares are indexed 0-63: row 0 = rank 8 (black back rank), col 0 = a-file.
    square = row * 8 + col.
    """

    def __init__(self) -> None:
        self.squares: list[Optional[Piece]] = [None] * 64
        self.turn: Color = Color.WHITE
        # K = white kingside, Q = white queenside, k = black kingside, q = black queenside
        self.castling_rights: dict[str, bool] = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.ep_square: Optional[int] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        # Undo stack: each entry is a dict with enough info to restore
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_start_position(self) -> None:
        """Place pieces in the standard starting position."""
        self.squares = [None] * 64
        self.turn = Color.WHITE
        self.castling_rights = {'K': True, 'Q': True, 'k': True, 'q': True}
        self.ep_square = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._history = []

        for col, pt in enumerate(_BACK_RANK):
            self.squares[sq(0, col)] = (Color.BLACK, pt)
        for col in range(8):
            self.squares[sq(1, col)] = (Color.BLACK, PieceType.PAWN)
        for col in range(8):
            self.squares[sq(6, col)] = (Color.WHITE, PieceType.PAWN)
        for col, pt in enumerate(_BACK_RANK):
            self.squares[sq(7, col)] = (Color.WHITE, pt)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def piece_at(self, square: int) -> Optional[Piece]:
        return self.squares[square]

    # ------------------------------------------------------------------
    # Make / Undo
    # ------------------------------------------------------------------

    def make_move(self, move: Move) -> None:
        """Execute a move (assumed pseudo-legal or legal) and push undo info."""
        piece = self.squares[move.from_sq]
        assert piece is not None, f'No piece at {move.from_sq}'
        color, piece_type = piece

        undo: dict = {
            'move': move,
            'captured': self.squares[move.to_sq],
            'ep_captured': None,
            'castling_rights': self.castling_rights.copy(),
            'ep_square': self.ep_square,
            'halfmove_clock': self.halfmove_clock,
            'fullmove_number': self.fullmove_number,
        }

        # En passant capture: remove the captured pawn
        if move.is_en_passant:
            ep_cap_row = move.to_sq // 8 + (1 if color == Color.WHITE else -1)
            ep_cap_sq = ep_cap_row * 8 + move.to_sq % 8
            undo['ep_captured'] = (ep_cap_sq, self.squares[ep_cap_sq])
            self.squares[ep_cap_sq] = None

        # Move the piece
        self.squares[move.to_sq] = piece
        self.squares[move.from_sq] = None

        # Promotion
        if move.promotion is not None:
            self.squares[move.to_sq] = (color, move.promotion)

        # Castling: also move the rook
        if move.is_castle:
            if move.to_sq == sq(7, 6):   # White kingside
                self.squares[sq(7, 5)] = self.squares[sq(7, 7)]
                self.squares[sq(7, 7)] = None
            elif move.to_sq == sq(7, 2): # White queenside
                self.squares[sq(7, 3)] = self.squares[sq(7, 0)]
                self.squares[sq(7, 0)] = None
            elif move.to_sq == sq(0, 6): # Black kingside
                self.squares[sq(0, 5)] = self.squares[sq(0, 7)]
                self.squares[sq(0, 7)] = None
            elif move.to_sq == sq(0, 2): # Black queenside
                self.squares[sq(0, 3)] = self.squares[sq(0, 0)]
                self.squares[sq(0, 0)] = None

        # Update en passant square
        self.ep_square = None
        if piece_type == PieceType.PAWN:
            from_row = move.from_sq // 8
            to_row = move.to_sq // 8
            if abs(to_row - from_row) == 2:
                self.ep_square = ((from_row + to_row) // 2) * 8 + (move.from_sq % 8)

        # Update castling rights
        if piece_type == PieceType.KING:
            if color == Color.WHITE:
                self.castling_rights['K'] = False
                self.castling_rights['Q'] = False
            else:
                self.castling_rights['k'] = False
                self.castling_rights['q'] = False

        if piece_type == PieceType.ROOK:
            _rook_castling_update(self.castling_rights, move.from_sq)

        # A rook being captured also loses castling rights
        if undo['captured'] is not None:
            _rook_castling_update(self.castling_rights, move.to_sq)

        # Halfmove clock
        if piece_type == PieceType.PAWN or undo['captured'] is not None or move.is_en_passant:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Fullmove number
        if color == Color.BLACK:
            self.fullmove_number += 1

        # Switch turn
        self.turn = Color.BLACK if color == Color.WHITE else Color.WHITE

        self._history.append(undo)

    def undo_move(self) -> None:
        """Restore the board to the state before the last make_move call."""
        if not self._history:
            return
        undo = self._history.pop()
        move = undo['move']

        # Switch turn back
        self.turn = Color.BLACK if self.turn == Color.WHITE else Color.WHITE
        color = self.turn

        # Restore the moving piece (un-promote if needed)
        piece_at_dest = self.squares[move.to_sq]
        moving_piece: Piece = (color, PieceType.PAWN) if move.promotion else piece_at_dest  # type: ignore[assignment]

        self.squares[move.from_sq] = moving_piece
        self.squares[move.to_sq] = undo['captured']

        # Restore en-passant captured pawn
        if move.is_en_passant and undo['ep_captured']:
            ep_sq, ep_piece = undo['ep_captured']
            self.squares[ep_sq] = ep_piece

        # Restore rook if castling
        if move.is_castle:
            if move.to_sq == sq(7, 6):
                self.squares[sq(7, 7)] = self.squares[sq(7, 5)]
                self.squares[sq(7, 5)] = None
            elif move.to_sq == sq(7, 2):
                self.squares[sq(7, 0)] = self.squares[sq(7, 3)]
                self.squares[sq(7, 3)] = None
            elif move.to_sq == sq(0, 6):
                self.squares[sq(0, 7)] = self.squares[sq(0, 5)]
                self.squares[sq(0, 5)] = None
            elif move.to_sq == sq(0, 2):
                self.squares[sq(0, 0)] = self.squares[sq(0, 3)]
                self.squares[sq(0, 3)] = None

        # Restore game state fields
        self.castling_rights = undo['castling_rights']
        self.ep_square = undo['ep_square']
        self.halfmove_clock = undo['halfmove_clock']
        self.fullmove_number = undo['fullmove_number']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def find_king(self, color: Color) -> Optional[int]:
        for s in range(64):
            p = self.squares[s]
            if p and p[0] == color and p[1] == PieceType.KING:
                return s
        return None

    def copy(self) -> 'Board':
        b = Board()
        b.squares = self.squares[:]
        b.turn = self.turn
        b.castling_rights = self.castling_rights.copy()
        b.ep_square = self.ep_square
        b.halfmove_clock = self.halfmove_clock
        b.fullmove_number = self.fullmove_number
        # Don't copy history — the copy is used for read-only queries
        return b


def _rook_castling_update(rights: dict[str, bool], square: int) -> None:
    """Remove castling right when a rook moves from or is captured on its home square."""
    if square == sq(7, 7):
        rights['K'] = False
    elif square == sq(7, 0):
        rights['Q'] = False
    elif square == sq(0, 7):
        rights['k'] = False
    elif square == sq(0, 0):
        rights['q'] = False
