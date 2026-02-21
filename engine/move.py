from dataclasses import dataclass
from typing import Optional

from engine.constants import PieceType, square_name, square_from_name

_PROMO_LETTER = {
    PieceType.QUEEN: 'q',
    PieceType.ROOK: 'r',
    PieceType.BISHOP: 'b',
    PieceType.KNIGHT: 'n',
}
_LETTER_PROMO = {v: k for k, v in _PROMO_LETTER.items()}


@dataclass
class Move:
    from_sq: int
    to_sq: int
    promotion: Optional[PieceType] = None
    is_castle: bool = False
    is_en_passant: bool = False

    def uci(self) -> str:
        s = square_name(self.from_sq) + square_name(self.to_sq)
        if self.promotion is not None:
            s += _PROMO_LETTER.get(self.promotion, '')
        return s

    @staticmethod
    def from_uci(uci: str) -> 'Move':
        from_sq = square_from_name(uci[:2])
        to_sq = square_from_name(uci[2:4])
        promotion = None
        if len(uci) == 5:
            promotion = _LETTER_PROMO.get(uci[4])
        return Move(from_sq, to_sq, promotion)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Move):
            return False
        return (
            self.from_sq == other.from_sq
            and self.to_sq == other.to_sq
            and self.promotion == other.promotion
        )

    def __hash__(self) -> int:
        return hash((self.from_sq, self.to_sq, self.promotion))

    def __repr__(self) -> str:
        return f'Move({self.uci()})'
