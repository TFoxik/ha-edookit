from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyedookit import Grades, Payments

from custom_components.edookit.const import CAPTURE_ENV

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_dev_page_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    # A shell that exported the dev switch must not turn capture on in tests.
    monkeypatch.setenv(CAPTURE_ENV, "0")


@pytest.fixture(autouse=True)
def mock_http_session() -> Iterator[MagicMock]:
    http = MagicMock()
    with (
        patch("custom_components.edookit.async_create_clientsession", return_value=http),
        patch(
            "custom_components.edookit.config_flow.async_create_clientsession",
            return_value=http,
        ),
    ):
        yield http


NO_PAYMENTS = Payments(
    paid=Decimal(0), remaining=Decimal(0), overpaid=Decimal(0), currency="CZK", requests=[]
)


@pytest.fixture(autouse=True)
def mock_school_pages() -> Iterator[None]:
    with (
        patch("pyedookit.client.EdookitClient.get_events", new=AsyncMock(return_value=[])),
        patch(
            "pyedookit.client.EdookitClient.get_payments",
            new=AsyncMock(return_value=NO_PAYMENTS),
        ),
        patch("pyedookit.client.EdookitClient.get_inbox", new=AsyncMock(return_value=[])),
        patch(
            "pyedookit.client.EdookitClient.get_grades",
            new=AsyncMock(return_value=Grades(None, [], [])),
        ),
    ):
        yield
