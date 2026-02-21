"""Pydantic request/response models for the REST API."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class NewGameRequest(BaseModel):
    mode: Literal['hvh', 'hvc', 'cvc'] = 'hvh'
    white_evaluator: Optional[str] = Field(
        default=None,
        description="Evaluator name for White AI. None means human controls White.",
    )
    black_evaluator: Optional[str] = Field(
        default=None,
        description="Evaluator name for Black AI. None means human controls Black.",
    )
    white_depth: int = Field(default=3, ge=1, le=6)
    black_depth: int = Field(default=3, ge=1, le=6)


class NewGameResponse(BaseModel):
    session_id: str
    mode: str


class GameStateResponse(BaseModel):
    session_id: str
    state: dict


class ResignRequest(BaseModel):
    color: Literal['white', 'black'] = 'white'
