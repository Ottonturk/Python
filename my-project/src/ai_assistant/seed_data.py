"""Seed data for the knowledge base."""

from typing import Any

from .knowledge_base import KnowledgeBase

SEED_DOCUMENTS: list[dict[str, Any]] = [
    {
        "document_id": "tariff-card-classic",
        "version": "2.1",
        "effective_from": "2024-01-01",
        "effective_to": None,
        "source_url": "internal://docs/tariffs/card-classic-v2.1",
        "title": "Тариф «Классическая карта»",
        "category": "tariff",
        "chunks": [
            "Ежемесячная комиссия за обслуживание карты «Классическая» — 299 рублей.",
            "Комиссия не взимается, если средний остаток на счёте за месяц превышает 50 000 рублей.",
            "Бесплатное обслуживание предоставляется при оформлении зарплатного проекта.",
        ],
    },
    {
        "document_id": "tariff-card-classic",
        "version": "1.0",
        "effective_from": "2023-01-01",
        "effective_to": "2023-12-31",
        "source_url": "internal://docs/tariffs/card-classic-v1.0",
        "title": "Тариф «Классическая карта» (архив)",
        "category": "tariff",
        "chunks": [
            "Ежемесячная комиссия за обслуживание карты «Классическая» — 199 рублей.",
            "Бесплатное обслуживание при среднем остатке от 30 000 рублей.",
        ],
    },
    {
        "document_id": "faq-transfers",
        "version": "1.0",
        "effective_from": "2024-01-01",
        "effective_to": None,
        "source_url": "internal://docs/faq/transfers",
        "title": "FAQ: Переводы",
        "category": "faq",
        "chunks": [
            "Перевод между своими счетами в банке — бесплатно.",
            "Перевод на карту другого банка по номеру карты — комиссия 1%, минимум 30 рублей.",
            "Перевод по номеру телефона (СБП) до 100 000 рублей в месяц — бесплатно.",
        ],
    },
    {
        "document_id": "contract-individual",
        "version": "1.0",
        "effective_from": "2024-03-01",
        "effective_to": None,
        "source_url": "internal://docs/contracts/client-12345",
        "title": "Индивидуальные условия договора клиента 12345",
        "category": "contract",
        "chunks": [
            "Клиенту предоставлена скидка: комиссия за обслуживание карты — 0 рублей в течение первого года.",
            "Бесплатные переводы по СБП до 200 000 рублей в месяц.",
        ],
    },
]


def create_seed_knowledge_base() -> KnowledgeBase:
    kb = KnowledgeBase()
    kb.initialize(SEED_DOCUMENTS)
    return kb