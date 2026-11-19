"""Unit-тесты для проверки MockLLMClient и AIEngine с моковым LLM."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ai_assistant.llm_client import MockLLMClient, create_llm_client
from ai_assistant.action_manager import ActionManager
from ai_assistant.engine import AIEngine
from ai_assistant.models import Client


class TestMockLLMClient(unittest.TestCase):
    """Тесты мокового LLM клиента."""

    def setUp(self) -> None:
        self.llm = MockLLMClient()

    def test_commission_intent(self) -> None:
        result = self.llm.complete_json("Почему списали 299 рублей за карту?")
        self.assertEqual(result.get("intent"), "explain_commission")
        self.assertGreaterEqual(result.get("confidence", 0), 0.5)

    def test_transfer_intent(self) -> None:
        result = self.llm.complete_json("Переведи маме 10 тысяч")
        self.assertEqual(result.get("intent"), "prepare_transfer")
        self.assertGreaterEqual(result.get("confidence", 0), 0.5)

    def test_dispute_intent(self) -> None:
        result = self.llm.complete_json("Вижу два одинаковых списания")
        self.assertEqual(result.get("intent"), "register_dispute")
        self.assertGreaterEqual(result.get("confidence", 0), 0.5)

    def test_escalation_intent(self) -> None:
        result = self.llm.complete_json("Соедини меня с оператором")
        self.assertEqual(result.get("intent"), "escalate_to_human")
        self.assertGreaterEqual(result.get("confidence", 0), 0.5)

    def test_unknown_intent(self) -> None:
        result = self.llm.complete_json("Привет, как дела?")
        self.assertEqual(result.get("intent"), "unknown")

    def test_complete_returns_string(self) -> None:
        result = self.llm.complete("какой-то текст")
        self.assertIsInstance(result, str)

    def test_complete_json_returns_dict(self) -> None:
        result = self.llm.complete_json("какой-то текст")
        self.assertIsInstance(result, dict)
        self.assertIn("intent", result)

    def test_create_llm_client_mock(self) -> None:
        llm = create_llm_client("mock")
        self.assertIsInstance(llm, MockLLMClient)

    def test_create_llm_client_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_llm_client("unknown_provider")


class TestAIEngineWithMock(unittest.TestCase):
    """Тесты AIEngine с моковым LLM."""

    def setUp(self) -> None:
        self.am = ActionManager()
        self.engine = AIEngine(self.am, llm_provider="mock")
        self.client = Client(
            client_id="client-12345",
            name="Тестовый Клиент",
            cards=[
                {"masked": "****1234", "type": "Классическая", "package": "Стандарт"},
            ],
            service_packages=["Стандарт"],
            accounts=[
                {"account_id": "acc-001", "currency": "RUB", "balance": 75000.0},
            ],
        )

    def test_commission_scenario(self) -> None:
        result = self.engine.handle_commission_query(
            self.client,
            "Почему списали 299 рублей за обслуживание карты?",
        )
        self.assertEqual(result["scenario"], "A")
        self.assertIn("status", result)
        self.assertIn("answer", result)

    def test_transfer_prepare_and_confirm(self) -> None:
        prepared = self.engine.handle_transfer_request(
            self.client,
            "Переведи маме 10000",
            recipient="Мама",
            amount=10000.0,
            currency="RUB",
        )
        self.assertEqual(prepared["status"], "prepared")
        self.assertTrue(prepared["requires_confirmation"])
        self.assertIsNotNone(prepared["action_id"])
        self.assertIsNotNone(prepared["idempotency_key"])

        confirmed = self.engine.confirm_transfer(
            prepared["action_id"], client_confirmed=True
        )
        self.assertEqual(confirmed["status"], "executed")

    def test_transfer_reject(self) -> None:
        prepared = self.engine.handle_transfer_request(
            self.client,
            "Переведи маме 10000",
            recipient="Мама",
            amount=10000.0,
            currency="RUB",
        )
        rejected = self.engine.confirm_transfer(
            prepared["action_id"], client_confirmed=False
        )
        self.assertEqual(rejected["status"], "cancelled")

    def test_dispute_scenario(self) -> None:
        result = self.engine.handle_dispute(
            self.client,
            "Вижу два одинаковых списания за один заказ",
            operation_ids=["op-001", "op-002"],
        )
        self.assertEqual(result["scenario"], "C")
        self.assertEqual(result["status"], "registered")
        self.assertTrue(result["requires_human_review"])
        self.assertIsNotNone(result["action_id"])

    def test_escalation_scenario(self) -> None:
        result = self.engine.escalate_to_human(
            self.client, context="Клиент спрашивает о дублирующем списании"
        )
        self.assertEqual(result["scenario"], "escalation")
        self.assertEqual(result["status"], "escalated")
        self.assertIsNotNone(result["action_id"])

    def test_idempotency(self) -> None:
        first = self.engine.handle_transfer_request(
            self.client,
            "Переведи маме 10000",
            recipient="Мама",
            amount=10000.0,
            currency="RUB",
        )
        second = self.engine.handle_transfer_request(
            self.client,
            "Переведи маме 10000",
            recipient="Мама",
            amount=10000.0,
            currency="RUB",
        )
        self.assertEqual(first["action_id"], second["action_id"])
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_audit_log_records_actions(self) -> None:
        self.engine.handle_transfer_request(
            self.client,
            "Переведи маме 10000",
            recipient="Мама",
            amount=10000.0,
            currency="RUB",
        )
        audit = self.am.get_audit_log(self.client.client_id)
        self.assertGreaterEqual(len(audit), 1)
        self.assertEqual(audit[0].client_id, self.client.client_id)
        self.assertIsNotNone(audit[0].action_id)


if __name__ == "__main__":
    unittest.main()