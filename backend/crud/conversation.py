from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    text: str
