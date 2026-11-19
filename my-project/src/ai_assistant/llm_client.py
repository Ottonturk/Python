"""LLM клиент с поддержкой реального провайдера (OpenAI/совместимый API) и мока."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Абстрактный клиент для взаимодействия с LLM."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Выполнить запрос к LLM и вернуть текст ответа."""
        ...

    @abstractmethod
    def complete_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """Выполнить запрос к LLM и вернуть ответ в виде JSON-объекта."""
        ...


class MockLLMClient(LLMClient):
    """Мок LLM для разработки и тестирования без реального API."""

    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        prompt_lower = prompt.lower()

        if "спор" in prompt_lower or "дubl" in prompt_lower or "два одинаков" in prompt_lower:
            return json.dumps(
                {
                    "intent": "register_dispute",
                    "entities": {"operation_ids": [], "description": prompt[:200]},
                    "needs_data": True,
                    "confidence": 0.88,
                },
                ensure_ascii=False,
            )
        if any(w in prompt_lower for w in ["комисси", "списан", "списал", "списать", "комиссия"]):
            return json.dumps(
                {
                    "intent": "explain_commission",
                    "entities": {"amount": None, "currency": "RUB"},
                    "needs_data": True,
                    "confidence": 0.9,
                },
                ensure_ascii=False,
            )
        if "перевод" in prompt_lower or "переведи" in prompt_lower:
            return json.dumps(
                {
                    "intent": "prepare_transfer",
                    "entities": {
                        "recipient": None,
                        "amount": None,
                        "currency": "RUB",
                        "needs_clarification": True,
                    },
                    "needs_data": True,
                    "confidence": 0.85,
                },
                ensure_ascii=False,
            )
        if "оператор" in prompt_lower or "сотрудник" in prompt_lower or "человек" in prompt_lower:
            return json.dumps(
                {
                    "intent": "escalate_to_human",
                    "entities": {"context": prompt[:200]},
                    "needs_data": False,
                    "confidence": 0.95,
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"intent": "unknown", "entities": {}, "needs_data": False, "confidence": 0.5},
            ensure_ascii=False,
        )

    def complete_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        text = self.complete(prompt, system_prompt, temperature, max_tokens)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"intent": "unknown", "entities": {}, "confidence": 0.0}


class OpenAILLMClient(LLMClient):
    """Реальный LLM клиент через OpenAI API (или совместимый, например, vLLM, Llama.cpp)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-3.5-turbo",
        timeout: int = 30,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx is required for OpenAILLMClient. Install with: pip install httpx"
            ) from exc

        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = (
            base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = self._client.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    def complete_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        json_system = (
            (system_prompt or "")
            + "\n\nОтвечай строго в формате JSON, без дополнительного текста."
        )
        text = self.complete(
            prompt, json_system, temperature=temperature, max_tokens=max_tokens
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {"intent": "unknown", "entities": {}, "confidence": 0.0, "raw_response": text}


def create_llm_client(
    provider: str = "mock",
    **kwargs: Any,
) -> LLMClient:
    """Фабрика для создания LLM клиента.

    Args:
        provider: "mock" (по умолчанию) или "openai".
        **kwargs: Передаются в конструктор соответствующего клиента.

    Returns:
        Экземпляр LLMClient.
    """
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai":
        return OpenAILLMClient(**kwargs)
    raise ValueError(
        f"Неизвестный провайдер LLM: {provider}. Доступно: mock, openai"
    )