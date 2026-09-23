"""Optional Anthropic API provider for Prince AI Team."""

import requests
from typing import Any, Dict, List, Optional
from config import ANTHROPIC_API_KEY
from llm.base import LLMProvider
from logging_utils.logger import get_logger

logger = get_logger("AnthropicProvider")


class AnthropicProvider(LLMProvider):
    """Optional cloud LLM provider using Anthropic Messages API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def check_status(self) -> Dict[str, Any]:
        has_key = bool(self.api_key and self.api_key.startswith("sk-ant"))
        return {
            "online": has_key,
            "provider": "anthropic",
            "model": self.model,
            "message": "Anthropic API key configured" if has_key else "Missing or invalid ANTHROPIC_API_KEY in .env"
        }

    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False
    ) -> str:
        if not self.api_key:
            return "[Error: ANTHROPIC_API_KEY not configured]"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        # Filter and structure messages for Anthropic API
        formatted = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "assistant"
            formatted.append({"role": role, "content": m.get("content", "")})

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": formatted
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data["content"][0]["text"].strip()
            else:
                return f"[Anthropic Error {resp.status_code}: {resp.text}]"
        except Exception as e:
            return f"[Anthropic Exception: {e}]"
