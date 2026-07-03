import json
import os
from typing import Any, Dict, List, Optional, Tuple

import anyio
import requests


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.api_url = api_url or os.getenv("LLM_API_URL")
        base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
        if not self.api_url and base_url:
            self.api_url = f"{base_url}/v1/chat/completions"
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.timeout_s = timeout_s

        if not self.api_url:
            raise ValueError("LLM_API_URL or LLM_BASE_URL must be set.")
        if not self.api_key:
            raise ValueError("LLM_API_KEY must be set.")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 800,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Dict[str, Any], Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        def _post() -> Dict[str, Any]:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            return response.json()

        data = await anyio.to_thread.run_sync(_post)
        content = None
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content")
        return content, payload, data
