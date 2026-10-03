from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


class PushToken(CamelModel):
    token: str = Field(pattern=r"^Expo(nent)?PushToken\[.+\]$", max_length=200)
    platform: Literal["ios", "android"]
