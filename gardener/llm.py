"""A tiny client for any OpenAI-compatible chat endpoint.

Ollama, llama.cpp's server, vLLM and most hosted open-model providers all speak
this protocol, so Gemma can run on a laptop (Ollama), a DigitalOcean GPU
Droplet, or Google Cloud with nothing changed but environment variables:

    GARDENER_LLM_URL   base URL, default http://localhost:11434/v1  (Ollama)
    GARDENER_MODEL     model name, default gemma3:4b
    GARDENER_API_KEY   optional bearer token for hosted endpoints
    GARDENER_LLM       set to "off" to skip the model entirely

Standard library only (urllib), so the project has no dependencies to install.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gemma3:4b"


class LLMError(RuntimeError):
    """The model endpoint was unreachable, slow, or returned something unusable."""


@dataclass
class LLMClient:
    base_url: str = DEFAULT_URL
    model: str = DEFAULT_MODEL
    api_key: str = ""
    timeout: float = 45.0
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "LLMClient":
        return cls(
            base_url=os.environ.get("GARDENER_LLM_URL", DEFAULT_URL).rstrip("/"),
            model=os.environ.get("GARDENER_MODEL", DEFAULT_MODEL),
            api_key=os.environ.get("GARDENER_API_KEY", ""),
            timeout=float(os.environ.get("GARDENER_TIMEOUT", "45")),
            enabled=os.environ.get("GARDENER_LLM", "on").lower() not in ("off", "0", "false", "no"),
        )

    def _request(self, path: str, payload: dict | None, timeout: float) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = ""
            try:  # Ollama explains itself, e.g. 'model "gemma3:4b" not found, try pulling it first'
                detail = json.loads(e.read().decode()).get("error", {})
                detail = detail.get("message", "") if isinstance(detail, dict) else str(detail)
            except Exception:
                pass
            raise LLMError(f"model endpoint returned HTTP {e.code}" + (f": {detail}" if detail else "")) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LLMError(f"model endpoint unreachable ({e})") from e
        except json.JSONDecodeError as e:
            raise LLMError("model endpoint returned invalid JSON") from e

    def available(self) -> bool:
        """Cheap reachability check, used by /api/health."""
        if not self.enabled:
            return False
        try:
            self._request("/models", None, timeout=2.0)
            return True
        except LLMError:
            return False

    def complete(self, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> tuple[str, float]:
        """Send one user message, return (text, seconds).

        Instructions and data go in a single user turn on purpose: that is the
        one format every Gemma serving stack handles the same way, with or
        without native system-prompt support.
        """
        return self.chat(prompt, max_tokens=max_tokens, temperature=temperature)

    def chat(self, prompt: str, image: str | None = None, max_tokens: int = 320, temperature: float = 0.3,
             json_mode: bool = False, timeout: float | None = None) -> tuple[str, float]:
        """One user turn, optionally with an image (a base64 data URL), return (text, seconds).

        Images use the OpenAI message format, which Ollama, vLLM and llama.cpp
        accept for vision models such as Gemma 3 (4b and larger)."""
        if not self.enabled:
            raise LLMError("model disabled (GARDENER_LLM=off)")
        content: str | list = prompt
        if image:
            content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image}}]
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        body = self._request("/chat/completions", payload, timeout=timeout or self.timeout)
        elapsed = time.perf_counter() - start
        try:
            text = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError, TypeError) as e:
            raise LLMError("model response had no message content") from e
        if not text:
            raise LLMError("model returned an empty message")
        return text, elapsed
