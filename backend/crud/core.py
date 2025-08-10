from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    database: bool

