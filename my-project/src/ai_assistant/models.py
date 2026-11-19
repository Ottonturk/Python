"""Data models for the AI assistant MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ActionStatus(str, Enum):
    PENDING = "pending"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"


class ActionType(str, Enum):
    EXPLAIN_COMMISSION = "explain_commission"
    PREPARE_TRANSFER = "prepare_transfer"
    EXECUTE_TRANSFER = "execute_transfer"
    REGISTER_DISPUTE = "register_dispute"
    ESCALATE_TO_HUMAN = "escalate_to_human"


@dataclass
class Client:
    client_id: str
    name: str
    cards: list[dict] = field(default_factory=list)
    service_packages: list[str] = field(default_factory=list)
    accounts: list[dict] = field(default_factory=list)


@dataclass
class Operation:
    operation_id: str
    client_id: str
    amount: float
    currency: str
    merchant: str | None
    status: str
    timestamp: datetime
    card_masked: str | None = None


@dataclass
class Action:
    action_id: str
    client_id: str
    action_type: ActionType
    status: ActionStatus
    parameters: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    client_confirmed: bool = False
    confirmed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AuditEntry:
    entry_id: str
    timestamp: datetime
    client_id: str
    action_id: str
    action_type: str
    parameters: dict[str, Any]
    result: str
    error_code: str | None
    source_system: str