"""LLM-based contract match verification using Ollama."""

import requests
from typing import Literal

MatchType = Literal["identical", "opposite", "unrelated", "unsure"]

SYSTEM_PROMPT = """Classify if two prediction market contracts resolve the SAME way or OPPOSITE way.

SAME: Both YES win together, both NO win together.
OPPOSITE: One YES wins when the other NO wins.
UNRELATED: Different events entirely.
UNSURE: Cannot confidently determine.

Output exactly one word: SAME, OPPOSITE, UNRELATED, or UNSURE."""


class LLMVerifier:
    """Verifies contract match types using Ollama."""

    def __init__(self, model: str, ollama_url: str = "http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url
        self._check_availability()

    def _check_availability(self) -> None:
        """Verify Ollama is running and model exists. Raises RuntimeError if not."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama not available at {self.ollama_url}: {e}")

        models = [m["name"] for m in resp.json().get("models", [])]
        model_base = self.model.split(":")[0]
        if not any(model_base in m for m in models):
            raise RuntimeError(
                f"Model '{self.model}' not found. Available: {models}. "
                f"Run: ollama pull {self.model}"
            )

    def classify(self, title_a: str, title_b: str) -> MatchType:
        """Classify whether two contracts resolve the same way or opposite."""
        prompt = f'A: "{title_a}"\nB: "{title_b}"'

        resp = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 5},
            },
            timeout=60,
        )
        resp.raise_for_status()

        answer = resp.json().get("response", "").strip().upper()

        if "SAME" in answer:
            return "identical"
        if "OPPOSITE" in answer:
            return "opposite"
        if "UNRELATED" in answer:
            return "unrelated"
        return "unsure"
