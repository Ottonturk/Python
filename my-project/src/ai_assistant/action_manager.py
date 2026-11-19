"""Action Manager: preparation, confirmation, execution, idempotency."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import Action, ActionStatus, ActionType, AuditEntry


class ActionManager:
    """Manages the lifecycle of client actions with idempotency and audit."""

    IDEMPOTENCY_WINDOW_HOURS = 24

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}
        self._audit_log: list[AuditEntry] = []
        self._action_counter = 0
        self._audit_counter = 0

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------
    @staticmethod
    def _make_idempotency_key(
        client_id: str,
        action_type: ActionType,
        parameters: dict[str, Any],
    ) -> str:
        payload = {
            "client_id": client_id,
            "action_type": action_type.value,
            "parameters": parameters,
        }
        raw = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        bucket = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ).isoformat()
        return f"{raw[:32]}:{bucket}"

    def _find_existing_by_idempotency(
        self, client_id: str, action_type: ActionType, key: str
    ) -> Action | None:
        for action in self._actions.values():
            if (
                action.client_id == client_id
                and action.action_type == action_type
                and action.idempotency_key == key
            ):
                return action
        return None

    # ------------------------------------------------------------------
    # Core action flow
    # ------------------------------------------------------------------
    def prepare_action(
        self,
        client_id: str,
        action_type: ActionType,
        parameters: dict[str, Any],
    ) -> Action:
        """Create a pending action. Returns existing if idempotent key matches."""
        key = self._make_idempotency_key(client_id, action_type, parameters)

        existing = self._find_existing_by_idempotency(client_id, action_type, key)
        if existing is not None:
            return existing

        self._action_counter += 1
        action = Action(
            action_id=f"act-{self._action_counter:06d}",
            client_id=client_id,
            action_type=action_type,
            status=ActionStatus.PENDING,
            parameters=parameters,
            idempotency_key=key,
        )
        self._actions[action.action_id] = action
        self._audit(
            client_id=client_id,
            action_id=action.action_id,
            action_type=action_type.value,
            parameters=parameters,
            result="prepared",
            error_code=None,
            source_system="ai-assistant",
        )
        return action

    def confirm_action(self, action_id: str, client_confirmed: bool = True) -> Action:
        action = self._actions.get(action_id)
        if action is None:
            raise KeyError(f"Action {action_id} not found")
        if action.status != ActionStatus.PENDING:
            raise ValueError(f"Action {action_id} is not in PENDING state")

        action.client_confirmed = client_confirmed
        if client_confirmed:
            action.status = ActionStatus.PENDING_CONFIRMATION
            action.confirmed_at = datetime.now(timezone.utc)
        else:
            action.status = ActionStatus.CANCELLED

        action.updated_at = datetime.now(timezone.utc)
        self._audit(
            client_id=action.client_id,
            action_id=action_id,
            action_type=action.action_type.value,
            parameters=action.parameters,
            result="confirmed" if client_confirmed else "rejected",
            error_code=None,
            source_system="ai-assistant",
        )
        return action

    def execute_action(self, action_id: str, success: bool = True) -> Action:
        action = self._actions.get(action_id)
        if action is None:
            raise KeyError(f"Action {action_id} not found")
        if action.status != ActionStatus.PENDING_CONFIRMATION:
            raise ValueError(
                f"Action {action_id} is not confirmed (status={action.status})"
            )

        if success:
            action.status = ActionStatus.EXECUTED
            action.result = {
                "status": "executed",
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            action.status = ActionStatus.FAILED
            action.error = "Core Banking error: temporary failure"

        action.updated_at = datetime.now(timezone.utc)
        self._audit(
            client_id=action.client_id,
            action_id=action_id,
            action_type=action.action_type.value,
            parameters=action.parameters,
            result="executed" if success else "failed",
            error_code=None if success else "CORE_BANKING_ERROR",
            source_system="core-banking-sim",
        )
        return action

    def get_action(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    def get_actions_for_client(self, client_id: str) -> list[Action]:
        return [a for a in self._actions.values() if a.client_id == client_id]

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def _audit(
        self,
        client_id: str,
        action_id: str,
        action_type: str,
        parameters: dict[str, Any],
        result: str,
        error_code: str | None,
        source_system: str,
    ) -> None:
        self._audit_counter += 1
        entry = AuditEntry(
            entry_id=f"aud-{self._audit_counter:06d}",
            timestamp=datetime.now(timezone.utc),
            client_id=client_id,
            action_id=action_id,
            action_type=action_type,
            parameters=parameters,
            result=result,
            error_code=error_code,
            source_system=source_system,
        )
        self._audit_log.append(entry)

    def get_audit_log(self, client_id: str | None = None) -> list[AuditEntry]:
        if client_id is None:
            return list(self._audit_log)
        return [e for e in self._audit_log if e.client_id == client_id]