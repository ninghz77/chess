"""Zobrist hashing for fast threefold-repetition detection."""
import random

from engine.constants import Color, PieceType


class ZobristHasher:
    """Deterministic Zobrist hash table seeded once at import time."""

    def __init__(self, seed: int = 42) -> None:
        rng = random.Random(seed)

        # piece_table[color_int][piece_type_int][square]
        self.piece_table: list[list[list[int]]] = [
            [
                [rng.getrandbits(64) for _ in range(64)]
                for _ in range(6)  # 6 piece types
            ]
            for _ in range(2)  # 2 colors
        ]
        self.black_to_move: int = rng.getrandbits(64)
        # Castling: K, Q, k, q
        self.castling: list[int] = [rng.getrandbits(64) for _ in range(4)]
        # En-passant: one random per file (0-7)
        self.ep_file: list[int] = [rng.getrandbits(64) for _ in range(8)]

    def hash_board(self, board) -> int:
        """Compute the full Zobrist hash for the given Board."""
        h = 0
        for s in range(64):
            piece = board.squares[s]
            if piece is not None:
                color, pt = piece
                h ^= self.piece_table[int(color)][int(pt)][s]
        if board.turn == Color.BLACK:
            h ^= self.black_to_move
        for i, key in enumerate(('K', 'Q', 'k', 'q')):
            if board.castling_rights.get(key):
                h ^= self.castling[i]
        if board.ep_square is not None:
            h ^= self.ep_file[board.ep_square % 8]
        return h
