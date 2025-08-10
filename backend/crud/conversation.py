from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class StartConversationRequest(BaseModel):
    title: Optional[str] = None


class StartConversationResponse(BaseModel):
    conversation_id: UUID
    title: Optional[str] = None

class ChatMessageRequest(BaseModel):
    text: str


class ChatMessageResponse(BaseModel):
    conversation_id: UUID
    reply_text: str
    usage_total_tokens: Optional[int] = None



class ConversationImportRequest(BaseModel):
    title: Optional[str] = None
    messages: Any


class ConversationExportResponse(BaseModel):
    conversation_id: UUID
    title: Optional[str] = None
    messages: Any
    created_at: datetime
    updated_at: datetime
