"""Ollama LLM Provider for Prince AI Team (100% Free & Local)."""

import json
import requests
from typing import Any, Dict, List, Optional
import os
from config import OLLAMA_HOST, OLLAMA_MODEL
from llm.base import LLMProvider
from logging_utils.logger import get_logger

logger = get_logger("OllamaProvider")


class OllamaProvider(LLMProvider):
    """Local LLM provider using Ollama API."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = (host or OLLAMA_HOST).rstrip("/")
        self.model = model or OLLAMA_MODEL
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))

    def check_status(self) -> Dict[str, Any]:
        """Verifies if Ollama is online and lists available models."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                model_ready = any(self.model in m for m in models)
                return {
                    "online": True,
                    "provider": "ollama",
                    "host": self.host,
                    "model": self.model,
                    "model_ready": model_ready,
                    "available_models": models,
                    "message": f"Ollama online with {len(models)} models."
                }
            return {
                "online": False,
                "provider": "ollama",
                "host": self.host,
                "message": f"Ollama HTTP {resp.status_code}"
            }
        except Exception as e:
            return {
                "online": False,
                "provider": "ollama",
                "host": self.host,
                "message": f"Could not connect to Ollama at {self.host} ({e})"
            }

    def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        json_mode: bool = False
    ) -> str:
        """Calls local Ollama /api/chat."""
        formatted_msgs = []
        if system_prompt:
            formatted_msgs.append({"role": "system", "content": system_prompt})
        formatted_msgs.extend(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_msgs,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
            else:
                err = f"Ollama error {resp.status_code}: {resp.text}"
                logger.error(err)
                return f"[Ollama Error {resp.status_code}]"
        except requests.exceptions.ConnectionError:
            err = f"Cannot reach Ollama at {self.host}. Please start Ollama (`ollama serve`)."
            logger.error(err)
            return f"[Offline Error] {err}"
        except Exception as e:
            logger.error(f"Ollama generation exception: {e}")
            return f"[Ollama Exception: {e}]"
