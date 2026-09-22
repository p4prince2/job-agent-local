"""Modular LLM Client for Prince AI Team.

Defaults to local Ollama (100% free, private, offline).
Supports llama3.2 (already installed) and other local models.
Provides modular adapters for optional Gemini / OpenAI compatible endpoints.
"""

import json
import logging
import requests
from typing import Any, Dict, List, Optional
from core.config import (
    LLM_PROVIDER,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)

logger = logging.getLogger("PrinceAI.LLM")


class LLMClient:
    """Modular LLM client supporting local Ollama, Gemini, and OpenAI-compatible providers."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = (provider or LLM_PROVIDER).lower()
        self.model = model or OLLAMA_MODEL
        self.ollama_host = OLLAMA_HOST
        self.timeout = 120  # generous timeout for local model generation

    def check_status(self) -> Dict[str, Any]:
        """Checks connectivity to the configured LLM provider and lists available models."""
        if self.provider == "ollama":
            try:
                resp = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    model_found = any(self.model in m for m in models)
                    return {
                        "online": True,
                        "provider": "ollama",
                        "host": self.ollama_host,
                        "current_model": self.model,
                        "model_ready": model_found,
                        "available_models": models,
                        "message": f"Ollama is online with {len(models)} models."
                    }
                return {
                    "online": False,
                    "provider": "ollama",
                    "host": self.ollama_host,
                    "message": f"Ollama responded with status code {resp.status_code}."
                }
            except Exception as e:
                return {
                    "online": False,
                    "provider": "ollama",
                    "host": self.ollama_host,
                    "message": f"Cannot connect to Ollama at {self.ollama_host}. Is Ollama running? ({e})"
                }
        elif self.provider == "gemini":
            return {
                "online": bool(GEMINI_API_KEY),
                "provider": "gemini",
                "message": "Gemini API key configured" if GEMINI_API_KEY else "Missing GEMINI_API_KEY"
            }
        else:
            return {
                "online": bool(OPENAI_API_KEY),
                "provider": "openai",
                "message": "OpenAI / compatible endpoint configured" if OPENAI_API_KEY else "Missing OPENAI_API_KEY"
            }

    def generate(self, messages: List[Dict[str, str]], system_prompt: Optional[str] = None,
                 temperature: float = 0.7, json_mode: bool = False) -> str:
        """Generates a text completion given message history."""
        if self.provider == "ollama":
            return self._generate_ollama(messages, system_prompt, temperature, json_mode)
        elif self.provider == "gemini":
            return self._generate_gemini(messages, system_prompt, temperature)
        elif self.provider == "openai":
            return self._generate_openai(messages, system_prompt, temperature, json_mode)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _generate_ollama(self, messages: List[Dict[str, str]], system_prompt: Optional[str],
                         temperature: float, json_mode: bool) -> str:
        """Call local Ollama /api/chat endpoint."""
        formatted_msgs = []
        if system_prompt:
            formatted_msgs.append({"role": "system", "content": system_prompt})
        formatted_msgs.extend(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_msgs,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(
                f"{self.ollama_host}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                msg = data.get("message", {})
                return msg.get("content", "").strip()
            else:
                logger.error(f"Ollama error {resp.status_code}: {resp.text}")
                return f"[Ollama Error {resp.status_code}]: {resp.text}"
        except requests.exceptions.ConnectionError:
            err = f"Failed to connect to local Ollama at {self.ollama_host}. Please ensure Ollama is running (`ollama serve`)."
            logger.error(err)
            return f"[Offline Mode] {err}"
        except Exception as e:
            logger.error(f"Ollama generation exception: {e}")
            return f"[Ollama Exception]: {str(e)}"

    def _generate_gemini(self, messages: List[Dict[str, str]], system_prompt: Optional[str],
                         temperature: float) -> str:
        """Fallback to Google Gemini API if configured."""
        if not GEMINI_API_KEY:
            return "[Error: GEMINI_API_KEY not configured in .env]"
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
            for m in messages:
                role = "user" if m.get("role") in ("user", "system") else "model"
                contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
            resp = requests.post(url, json={"contents": contents, "generationConfig": {"temperature": temperature}}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            return f"[Gemini Error {resp.status_code}]: {resp.text}"
        except Exception as e:
            return f"[Gemini Exception]: {e}"

    def _generate_openai(self, messages: List[Dict[str, str]], system_prompt: Optional[str],
                         temperature: float, json_mode: bool) -> str:
        """Fallback to OpenAI-compatible endpoint if configured."""
        if not OPENAI_API_KEY:
            return "[Error: OPENAI_API_KEY not configured in .env]"
        try:
            url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
            formatted = []
            if system_prompt:
                formatted.append({"role": "system", "content": system_prompt})
            formatted.extend(messages)
            payload = {
                "model": self.model or "gpt-3.5-turbo",
                "messages": formatted,
                "temperature": temperature
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            resp = requests.post(url, headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            return f"[OpenAI Error {resp.status_code}]: {resp.text}"
        except Exception as e:
            return f"[OpenAI Exception]: {e}"


# Singleton default client
default_llm = LLMClient()
