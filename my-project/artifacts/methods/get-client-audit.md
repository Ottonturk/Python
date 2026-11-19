# Оглавление

1. [Назначение](#назначение)
2. [Алгоритм работы](#алгоритм-работы)
3. [Входные атрибуты](#входные-атрибуты)
4. [Выходные атрибуты](#выходные-атрибуты)
5. [Пример запроса](#пример-запроса)
6. [Пример ответа](#пример-ответа)
7. [Коды ответа](#коды-ответа)

# Назначение

Метод возвращает неизменяемый аудит-лог всех действий AI для клиента. Требует роли security-auditor или compliance-officer.

# Алгоритм работы

1. Принять идентификатор клиента.
2. Проверить аутентификацию и права доступа (роль security-auditor или compliance-officer).
3. Получить все записи аудита для клиента из неизменяемого хранилища.
4. Вернуть записи аудита с временными метками, типами действий, результатами и исходными системами.

# Входные атрибуты

| Атрибут | Где передается | Тип данных | Описание |
|---------|---------------|------------|----------|
| client_id | path | string | Идентификатор клиента |

# Выходные атрибуты

| Атрибут | Тип данных | Описание |
|---------|------------|----------|
| entries | array[object] | Массив записей аудита |
| entries[].entry_id | string | Идентификатор записи |
| entries[].timestamp | string (date-time) | Время события |
| entries[].action_type | string | Тип действия |
| entries[].result | string | Результат действия |
| entries[].error_code | string | Код ошибки (если есть) |
| entries[].source_system | string | Исходная система (ai-assistant, core-banking-sim) |

# Пример запроса

```http
GET /clients/client-12345/audit
Authorization: Bearer <jwt-token>
```

# Пример ответа

```json
{
  "entries": [
    {
      "entry_id": "aud-000001",
      "timestamp": "2024-06-15T10:00:00Z",
      "client_id": "client-12345",
      "action_id": "act-000001",
      "action_type": "prepare_transfer",
      "result": "prepared",
      "error_code": null,
      "source_system": "ai-assistant"
    },
    {
      "entry_id": "aud-000002",
      "timestamp": "2024-06-15T10:05:00Z",
      "client_id": "client-12345",
      "action_id": "act-000001",
      "action_type": "prepare_transfer",
      "result": "executed",
      "error_code": null,
      "source_system": "core-banking-sim"
    }
  ]
}
```

# Коды ответа

- `200` — аудит-лог клиента
- `401` — не авторизован
- `403` — недостаточно прав для просмотра аудита
- `404` — клиент не найден