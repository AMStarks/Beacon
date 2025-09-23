import os
import json
import hashlib
from typing import Dict, Any, List, Optional
import httpx


class LLMService:
    """Wrapper for Grok (x.ai) chat completions used to refine titles and summaries.

    Controlled via env flags:
      - GROK_API_KEY: required to enable
      - LLM_TITLES=1 to allow title refinement
      - LLM_SUMMARIES=1 to allow summary refinement
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("GROK_API_KEY")
        self.enabled = bool(self.api_key)
        self.base_url = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1/chat/completions")
        self.model = os.getenv("GROK_MODEL", "grok-4-latest")
        self.allow_titles = os.getenv("LLM_TITLES", "0") not in {"0", "false", "False", "off"}
        self.allow_summaries = os.getenv("LLM_SUMMARIES", "0") not in {"0", "false", "False", "off"}
        self.client = httpx.AsyncClient(timeout=20.0)
        # In-memory cache for this process
        self._cache: Dict[str, Dict[str, str]] = {}

    def _key(self, headlines: List[str], current_title: str, current_summary: str) -> str:
        text = "\n".join(headlines) + "\n" + current_title + "\n" + current_summary
        return hashlib.md5(text.encode()).hexdigest()

    async def refine(self, headlines: List[str], sources: List[str], current_title: str, current_summary: str) -> Dict[str, str]:
        """Return possibly improved {title, summary}. Falls back to current on failure."""
        result = {"title": current_title, "summary": current_summary}
        if not self.enabled or (not self.allow_titles and not self.allow_summaries):
            return result

        cache_key = self._key(headlines, current_title, current_summary)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return {"title": cached.get("title", current_title), "summary": cached.get("summary", current_summary)}

        system = (
            "You are an assistant that writes concise, neutral news topic titles and summaries. "
            "Rules: 1) Be specific; include key actors/teams and outcome. 2) No hype or adjectives. "
            "3) For sports, prefer 'Team A beat Team B SCORE' when known. 4) Summary is 1-2 sentences, factual, with no opinion. "
            "5) Keep titles under 60 characters. 6) Use proper title case: capitalize first word and all important words, "
            "but lowercase articles (a, an, the), prepositions (in, on, at, to, for, of, with, by), and conjunctions (and, or, but). "
            "7) Avoid truncation - write complete, clear titles."
        )

        user = {
            "headlines": headlines[:8],
            "sources": sources[:8],
            "current_title": current_title,
            "current_summary": current_summary,
            "requirements": {
                "improve_title": bool(self.allow_titles),
                "improve_summary": bool(self.allow_summaries)
            }
        }

        payload = {
            "model": self.model,
            "stream": False,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    "Given JSON, return a compact JSON with keys title and summary. "
                    "If an item should not change, copy it. "
                    "IMPORTANT: Write complete, clear titles under 60 characters. No truncation or ellipses. "
                    "Use proper title case: capitalize important words, lowercase articles/prepositions/conjunctions. "
                    "JSON follows:\n" + json.dumps(user)
                )}
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            resp = await self.client.post(self.base_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            parsed = json.loads(content) if content.startswith("{") else {}
            title = parsed.get("title") or current_title
            summary = parsed.get("summary") or current_summary
            self._cache[cache_key] = {"title": title, "summary": summary}
            return {"title": title, "summary": summary}
        except Exception:
            return result

    async def close(self) -> None:
        await self.client.aclose()


