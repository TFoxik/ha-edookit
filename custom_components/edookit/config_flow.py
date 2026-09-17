from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pyedookit import AuthError, Session
from pyedookit import login as edookit_login

from .const import CONF_SCHOOL, CONF_SESSION, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class EdookitConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _try_login(
        self, school: str, user_input: dict[str, Any], errors: dict[str, str]
    ) -> Session | None:
        try:
            return await edookit_login(school, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        except AuthError:
            errors["base"] = "invalid_auth"
            return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            school = user_input[CONF_SCHOOL].strip().lower()
            await self.async_set_unique_id(f"{school}:{user_input[CONF_USERNAME].strip().lower()}")
            self._abort_if_unique_id_configured()

            session = await self._try_login(school, user_input, errors)
            if session is not None:
                return self.async_create_entry(
                    title=school,
                    data={CONF_SCHOOL: school, CONF_SESSION: session.to_json()},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        reauth_entry = self._get_reauth_entry()
        school = reauth_entry.data[CONF_SCHOOL]
        errors: dict[str, str] = {}
        if user_input is not None:
            session = await self._try_login(school, user_input, errors)
            if session is not None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_SESSION: session.to_json()},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"school": school},
        )
