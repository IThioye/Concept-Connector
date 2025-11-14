import asyncio
from typing import Any, Dict

import httpx
import requests


class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma3:4b", timeout: float = 60.0):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def _build_payload(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> Dict[str, Any]:
        return {
            "model": self.model,
            "prompt": f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n",
            "temperature": temperature,
            "stream": False,
        }

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        url = f"{self.base_url}/api/generate"
        payload = self._build_payload(prompt, system_prompt=system_prompt, temperature=temperature)
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")

    async def agenerate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        """Async variant of generate using httpx.AsyncClient."""
        payload = self._build_payload(prompt, system_prompt=system_prompt, temperature=temperature)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return data.get("response", "")

    async def ensure_async(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        """Convenience wrapper that allows sync contexts to reuse the async API via asyncio."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return await self.agenerate(prompt, system_prompt=system_prompt, temperature=temperature)
        return asyncio.run(self.agenerate(prompt, system_prompt=system_prompt, temperature=temperature))


ollama = OllamaService()
