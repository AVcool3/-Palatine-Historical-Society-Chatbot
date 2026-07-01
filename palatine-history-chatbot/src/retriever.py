"""Keyword retrieval over the indexed chunks using a pure-Python BM25 ranker.

No external services or embedding APIs are required, so search works fully
offline. If you later want semantic search, this is the module to swap out.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List

from src.ingest import Chunk, build_index, load_index, save_index

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common words that add noise to keyword matching.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "at", "by", "with", "as", "that", "this",
    "it", "from", "what", "when", "who", "where", "which", "how", "why", "did",
    "do", "does", "about", "tell", "me", "i", "you", "was", "into", "over",
}


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


class BM25Retriever:
    """Classic BM25 ranking over the chunk corpus."""

    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self._doc_tokens: List[List[str]] = [_tokenize(c.text) for c in chunks]
        self._doc_len = [len(toks) for toks in self._doc_tokens]
        self._avgdl = (sum(self._doc_len) / len(self._doc_len)) if self._doc_len else 0.0
        self._term_freqs: List[Counter] = [Counter(toks) for toks in self._doc_tokens]
        self._idf = self._compute_idf()

    def _compute_idf(self) -> dict:
        n = len(self.chunks)
        df: Counter = Counter()
        for toks in self._doc_tokens:
            for term in set(toks):
                df[term] += 1
        idf = {}
        for term, freq in df.items():
            # BM25 idf with +1 smoothing to keep values positive.
            idf[term] = math.log(1 + (n - freq + 0.5) / (freq + 0.5))
        return idf

    def search(self, query: str, top_k: int = 6) -> List[SearchResult]:
        q_terms = _tokenize(query)
        if not q_terms or not self.chunks:
            return []
        scores: List[float] = []
        for i, tf in enumerate(self._term_freqs):
            dl = self._doc_len[i] or 1
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                idf = self._idf.get(term, 0.0)
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
                score += idf * (freq * (self.k1 + 1)) / denom
            scores.append(score)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = [SearchResult(self.chunks[i], scores[i]) for i in ranked if scores[i] > 0]
        return results[:top_k]


def get_retriever(rebuild: bool = False) -> BM25Retriever:
    """Load the index (building it first if missing or if rebuild=True)."""
    chunks = [] if rebuild else load_index()
    if not chunks:
        chunks = build_index()
        save_index(chunks)
    return BM25Retriever(chunks)
