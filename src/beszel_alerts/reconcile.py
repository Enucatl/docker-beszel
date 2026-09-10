"""Reconcile Beszel alert records with a checked-in YAML definition."""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml


SUPPORTED_ALERTS = {
    "CPU",
    "ContainerHealth",
    "Disk",
    "Memory",
    "Status",
    "Temperature",
}


class ReconcileError(RuntimeError):
    """Raised when the definition cannot be safely reconciled."""


@dataclass(frozen=True)
class AlertDefinition:
    """One desired Beszel alert."""

    system: str
    name: str
    threshold: int | float
    minutes: int


@dataclass(frozen=True)
class Definition:
    """Validated alert configuration."""

    user: str
    systems: dict[str, tuple[AlertDefinition, ...]]


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReconcileError(f"{context} must be a mapping")
    return value


def _parse_threshold(value: Any, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReconcileError(f"{context}.threshold must be a number")
    if not math.isfinite(float(value)):
        raise ReconcileError(f"{context}.threshold must be finite")
    return value


def _parse_minutes(value: Any, context: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > 255
    ):
        raise ReconcileError(f"{context}.minutes must be an integer from 1 to 255")
    return value


def load_definition(path: Path) -> Definition:
    """Load and validate an alert definition."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ReconcileError(f"cannot read {path}: {exc}") from exc

    document = _require_mapping(raw, "root")
    user = document.get("user")
    if not isinstance(user, str) or not user.strip():
        raise ReconcileError("root.user must be a non-empty string")

    raw_systems = _require_mapping(document.get("systems"), "root.systems")
    systems: dict[str, tuple[AlertDefinition, ...]] = {}
    for system_name, raw_alerts in raw_systems.items():
        if not isinstance(system_name, str) or not system_name.strip():
            raise ReconcileError("system names must be non-empty strings")
        alerts = _require_mapping(raw_alerts, f"systems.{system_name}")
        parsed: list[AlertDefinition] = []
        for alert_name, raw_alert in alerts.items():
            context = f"systems.{system_name}.{alert_name}"
            if alert_name not in SUPPORTED_ALERTS:
                supported = ", ".join(sorted(SUPPORTED_ALERTS))
                raise ReconcileError(
                    f"{context} is unsupported; supported alerts: {supported}"
                )
            alert = _require_mapping(raw_alert, context)
            if set(alert) != {"threshold", "minutes"}:
                raise ReconcileError(
                    f"{context} must contain only threshold and minutes"
                )
            parsed.append(
                AlertDefinition(
                    system=system_name,
                    name=alert_name,
                    threshold=_parse_threshold(alert["threshold"], context),
                    minutes=_parse_minutes(alert["minutes"], context),
                )
            )
        systems[system_name] = tuple(parsed)

    return Definition(user=user, systems=systems)


class BeszelAPI:
    """Small PocketBase REST client used by the one-shot job."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = ""

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = self.token
        request = Request(
            self.base_url + path, data=body, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=15) as response:
                response_body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ReconcileError(
                f"Beszel API {method} {path} returned {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise ReconcileError(f"cannot reach Beszel API: {exc.reason}") from exc

        if not response_body:
            return None
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise ReconcileError(
                f"Beszel API returned invalid JSON for {method} {path}"
            ) from exc

    def authenticate(self, identity: str, password: str) -> None:
        result = self.request(
            "POST",
            "/api/collections/_superusers/auth-with-password",
            {"identity": identity, "password": password},
        )
        token = result.get("token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            raise ReconcileError("Beszel API authentication returned no token")
        self.token = token

    def list_records(
        self, collection: str, filter_expression: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, str] = {"page": "1", "perPage": "500"}
        if filter_expression:
            query["filter"] = filter_expression
        result = self.request(
            "GET", f"/api/collections/{collection}/records?{urlencode(query)}"
        )
        items = result.get("items") if isinstance(result, dict) else None
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            raise ReconcileError(f"Beszel API returned invalid {collection} records")
        return items

    def create_alert(
        self, user_id: str, system_id: str, alert: AlertDefinition
    ) -> None:
        self.request(
            "POST",
            "/api/collections/alerts/records",
            {
                "user": user_id,
                "system": system_id,
                "name": alert.name,
                "value": alert.threshold,
                "min": alert.minutes,
            },
        )

    def update_alert(self, alert_id: str, alert: AlertDefinition) -> None:
        self.request(
            "PATCH",
            f"/api/collections/alerts/records/{alert_id}",
            {"value": alert.threshold, "min": alert.minutes},
        )

    def delete_alert(self, alert_id: str) -> None:
        self.request("DELETE", f"/api/collections/alerts/records/{alert_id}")


def _quote_filter(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def reconcile(definition: Definition, api: BeszelAPI) -> tuple[int, int, int]:
    """Apply exact alert state and return created, updated, deleted counts."""
    users = api.list_records("users")
    matching_users = [
        record for record in users if record.get("email") == definition.user
    ]
    if len(matching_users) != 1:
        raise ReconcileError(
            f"expected one Beszel user {definition.user!r}, found {len(matching_users)}"
        )
    user_id = matching_users[0].get("id")
    if not isinstance(user_id, str) or not user_id:
        raise ReconcileError(f"Beszel user {definition.user!r} has no id")

    systems = api.list_records("systems")
    system_ids: dict[str, str] = {}
    for system_name in definition.systems:
        matches = [record for record in systems if record.get("name") == system_name]
        if len(matches) != 1:
            raise ReconcileError(
                f"expected one Beszel system {system_name!r}, found {len(matches)}"
            )
        system_id = matches[0].get("id")
        if not isinstance(system_id, str) or not system_id:
            raise ReconcileError(f"Beszel system {system_name!r} has no id")
        system_ids[system_name] = system_id

    existing = api.list_records("alerts", f"user = {_quote_filter(user_id)}")
    existing_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in existing:
        system_id = record.get("system")
        name = record.get("name")
        if isinstance(system_id, str) and isinstance(name, str):
            key = (system_id, name)
            if key in existing_by_key:
                raise ReconcileError(
                    f"duplicate existing alert for system {system_id!r}, name {name!r}"
                )
            existing_by_key[key] = record

    desired_keys: set[tuple[str, str]] = set()
    created = updated = deleted = 0
    for system_name, alerts in definition.systems.items():
        system_id = system_ids[system_name]
        for alert in alerts:
            key = (system_id, alert.name)
            desired_keys.add(key)
            current = existing_by_key.get(key)
            if current is None:
                api.create_alert(user_id, system_id, alert)
                created += 1
                continue
            if (
                current.get("value") != alert.threshold
                or current.get("min") != alert.minutes
            ):
                alert_id = current.get("id")
                if not isinstance(alert_id, str) or not alert_id:
                    raise ReconcileError(
                        f"existing {system_name} {alert.name} alert has no id"
                    )
                api.update_alert(alert_id, alert)
                updated += 1

    managed_system_ids = set(system_ids.values())
    for key, record in existing_by_key.items():
        if key[0] in managed_system_ids and key not in desired_keys:
            alert_id = record.get("id")
            if not isinstance(alert_id, str) or not alert_id:
                raise ReconcileError("existing alert selected for deletion has no id")
            api.delete_alert(alert_id)
            deleted += 1

    return created, updated, deleted


def main() -> int:
    config_path = Path(os.environ.get("ALERTS_CONFIG", "/app/alerts.yml"))
    base_url = os.environ.get("BESZEL_URL", "http://beszel:8090")
    identity = os.environ.get("BESZEL_ADMIN_EMAIL", "admin@docker.home.arpa")
    password_file = Path(
        os.environ.get(
            "BESZEL_ADMIN_PASSWORD_FILE", "/run/secrets/beszel_admin_password"
        )
    )

    try:
        definition = load_definition(config_path)
        password = password_file.read_text(encoding="utf-8").strip()
        if not password:
            raise ReconcileError(f"{password_file} is empty")
        api = BeszelAPI(base_url)
        api.authenticate(identity, password)
        created, updated, deleted = reconcile(definition, api)
    except (OSError, ReconcileError) as exc:
        print(f"beszel alert reconciliation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"beszel alerts reconciled: created={created} updated={updated} deleted={deleted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
