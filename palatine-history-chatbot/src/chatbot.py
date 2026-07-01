"""The chatbot: retrieve relevant passages, then ask the AI backend to answer
using only those passages, with citations.

If no AI provider is configured, it degrades gracefully to a "search mode" that
returns the most relevant passages directly, so the tool is still useful.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import config
from src import ai_backend
from src.retriever import BM25Retriever, SearchResult, get_retriever

SYSTEM_PROMPT = (
    "You are a knowledgeable, friendly assistant specializing in the history of "
    "Palatine, Illinois and Palatine Township. Answer the user's question using "
    "ONLY the numbered context passages provided. If the answer is not in the "
    "passages, say you don't have that information in your records and suggest "
    "the user check the Palatine Historical Society (palatinehistoricalsociety.com). "
    "Be concise and factual. Cite the passages you used with their bracket "
    "numbers like [1], [2]. Do not invent dates, names, or facts."
)


@dataclass
class Answer:
    text: str
    sources: List[SearchResult]
    used_ai: bool


def _build_context(results: List[SearchResult]) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        c = r.chunk
        blocks.append(f"[{i}] (Source: {c.source} — \"{c.title}\")\n{c.text}")
    return "\n\n".join(blocks)


class Chatbot:
    def __init__(self, retriever: Optional[BM25Retriever] = None):
        self.retriever = retriever or get_retriever()

    def ask(self, question: str, top_k: Optional[int] = None) -> Answer:
        top_k = top_k or config.TOP_K
        results = self.retriever.search(question, top_k=top_k)

        if not results:
            return Answer(
                text=(
                    "I couldn't find anything about that in my records. Try "
                    "rephrasing, or add relevant files to data/my_documents/ and "
                    "re-run the ingest."
                ),
                sources=[],
                used_ai=False,
            )

        # If no AI provider is configured, return the passages directly.
        if not ai_backend.is_configured():
            return Answer(text=self._format_search_only(results), sources=results, used_ai=False)

        context = _build_context(results)
        user_prompt = (
            f"Context passages:\n\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer using only the passages above, and cite them like [1]."
        )
        try:
            text = ai_backend.generate_answer(SYSTEM_PROMPT, user_prompt)
            return Answer(text=text, sources=results, used_ai=True)
        except ai_backend.BackendError as exc:
            # Fall back to search-only mode but tell the user why.
            fallback = self._format_search_only(results)
            return Answer(
                text=f"(AI answering unavailable: {exc}\nShowing the most relevant passages instead.)\n\n{fallback}",
                sources=results,
                used_ai=False,
            )

    @staticmethod
    def _format_search_only(results: List[SearchResult]) -> str:
        lines = ["Here are the most relevant passages from the records:\n"]
        for i, r in enumerate(results, start=1):
            snippet = r.chunk.text.strip().replace("\n", " ")
            if len(snippet) > 500:
                snippet = snippet[:500] + "…"
            lines.append(f"[{i}] {r.chunk.source} — {r.chunk.title}\n{snippet}\n")
        return "\n".join(lines)
