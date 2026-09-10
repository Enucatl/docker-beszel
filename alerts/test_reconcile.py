from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alerts.reconcile import (
    AlertDefinition,
    BeszelAPI,
    Definition,
    ReconcileError,
    load_definition,
    reconcile,
)


ROOT = Path(__file__).parents[1]


class FakeAPI:
    def __init__(self) -> None:
        self.records = {
            "users": [{"id": "user1", "email": "user@home.arpa"}],
            "systems": [{"id": "system1", "name": "proxmox-cortex.home.arpa"}],
            "alerts": [
                {
                    "id": "temperature1",
                    "user": "user1",
                    "system": "system1",
                    "name": "Temperature",
                    "value": 70,
                    "min": 5,
                    "triggered": False,
                },
                {
                    "id": "obsolete1",
                    "user": "user1",
                    "system": "system1",
                    "name": "CPU",
                    "value": 90,
                    "min": 10,
                },
            ],
        }
        self.calls: list[tuple[str, str, dict | None]] = []

    def list_records(self, collection: str, _filter: str | None = None) -> list[dict]:
        return [record.copy() for record in self.records[collection]]

    def create_alert(
        self, user_id: str, system_id: str, alert: AlertDefinition
    ) -> None:
        self.calls.append(
            ("create", alert.name, {"value": alert.threshold, "min": alert.minutes})
        )

    def update_alert(self, alert_id: str, alert: AlertDefinition) -> None:
        self.calls.append(
            ("update", alert_id, {"value": alert.threshold, "min": alert.minutes})
        )

    def delete_alert(self, alert_id: str) -> None:
        self.calls.append(("delete", alert_id, None))


def test_load_definition_matches_tracked_alerts() -> None:
    definition = load_definition(ROOT / "alerts.yml")

    assert definition.user == "user@home.arpa"
    assert definition.systems["proxmox-cortex.home.arpa"][-1] == AlertDefinition(
        "proxmox-cortex.home.arpa", "Temperature", 80, 5
    )


def test_invalid_alert_name_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "alerts.yml"
    path.write_text(
        "user: user@home.arpa\nsystems: {host: {Unknown: {threshold: 1, minutes: 1}}}\n"
    )

    with pytest.raises(ReconcileError, match="unsupported"):
        load_definition(path)


def test_reconcile_updates_and_removes_exact_state() -> None:
    api = FakeAPI()
    definition = Definition(
        user="user@home.arpa",
        systems={
            "proxmox-cortex.home.arpa": (
                AlertDefinition("proxmox-cortex.home.arpa", "Temperature", 80, 5),
            )
        },
    )

    assert reconcile(definition, api) == (0, 1, 1)
    assert api.calls == [
        ("update", "temperature1", {"value": 80, "min": 5}),
        ("delete", "obsolete1", None),
    ]


def test_reconcile_fails_before_mutating_unknown_system() -> None:
    api = FakeAPI()
    definition = Definition(user="user@home.arpa", systems={"missing.home.arpa": ()})

    with pytest.raises(ReconcileError, match="missing.home.arpa"):
        reconcile(definition, api)
    assert api.calls == []


def test_api_request_sends_auth_token() -> None:
    api = BeszelAPI("http://beszel")
    api.token = "token-value"
    response = MagicMock()
    response.read.return_value = b"{}"
    response.__enter__.return_value = response

    with patch("alerts.reconcile.urlopen", return_value=response) as urlopen:
        api.request("GET", "/api/test")

    request = urlopen.call_args.args[0]
    assert request.get_header("Authorization") == "token-value"
