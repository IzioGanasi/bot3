from pydantic import BaseModel, Field
from typing import Any, Union

class WsMessageBody(BaseModel):
    name: str
    version: str = "1.0"
    body: dict[str, Any] = Field(default_factory=dict)

class WsRequest(BaseModel):
    name: str
    request_id: str
    msg: Union[WsMessageBody, dict[str, Any]]

class Balance(BaseModel):
    id: int
    type: int
    amount: float
    currency: str
    is_fiat: bool = False
    is_marginal: bool = False

    @property
    def type_name(self):
        return {
            1: "Prática",
            4: "Real",
            2: "Teste",
            6: "Outro"
        }.get(self.type, f"Tipo {self.type}")

class Candle(BaseModel):
    id: int
    from_time: int = Field(alias="from")
    to_time: int = Field(alias="to")
    open: float
    close: float
    min: float
    max: float
    volume: float
