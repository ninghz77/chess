"""High-level GameState wrapping Board + history + result detection."""
from typing import Optional

from engine.board import Board
from engine.constants import Color, PieceType
from engine.move import Move
from engine.move_generator import generate_legal_moves, is_in_check
from engine.zobrist import ZobristHasher


class GameResult:
    ONGOING = 'ongoing'
    WHITE_WINS = 'white'
    BLACK_WINS = 'black'
    DRAW = 'draw'


class DrawReason:
    STALEMATE = 'stalemate'
    FIFTY_MOVE = 'fifty_move'
    THREEFOLD = 'threefold'
    INSUFFICIENT = 'insufficient_material'


class GameState:
    """
    Complete game state: board + move history + result detection.

    Call make_move() to advance the game.  Legal moves are cached and
    invalidated whenever the board changes.
    """

    def __init__(self) -> None:
        self.board = Board()
        self.board.setup_start_position()
        self._hasher = ZobristHasher()
        self._position_counts: dict[int, int] = {}
        self._move_history: list[Move] = []
        self._cached_legal: Optional[list[Move]] = None

        self.result: str = GameResult.ONGOING
        self.draw_reason: Optional[str] = None
        self.resignation: Optional[Color] = None

        self._record_position()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def legal_moves(self) -> list[Move]:
        if self._cached_legal is None:
            self._cached_legal = generate_legal_moves(self.board)
        return self._cached_legal

    @property
    def is_in_check(self) -> bool:
        return is_in_check(self.board, self.board.turn)

    @property
    def move_history(self) -> list[Move]:
        return list(self._move_history)

    # ------------------------------------------------------------------
    # Move execution
    # ------------------------------------------------------------------

    def make_move(self, move: Move) -> bool:
        """
        Attempt to make *move*.  Returns True on success, False if illegal
        or the game is already over.
        """
        if self.result != GameResult.ONGOING:
            return False
        if move not in self.legal_moves:
            return False

        self.board.make_move(move)
        self._move_history.append(move)
        self._cached_legal = None
        self._record_position()
        self._update_result()
        return True

    # ------------------------------------------------------------------
    # Resignation
    # ------------------------------------------------------------------

    def resign(self, color: Color) -> None:
        if self.result != GameResult.ONGOING:
            return
        self.resignation = color
        self.result = GameResult.BLACK_WINS if color == Color.WHITE else GameResult.WHITE_WINS

    # ------------------------------------------------------------------
    # Result detection
    # ------------------------------------------------------------------

    def _update_result(self) -> None:
        legal = self.legal_moves
        current = self.board.turn

        if not legal:
            if is_in_check(self.board, current):
                # Checkmate: the side that just moved wins
                self.result = GameResult.BLACK_WINS if current == Color.WHITE else GameResult.WHITE_WINS
            else:
                self.result = GameResult.DRAW
                self.draw_reason = DrawReason.STALEMATE
            return

        if self.board.halfmove_clock >= 100:
            self.result = GameResult.DRAW
            self.draw_reason = DrawReason.FIFTY_MOVE
            return

        h = self._hasher.hash_board(self.board)
        if self._position_counts.get(h, 0) >= 3:
            self.result = GameResult.DRAW
            self.draw_reason = DrawReason.THREEFOLD
            return

        if self._is_insufficient_material():
            self.result = GameResult.DRAW
            self.draw_reason = DrawReason.INSUFFICIENT

    def _is_insufficient_material(self) -> bool:
        pieces = [(s, c, pt) for s in range(64) if (p := self.board.squares[s]) for c, pt in [p]]
        if len(pieces) == 2:  # Only kings
            return True
        if len(pieces) == 3:  # K+B vs K or K+N vs K
            for _, _, pt in pieces:
                if pt in (PieceType.BISHOP, PieceType.KNIGHT):
                    return True
        if len(pieces) == 4:  # K+B vs K+B same color squares
            bishops = [(s, c) for s, c, pt in pieces if pt == PieceType.BISHOP]
            if len(bishops) == 2:
                s1, c1 = bishops[0]
                s2, c2 = bishops[1]
                if c1 != c2:  # Opposite colors own the bishops
                    if (s1 // 8 + s1 % 8) % 2 == (s2 // 8 + s2 % 8) % 2:
                        return True
        return False

    # ------------------------------------------------------------------
    # Zobrist helpers
    # ------------------------------------------------------------------

    def _record_position(self) -> None:
        h = self._hasher.hash_board(self.board)
        self._position_counts[h] = self._position_counts.get(h, 0) + 1

    def _unrecord_position(self) -> None:
        h = self._hasher.hash_board(self.board)
        count = self._position_counts.get(h, 0)
        if count <= 1:
            self._position_counts.pop(h, None)
        else:
            self._position_counts[h] = count - 1

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        board_array = []
        for s in range(64):
            piece = self.board.squares[s]
            if piece is not None:
                color, pt = piece
                board_array.append({
                    'color': color.name,
                    'type': pt.name,
                    'square': s,
                })

        legal_moves_list = [
            {
                'from': m.from_sq,
                'to': m.to_sq,
                'promotion': m.promotion.name if m.promotion else None,
                'is_castle': m.is_castle,
                'is_en_passant': m.is_en_passant,
            }
            for m in self.legal_moves
        ]

        return {
            'board': board_array,
            'turn': self.board.turn.name,
            'castling_rights': self.board.castling_rights,
            'ep_square': self.board.ep_square,
            'halfmove_clock': self.board.halfmove_clock,
            'fullmove_number': self.board.fullmove_number,
            'legal_moves': legal_moves_list,
            'in_check': self.is_in_check,
            'result': self.result,
            'draw_reason': self.draw_reason,
            'move_history': [m.uci() for m in self._move_history],
        }
