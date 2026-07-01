"""Command-line chat interface for the Palatine History Chatbot.

Usage:
    python cli.py                 # interactive chat
    python cli.py "your question" # one-shot question
"""
from __future__ import annotations

import sys

import config
from src import ai_backend
from src.chatbot import Answer, Chatbot


def _print_answer(answer: Answer) -> None:
    print("\n" + answer.text.strip() + "\n")
    if answer.sources:
        print("— sources —")
        for i, r in enumerate(answer.sources, start=1):
            print(f"  [{i}] {r.chunk.source}: {r.chunk.title}  ({r.chunk.doc_id})")
    print()


def main() -> None:
    print("Palatine History Chatbot (CLI)")
    print(f"AI provider: {config.AI_PROVIDER}  |  configured: {ai_backend.is_configured()}")
    if not ai_backend.is_configured():
        print("(No AI key detected — running in search-only mode. Set ANTHROPIC_API_KEY "
              "or AI_PROVIDER=local for full answers.)")
    print("Building/loading index…")
    bot = Chatbot()

    if len(sys.argv) > 1:
        _print_answer(bot.ask(" ".join(sys.argv[1:])))
        return

    print("Type your question, or 'quit' to exit.\n")
    while True:
        try:
            q = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in {"quit", "exit", "q"}:
            break
        _print_answer(bot.ask(q))


if __name__ == "__main__":
    main()
