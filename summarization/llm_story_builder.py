from __future__ import annotations

import asyncio
from typing import List

from ingestion.raw_article import RawArticle
from local_llm_service import local_llm


async def build_story_headline(topic: str, article_summaries: List[str]) -> str:
    content = '\n'.join(f"- {summary}" for summary in article_summaries if summary)
    prompt = (
        "You are a leading news editor. Based on the following bullet summaries, "
        "write a specific, factual headline in 8-12 words. Avoid clickbait and keep title case.\n"
        f"Topic: {topic}\nSummaries:\n{content}\nHeadline:"
    )
    text = await local_llm.generate_text(prompt, max_new_tokens=32, temperature=0.2)
    headline = text.split('Headline:')[-1].strip()
    return headline


async def build_story_summary(topic: str, article_summaries: List[str]) -> str:
    content = '\n'.join(f"- {summary}" for summary in article_summaries if summary)
    prompt = (
        "You are a neutral newswire editor. Synthesize the bullet summaries into a "
        "concise 2-sentence recap with the most important facts.\n"
        f"Topic: {topic}\nSummaries:\n{content}\nRecap:"
    )
    text = await local_llm.generate_text(prompt, max_new_tokens=120, temperature=0.2)
    recap = text.split('Recap:')[-1].strip()
    return recap
