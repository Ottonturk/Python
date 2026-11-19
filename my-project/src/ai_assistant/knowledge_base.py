"""RAG Knowledge Base — simplified file-based implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    version: str
    effective_from: datetime
    effective_to: datetime | None
    source_url: str
    title: str
    content: str
    category: str


class KnowledgeBase:
    """In-memory knowledge base with versioned chunks."""

    def __init__(self) -> None:
        self._chunks: list[KnowledgeChunk] = []
        self._initialized = False

    def initialize(self, seed_data: list[dict[str, Any]]) -> None:
        for doc in seed_data:
            doc_id = doc["document_id"]
            version = doc.get("version", "1.0")
            eff_from = datetime.fromisoformat(doc["effective_from"])
            eff_to = (
                datetime.fromisoformat(doc["effective_to"])
                if doc.get("effective_to")
                else None
            )
            source_url = doc.get("source_url", f"internal://docs/{doc_id}")
            title = doc.get("title", doc_id)
            category = doc.get("category", "faq")

            for i, chunk_text in enumerate(doc["chunks"]):
                chunk_id = f"{doc_id}::{version}::chunk-{i}"
                self._chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        version=version,
                        effective_from=eff_from,
                        effective_to=eff_to,
                        source_url=source_url,
                        title=title,
                        content=chunk_text,
                        category=category,
                    )
                )
        self._initialized = True

    def search(
        self,
        query: str,
        client_id: str = "",
        as_of: datetime | None = None,
        limit: int = 5,
    ) -> list[KnowledgeChunk]:
        if not self._initialized:
            return []

        as_of = as_of or datetime.now()
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in self._chunks:
            if chunk.effective_from > as_of:
                continue
            if chunk.effective_to is not None and chunk.effective_to < as_of:
                continue

            content_lower = chunk.content.lower()
            content_words = set(re.findall(r"\w+", content_lower))
            overlap = len(query_words & content_words)
            if overlap == 0:
                continue

            phrase_boost = 2 if query_lower in content_lower else 0
            score = overlap + phrase_boost
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def get_source_citation(self, chunk: KnowledgeChunk) -> str:
        date_str = chunk.effective_from.strftime("%d.%m.%Y")
        return f"{chunk.title} (v{chunk.version}, с {date_str}): {chunk.source_url}"