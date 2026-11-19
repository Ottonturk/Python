"""MVP entry point — demonstrates all three scenarios with LLM integration."""

from __future__ import annotations

from datetime import datetime

from ai_assistant.action_manager import ActionManager
from ai_assistant.engine import AIEngine
from ai_assistant.llm_client import create_llm_client
from ai_assistant.models import Client


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_llm_info(engine: AIEngine) -> None:
    provider = type(engine._llm).__name__
    print(f"\n  LLM провайдер: {provider}")


def run_commission_scenario(engine: AIEngine, client: Client) -> None:
    print_section("Сценарий А: Объяснение комиссии (с LLM)")
    result_a = engine.handle_commission_query(
        client,
        "Почему в этом месяце списали 299 рублей за обслуживание карты?",
        as_of=datetime(2024, 6, 15),
    )
    print(f"Статус: {result_a['status']}")
    print(f"Намерение: {result_a.get('detected_intent', 'N/A')}")
    print(f"Уверенность: {result_a.get('confidence', 0.0)}")
    print(f"Ответ: {result_a['answer']}")
    print(f"Источники: {result_a['sources']}")


def run_transfer_scenario(engine: AIEngine, client: Client) -> None:
    print_section("Сценарий Б: Перевод по разговорному запросу")
    result_b = engine.handle_transfer_request(
        client,
        "Переведи маме 10 тысяч, как в прошлый раз",
        recipient="Мама",
        amount=10000.0,
        currency="RUB",
    )
    print(f"Статус: {result_b['status']}")
    print(f"Сообщение: {result_b['message']}")
    print(f"ID действия: {result_b['action_id']}")
    print(f"Ключ идемпотентности: {result_b['idempotency_key']}")

    print("\n  --> Клиент подтверждает перевод (2FA / push)...")
    result_b_conf = engine.confirm_transfer(result_b["action_id"], client_confirmed=True)
    print(f"Статус после подтверждения: {result_b_conf['status']}")
    print(f"Сообщение: {result_b_conf['message']}")


def run_dispute_scenario(engine: AIEngine, client: Client) -> None:
    print_section("Сценарий В: Спорная операция (duplicate списание)")
    result_c = engine.handle_dispute(
        client,
        "Вижу два одинаковых списания за один заказ. Верните лишнее.",
        operation_ids=["op-001", "op-002"],
    )
    print(f"Статус: {result_c['status']}")
    print(f"Сообщение: {result_c['message']}")
    print(f"Требует проверки человеком: {result_c['requires_human_review']}")


def run_idempotency_demo(engine: AIEngine, client: Client) -> None:
    print_section("Демо идемпотентности (повторный запрос перевода)")
    idem = engine.demo_idempotency(client)
    print(f"Первый ID действия:  {idem['first_action_id']}")
    print(f"Второй ID действия:  {idem['second_action_id']}")
    print(f"Идемпотентно:        {idem['idempotent']}")
    print(f"Ключ идемпотентности: {idem['idempotency_key']}")


def run_escalation_scenario(engine: AIEngine, client: Client) -> None:
    print_section("Передача сотруднику поддержки")
    result_esc = engine.escalate_to_human(
        client, context="Клиент спрашивает о дублирующем списании, операция act-000003"
    )
    print(f"Статус: {result_esc['status']}")
    print(f"Сообщение: {result_esc['message']}")


def print_audit_log(am: ActionManager, client: Client) -> None:
    print_section("Аудит-лог действий клиента client-12345")
    audit = am.get_audit_log(client.client_id)
    for entry in audit:
        print(
            f"  [{entry.timestamp.strftime('%H:%M:%S')}] "
            f"{entry.action_type} -> {entry.result} "
            f"(source: {entry.source_system})"
        )


def main() -> None:
    am = ActionManager()

    # Демонстрация с mock LLM (по умолчанию, не требует API ключа)
    print("\n=== Запуск с MOCK LLM (без API ключа) ===")
    engine = AIEngine(am, llm_provider="mock")
    print_llm_info(engine)

    # Demo client с индивидуальным договором
    client = Client(
        client_id="client-12345",
        name="Иван Иванов",
        cards=[
            {"masked": "****1234", "type": "Классическая", "package": "Стандарт"},
        ],
        service_packages=["Стандарт"],
        accounts=[
            {"account_id": "acc-001", "currency": "RUB", "balance": 75000.0},
        ],
    )

    run_commission_scenario(engine, client)
    run_transfer_scenario(engine, client)
    run_dispute_scenario(engine, client)
    run_idempotency_demo(engine, client)
    run_escalation_scenario(engine, client)
    print_audit_log(am, client)

    # Демонстрация переключения на OpenAI (если есть API ключ)
    print_section("Настройка для реального LLM (OpenAI)")
    print(
        "Для использования реального LLM установите переменную окружения "
        "OPENAI_API_KEY и запустите:\n"
        "  engine = AIEngine(am, llm_provider=\"openai\", model=\"gpt-3.5-turbo\")\n"
        "Или используйте совместимый API (vLLM, Llama.cpp):\n"
        "  engine = AIEngine(\n"
        "      am, llm_provider=\"openai\",\n"
        "      base_url=\"http://localhost:8000/v1\",\n"
        "      api_key=\"dummy\",\n"
        "      model=\"your-model\"\n"
        "  )"
    )

    print("\nMVP демонстрация завершена.")


if __name__ == "__main__":
    main()