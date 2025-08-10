from __future__ import annotations as _annotations

from fastapi import Depends
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from backend.ai.provider.deep_infra import DeepInfraProvider


def get_model() -> OpenAIModel:
    return OpenAIModel("Qwen/Qwen3-235B-A22B", provider=DeepInfraProvider())


def get_chat_agent(model: OpenAIModel = Depends(get_model)) -> Agent:
    return Agent(model)


def get_title_agent(model: OpenAIModel = Depends(get_model)) -> Agent:
    return Agent(
        model,
        system_prompt=(
            "The following is the first message of a conversation. "
            "Reply with only a title for the conversation that is succinct and descriptive, "
            "capturing the topic of the conversation. "
        ),
    )
