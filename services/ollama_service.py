import requests


class OllamaService:
    def __init__(self, base_url="http://localhost:11434", model="gemma3:4b"):
        self.base_url = base_url
        self.model = model


    def generate(self, prompt, system_prompt="", temperature=0.7):
        url = f"{self.base_url}/api/generate"
        payload = {
        "model": self.model,
        "prompt": f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n",
        "temperature": temperature,
        "stream": False,
        }
        r = requests.post(url, json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        return data.get("response", "")


ollama = OllamaService()