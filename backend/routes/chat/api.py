from __future__ import annotations as _annotations

import json
import pathlib
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
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
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(name="index.html", request=request, context={})


@router.get("/{conversation_id}", response_class=HTMLResponse)
async def get_chat_messages(
    conversation_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    conversation = await db_session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return templates.TemplateResponse(
        name="partials/chat_messages.html",
        request=request,
        context={
            "conversation_id": conversation.id,
            "title": conversation.title or "Chat",
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

    # Build message_history for Agent from stored JSON
    stored_messages_json = json.dumps(conversation.messages).encode("utf-8")
    message_history: list[ModelMessage]
    if conversation.messages:
        message_history = ModelMessagesTypeAdapter.validate_json(stored_messages_json)
    else:
        message_history = []

    result = await agent.run(message.text, message_history=message_history)

    # Persist updated message history back to DB (as JSON)
    updated_messages_bytes = result.all_messages_json()
    conversation.messages = json.loads(updated_messages_bytes.decode("utf-8"))
    conversation.updated_at = datetime.now()
    db_session.add(conversation)
    await db_session.commit()

    assistant_text = str(result.output)

    return templates.TemplateResponse(
        name="partials/chat_message_response.html",
        request=request,
        context={
            "user_text": message.text,
            "assistant_text": assistant_text,
        },
    )


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

    chat_response = await chat(
        conversation_id=conversation.id,
        request=request,
        message=message,
        agent=chat_agent,
        db_session=db_session,
    )

    # Inform HTMX to push the new URL so refresh/back works nicely
    chat_response.headers["HX-Push-Url"] = f"{router.prefix}/{conversation.id}"
    return chat_response
