from __future__ import annotations as _annotations

import json
import pathlib
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    TextPart,
    UserPromptPart,
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated

from backend.ai.agent import get_chat_agent, get_title_agent
from backend.crud.conversation import ChatMessageRequest
from backend.db.conversation import Conversation
from backend.db.core import get_db_session

router = APIRouter(prefix="/chat", tags=["chat"])

local_templates_dir = pathlib.Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=[local_templates_dir, "backend/templates"])


@router.get("/", response_class=HTMLResponse)
async def chat_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        name="chat_index.html", request=request, context={}
    )


@router.get("/{conversation_id}", response_class=HTMLResponse)
async def get_chat(
    conversation_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    conversation = await db_session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = ModelMessagesTypeAdapter.validate_python(conversation.messages)
    return templates.TemplateResponse(
        name="chat.html",
        request=request,
        context={
            "conversation_id": conversation.id,
            "title": conversation.title or "Chat",
            "messages": [_message_to_display_dict(message) for message in messages],
        },
    )


@router.post("/{conversation_id}", response_class=HTMLResponse)
async def chat(
    conversation_id: UUID,
    request: Request,
    message: Annotated[ChatMessageRequest, Form()],
    agent: Agent = Depends(get_chat_agent),
    db_session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    # Read message text from form or JSON
    if not message.text:
        return HTMLResponse("", status_code=204)

    conversation = await db_session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    assistant_text = await _ask_agent(
        conversation=conversation,
        question=message.text,
        agent=agent,
        db_session=db_session,
    )

    response = templates.TemplateResponse(
        name="partials/chat_message_response.html",
        request=request,
        context={
            "user_text": message.text,
            "assistant_text": assistant_text,
        },
    )
    return response


@router.post("/", response_class=HTMLResponse)
async def new_chat(
    request: Request,
    message: Annotated[ChatMessageRequest, Form()],
    title_agent: Agent = Depends(get_title_agent),
    chat_agent: Agent = Depends(get_chat_agent),
    db_session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    title = (await title_agent.run(message.text)).output

    conversation = Conversation(title=title)
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    conversation_id = conversation.id

    assistant_text = await _ask_agent(
        conversation=conversation,
        question=message.text,
        agent=chat_agent,
        db_session=db_session,
    )

    response = templates.TemplateResponse(
        name="chat.html",
        request=request,
        context={
            "conversation_id": conversation_id,
            "title": conversation.title,
            "user_text": message.text,
            "assistant_text": assistant_text,
        },
    )
    response.headers["HX-Push-Url"] = f"{router.prefix}/{conversation_id}"
    return response


async def _ask_agent(
    conversation: Conversation,
    question: str,
    agent: Agent,
    db_session: AsyncSession,
):
    """Ask an agent a question and persist the result."""
    # Build message_history for Agent from stored JSON
    messages = ModelMessagesTypeAdapter.validate_python(conversation.messages)
    message_history: list[ModelMessage]
    if messages:
        message_history = messages
    else:
        message_history = []

    result = await agent.run(question, message_history=message_history)

    # Persist updated message history back to DB (as JSON)
    updated_messages_bytes = result.all_messages_json()
    conversation.messages = json.loads(updated_messages_bytes.decode("utf-8"))
    conversation.updated_at = datetime.now()
    db_session.add(conversation)
    await db_session.commit()

    assistant_text = str(result.output)
    return assistant_text


def _message_to_display_dict(message: ModelMessage) -> dict[str, str]:
    parts = message.parts
    part_texts: list[str] = []
    for part in parts:
        if isinstance(part, UserPromptPart) and isinstance(part.content, str):
            part_texts.append(part.content)
        elif isinstance(part, TextPart):
            part_texts.append(part.content)
    return {
        "role": "user" if isinstance(message, ModelRequest) else "assistant",
        "content": "\n".join(part_texts),
    }
