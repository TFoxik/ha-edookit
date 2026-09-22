from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def mock_http_session() -> Iterator[MagicMock]:
    http = MagicMock()
    with (
        patch("custom_components.edookit.get_http_session", return_value=http),
        patch("custom_components.edookit.config_flow.get_http_session", return_value=http),
    ):
        yield http
