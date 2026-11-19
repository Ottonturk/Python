"""AI Engine: scenario handling for the MVP assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .knowledge_base import KnowledgeBase
from .llm_client import LLMClient, MockLLMClient, create_llm_client
from .seed_data import create_seed_knowledge_base
from .models import ActionStatus, ActionType, Client
from .action_manager import ActionManager


class AIEngine:
    """Orchestrates the three mandatory scenarios: A, B, C."""

    def __init__(
        self,
        action_manager: ActionManager,
        kb: KnowledgeBase | None = None,
        llm_client: LLMClient | None = None,
        llm_provider: str = "mock",
        **llm_kwargs: Any,
    ) -> None:
        self._am = action_manager
        self._kb = kb or create_seed_knowledge_base()
        self._llm = llm_client or create_llm_client(llm_provider, **llm_kwargs)

    # ------------------------------------------------------------------
    # Scenario A: Explanation of commission
    # ------------------------------------------------------------------
    def handle_commission_query(
        self,
        client: Client,
        query: str,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        """Answer a question about a fee/commission with source citation."""
        as_of = as_of or datetime.now()

        # 1. LLM анализирует намерение и извлекает сущности
        llm_result = self._llm.complete_json(
            prompt=(
                f"Проанализируй запрос клиента: \"{query}\"\n"
                f"Определи намерение (intent) и извлеки сущности (entities).\n"
                f"Возможные намерения: explain_commission, prepare_transfer, register_dispute, escalate_to_human, unknown.\n"
                f"Ответь в формате JSON: {{intent, entities, confidence}}"
            ),
            system_prompt="Ты — банковский AI-ассистент. Анализируй запросы клиентов на русском языке.",
            temperature=0.3,
        )

        intent = llm_result.get("intent", "unknown")
        confidence = float(llm_result.get("confidence", 0.0))

        if intent != "explain_commission":
            return {
                "scenario": "A",
                "status": "unknown_intent",
                "answer": (
                    "Я не уверен, что понимаю ваш вопрос. "
                    "Переформулируйте, пожалуйста, или обратитесь в поддержку."
                ),
                "sources": [],
                "confidence": confidence,
                "detected_intent": intent,
            }

        # 2. RAG поиск знаний с учетом актуальности на дату
        chunks = self._kb.search(query, client.client_id, as_of=as_of, limit=5)

        if not chunks:
            return {
                "scenario": "A",
                "status": "no_data",
                "answer": (
                    "Не удалось найти информацию о тарифах и условиях, "
                    "действовавших на указанную дату. Обратитесь в поддержку."
                ),
                "sources": [],
                "confidence": confidence,
            }

        # 3. LLM формирует ответ на основе найденных чанков
        context_chunks = "\n".join(
            f"[{i+1}] {chunk.content}" for i, chunk in enumerate(chunks[:3])
        )
        answer_text = self._llm.complete(
            prompt=(
                f"На основе следующей информации из базы знаний банка:\n{context_chunks}\n\n"
                f"Ответь на вопрос клиента: \"{query}\"\n"
                f"Укажи источники информации. Не придумывай причины, которых нет в данных."
            ),
            system_prompt="Ты — банковский AI-ассистент. Отвечай на русском языке, основываясь только на предоставленных данных.",
            temperature=0.3,
        )

        citations: list[str] = []
        for chunk in chunks[:3]:
            citations.append(self._kb.get_source_citation(chunk))

        # Проверка индивидуальных условий
        contract_chunks = self._kb.search(
            "индивидуальные условия комиссия обслуживание карты",
            client.client_id,
            as_of=as_of,
            limit=3,
        )
        has_individual = any(c.category == "contract" for c in contract_chunks)

        if has_individual:
            answer_text += (
                "\n\nПримечание: по вашему индивидуальному договору могут "
                "действовать особые условия. Уточните в приложении или у сотрудника банка."
            )

        return {
            "scenario": "A",
            "status": "ok",
            "answer": answer_text,
            "sources": citations,
            "confidence": confidence,
            "as_of": as_of.isoformat(),
        }

    # ------------------------------------------------------------------
    # Scenario B: Transfer preparation
    # ------------------------------------------------------------------
    def handle_transfer_request(
        self,
        client: Client,
        query: str,
        recipient: str | None = None,
        amount: float | None = None,
        currency: str = "RUB",
        from_account: str | None = None,
    ) -> dict[str, Any]:
        """Prepare a transfer action awaiting client confirmation."""
        parameters: dict[str, Any] = {
            "recipient": recipient or "не указан",
            "amount": amount,
            "currency": currency,
            "from_account": from_account or "основной счёт",
        }

        action = self._am.prepare_action(
            client_id=client.client_id,
            action_type=ActionType.PREPARE_TRANSFER,
            parameters=parameters,
        )

        return {
            "scenario": "B",
            "status": "prepared",
            "action_id": action.action_id,
            "idempotency_key": action.idempotency_key,
            "message": (
                f"Подготовлен перевод {amount or '?'} {currency} на "
                f"{recipient or 'получателя'}. Требуется ваше подтверждение."
            ),
            "parameters": parameters,
            "requires_confirmation": True,
        }

    def confirm_transfer(self, action_id: str, client_confirmed: bool = True) -> dict[str, Any]:
        """Client confirms or rejects the prepared transfer."""
        action = self._am.confirm_action(action_id, client_confirmed)
        if not client_confirmed:
            return {
                "scenario": "B",
                "status": "cancelled",
                "message": "Перевод отменён по вашему запросу.",
            }

        executed = self._am.execute_action(action_id, success=True)
        return {
            "scenario": "B",
            "status": executed.status.value,
            "action_id": action_id,
            "message": (
                "Перевод выполнен успешно."
                if executed.status == "executed"
                else "Ошибка выполнения перевода."
            ),
            "result": executed.result,
        }

    # ------------------------------------------------------------------
    # Scenario C: Dispute operation
    # ------------------------------------------------------------------
    def handle_dispute(
        self,
        client: Client,
        query: str,
        operation_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register a dispute for duplicate/incorrect operations."""
        parameters: dict[str, Any] = {
            "operation_ids": operation_ids or [],
            "description": query,
        }

        action = self._am.prepare_action(
            client_id=client.client_id,
            action_type=ActionType.REGISTER_DISPUTE,
            parameters=parameters,
        )

        return {
            "scenario": "C",
            "status": "registered",
            "action_id": action.action_id,
            "message": (
                "Обращение о спорной операции зарегистрировано. "
                "Решение о возврате принимается банком в установленный срок. "
                "Это не гарантия возврата средств."
            ),
            "requires_human_review": True,
        }

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------
    def escalate_to_human(self, client: Client, context: str = "") -> dict[str, Any]:
        """Escalate the dialog to a human support agent with context."""
        action = self._am.prepare_action(
            client_id=client.client_id,
            action_type=ActionType.ESCALATE_TO_HUMAN,
            parameters={"context": context},
        )
        return {
            "scenario": "escalation",
            "status": "escalated",
            "action_id": action.action_id,
            "message": (
                "Вы соединены с сотрудником поддержки. "
                "История диалога и контекст переданы."
            ),
        }

    # ------------------------------------------------------------------
    # Idempotency demo
    # ------------------------------------------------------------------
    def demo_idempotency(self, client: Client) -> dict[str, Any]:
        """Show that repeating the same transfer request returns the same action."""
        first = self.handle_transfer_request(
            client, "Переведи маме 10000", recipient="Мама", amount=10000.0
        )
        second = self.handle_transfer_request(
            client, "Переведи маме 10000", recipient="Мама", amount=10000.0
        )
        return {
            "first_action_id": first["action_id"],
            "second_action_id": second["action_id"],
            "idempotent": first["action_id"] == second["action_id"],
            "idempotency_key": first["idempotency_key"],
        }