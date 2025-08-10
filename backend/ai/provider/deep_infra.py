from __future__ import annotations as _annotations

import os
import pathlib

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates
from httpx import AsyncClient as AsyncHTTPClient
from openai import AsyncOpenAI
from pydantic_ai.exceptions import UserError
from pydantic_ai.models import cached_async_http_client
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.profiles.openai import OpenAIJsonSchemaTransformer, OpenAIModelProfile
from pydantic_ai.providers import Provider

router = APIRouter()

local_templates_dir = pathlib.Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=[local_templates_dir, "backend/templates"])


class DeepInfraProvider(Provider[AsyncOpenAI]):
    @property
    def name(self) -> str:
        return "deepinfra"

    @property
    def base_url(self) -> str:
        return "https://api.deepinfra.com/v1/openai"

    @property
    def client(self) -> AsyncOpenAI:
        return self._client

    def model_profile(self, model_name: str) -> ModelProfile | None:
        return OpenAIModelProfile(
            json_schema_transformer=OpenAIJsonSchemaTransformer,
            supports_json_object_output=True,
        )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        openai_client: AsyncOpenAI | None = None,
        http_client: AsyncHTTPClient | None = None,
    ) -> None:
        api_key = api_key or os.getenv("DEEPINFRA_API_KEY")
        if not api_key and openai_client is None:
            raise UserError(
                "Set the `DEEPINFRA_API_KEY` environment variable or pass it via "
                "`DeepInfraProvider(api_key=...)` to use the DeepInfra provider."
            )

        if openai_client is not None:
            self._client = openai_client
        elif http_client is not None:
            self._client = AsyncOpenAI(
                base_url=self.base_url, api_key=api_key, http_client=http_client
            )
        else:
            http_client = cached_async_http_client(provider="deepinfra")
            self._client = AsyncOpenAI(
                base_url=self.base_url, api_key=api_key, http_client=http_client
            )
