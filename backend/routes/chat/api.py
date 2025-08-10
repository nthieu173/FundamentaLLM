from __future__ import annotations as _annotations

import json
import pathlib
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.models.openai import OpenAIModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.provider.deep_infra import DeepInfraProvider
from backend.db.conversation import Conversation
from backend.db.core import db_session

router = APIRouter()

local_templates_dir = pathlib.Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=[local_templates_dir, "backend/templates"])


def _get_agent() -> Agent[Any, Any]:
    model = OpenAIModel("Qwen/Qwen3-235B-A22B", provider=DeepInfraProvider())
    return Agent(model)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(name="index.html", request=request, context={})


@router.post("/chat/start", response_class=HTMLResponse)
async def start_conversation(
    request: Request, db_session: AsyncSession = Depends(db_session)
) -> HTMLResponse:
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        title: Optional[str] = data.get("title")
    else:
        form = await request.form()
        title = form.get("title")

    conversation = Conversation(title=title)
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    response = templates.TemplateResponse(
        name="chat.html",
        request=request,
        context={
            "conversation_id": conversation.id,
            "title": conversation.title or "New Chat",
        },
    )
    # Inform HTMX to push the new URL so refresh/back works nicely
    response.headers["HX-Push-Url"] = f"/chat/{conversation.id}"
    return response


@router.get("/chat/{conversation_id}", response_class=HTMLResponse)
async def get_chat(
    conversation_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    conversation = await db_session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return templates.TemplateResponse(
        name="chat.html",
        request=request,
        context={
            "conversation_id": conversation.id,
            "title": conversation.title or "Chat",
        },
    )


@router.post("/chat/{conversation_id}", response_class=HTMLResponse)
async def chat(
    conversation_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    # Read message text from form or JSON
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        user_text: str = data.get("text", "").strip()
    else:
        form = await request.form()
        user_text = (form.get("text") or "").strip()

    if not user_text:
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

    agent = _get_agent()
    result = await agent.run(user_text, message_history=message_history)

    # Persist updated message history back to DB (as JSON)
    updated_messages_bytes = result.all_messages_json()
    conversation.messages = json.loads(updated_messages_bytes.decode("utf-8"))
    conversation.updated_at = datetime.now()
    db_session.add(conversation)
    await db_session.commit()

    assistant_text = str(result.output)

    return templates.TemplateResponse(
        name="partials/_chat_messages_append.html",
        request=request,
        context={
            "user_text": user_text,
            "assistant_text": assistant_text,
        },
    )


@router.post("/chat/{conversation_id}/import", response_class=HTMLResponse)
async def import_conversation(
    conversation_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    # Accept either JSON body or form field named "payload" with JSON
    messages: Any
    title: Optional[str]
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
        else:
            form = await request.form()
            raw = form.get("payload") or "{}"
            data = json.loads(raw)
        title = data.get("title")
        messages = data["messages"]
        # Validate messages can round-trip through Pydantic AI loader
        _ = ModelMessagesTypeAdapter.validate_python(messages)
    except Exception as e:  # noqa: BLE001
        return templates.TemplateResponse(
            name="partials/_import_result.html",
            request=request,
            context={"ok": False, "error": str(e)},
            status_code=400,
        )

    conversation = await db_session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.title = title if title is not None else conversation.title
    conversation.messages = messages
    conversation.updated_at = datetime.now()
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    return templates.TemplateResponse(
        name="partials/_import_result.html",
        request=request,
        context={"ok": True, "title": conversation.title},
    )
