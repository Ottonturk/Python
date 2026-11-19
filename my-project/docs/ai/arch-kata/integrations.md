# 2.3 Интеграции

| Интеграция | Протокол | Аутентификация | Направление | Назначение |
|------------|----------|----------------|-------------|------------|
| Клиент ↔ Chat API | HTTPS / WSS | JWT (OAuth2 PKCE) | ↔ | Чат, получение ответов |
| Chat API ↔ Core Banking API | REST (gRPC) | mTLS + client cert | → | Баланс, карты, операции, реквизиты |
| Chat API → RAG Service | HTTP | Внутренний токен | → | Поиск ответов из базы знаний |
| Action Manager → Core Banking | REST | mTLS + ключ идемпотентности | → | Подготовка переводов, обращений |
| Escalation → Support System | REST | OAuth2 | → | Передача диалога сотруднику |
| Audit → SIEM | Syslog / Kafka | Сертификат | → | Аудит всех действий |

## 2.4 Sequence: сценарий А (Объяснение комиссии)

```plantuml
@startuml
autoactivate on

participant "Клиент" as Client
participant "Чат API" as ChatAPI
participant "NLU/LLM" as LLM
participant "RAG" as RAG
participant "Core Banking API" as Core
participant "История сессий" as Context

Client -> ChatAPI: «Почему списали 299 руб. за карту?»
ChatAPI -> Context: загрузить сессию + профиль клиента
Context --> ChatAPI: карты, пакеты услуг, история операций
ChatAPI -> LLM: анализ намерения (списание/комиссия)
LLM --> ChatAPI: намерение = объяснение_комиссии, нужны данные операции
ChatAPI -> Core: GET счета/карты клиента + операции за период
Core --> ChatAPI: список операций, включая списание 299 руб.
ChatAPI -> RAG: поиск условий обслуживания карты (актуальная версия)
RAG --> ChatAPI: условия тарифа, пункт о комиссии
ChatAPI -> LLM: сформулировать ответ (операция + условия + причина)
LLM --> ChatAPI: текст ответа клиенту
ChatAPI --> Client: ответ: «Это комиссия за обслуживание карты X, тариф Y, пункт Z договора»
@enduml
```

## 2.5 Sequence: сценарий Б (Перевод по разговорному запросу)

```plantuml
@startuml
autoactivate on

participant "Клиент" as Client
participant "Чат API" as ChatAPI
participant "NLU/LLM" as LLM
participant "RAG" as RAG
participant "Core Banking API" as Core
participant "Action Manager" as ActionMgr
participant "История сессий" as Context

Client -> ChatAPI: «Переведи маме 10 тысяч, как в прошлый раз»
ChatAPI -> Context: загрузить сессию, профиль, прошлые переводы
Context --> ChatAPI: предыдущий перевод получателю «Мама», реквизиты
ChatAPI -> LLM: извлечь получателя, сумму, валюту, счёт
LLM --> ChatAPI: получатель=Мама, сумма=10000, валюта=RUB, нужны реквизиты
alt реквизиты известны из прошлого перевода
  ChatAPI -> Core: GET реквизиты получателя (по истории)
  Core --> ChatAPI: реквизиты карты/счёта мамы
else реквизиты неизвестны
  ChatAPI --> Client: уточнить реквизиты получателя (номер карты/телефон)
  Client -> ChatAPI: реквизиты
end
ChatAPI -> ActionMgr: подготовить перевод (идемпотентный ключ)
ActionMgr -> Core: PREPARE перевод (без списания)
Core --> ActionMgr: параметры операции (комиссия, срок, статус)
ActionMgr --> ChatAPI: карточка операции для подтверждения
ChatAPI --> Client: показать параметры: получатель, сумма, комиссия, статус
Client -> ChatAPI: подтвердить операцию (2FA / push)
ChatAPI -> ActionMgr: подтверждение клиента + идемпотентный ключ
ActionMgr -> Core: EXECUTE перевод
Core --> ActionMgr: результат (успех / ошибка)
ActionMgr --> ChatAPI: статус операции
ChatAPI --> Client: «Перевод маме 10 000 руб. выполнен» или ошибка
@enduml
```

## 2.6 Sequence: сценарий В (Спорная операция)

```plantuml
@startuml
autoactivate on

participant "Клиент" as Client
participant "Чат API" as ChatAPI
participant "NLU/LLM" as LLM
participant "Core Banking API" as Core
participant "Action Manager" as ActionMgr
participant "Обращения (Support)" as Support
participant "История сессий" as Context

Client -> ChatAPI: «Вижу два одинаковых списания за один заказ. Верните лишнее»
ChatAPI -> Context: загрузить сессию, профиль клиента
Context --> ChatAPI: карты, операции
ChatAPI -> Core: GET операции клиента (по датам, суммам, merchants)
Core --> ChatAPI: список операций, включая возможные дубликаты
ChatAPI -> LLM: найти пары дубликатов, подтвердить с клиентом
LLM --> ChatAPI: кандидаты на дубликаты, нужна уверенность клиента
ChatAPI --> Client: «Я нашёл два похожих списания на сумму X. Это один заказ?»
Client -> ChatAPI: «Да, это один заказ. Верните лишнее»
ChatAPI -> ActionMgr: зарегистрировать обращение (спорная операция)
ActionMgr -> Core: CREATE обращение (тип: спорная операция, данные клиента, ссылки на операции)
Core --> ActionMgr: номер обращения, статус «в рассмотрении»
ActionMgr --> ChatAPI: номер обращения + ожидание решения
ChatAPI --> Client: «Обращение №12345 зарегистрировано. Решение о возврате принимается банком в течение N дней»
ChatAPI --> Client: «Это не гарантия возврата. Ожидайте уведомления»
alt клиент хочет передать сотруднику
  ChatAPI -> Support: передать контекст диалога + номер обращения
  Support --> ChatAPI: оператор подключён
  ChatAPI --> Client: «Вы соединены с сотрудником поддержки»
end
@enduml
```

## 2.7 Границы доверия и модели угроз

| Граница | Угроза | М控制 |
|---------|--------|------|
| Клиент → Chat API | Подделка запроса, перехват токена | JWT с коротким временем жизни, PKCE, HTTPS |
| Chat API → LLM | Утечка персональных данных в запрос к модели | Деидентификация (маскировка PAN, ФИО), только необходимые данные |
| LLM → Chat API | Недостоверный ответ, галлюцинации | RAG с подтверждением из источника, человеческий ревью для критичных ответов |
| Action Manager → Core | Двойное списание, несанкционированный перевод | Идемпотентность, подтверждение клиента, mTLS |
| Любой компонент → Core | Несанкционированный доступ к счетам клиента | OAuth2 scopes, проверка прав на уровне Core API |