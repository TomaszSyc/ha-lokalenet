"""Config flow for the LokaleNET integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import create_client
from .api import LokaleNetAuthError, LokaleNetConnectionError
from .const import CONF_URL, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def normalise_url(url: str) -> str:
    """The portal address in one form; raises ValueError if it cannot be used."""
    url = url.strip()
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    if parts.scheme != "https":
        # Over plain HTTP the password would travel unencrypted on every refresh.
        raise ValueError("insecure_url")
    if (
        not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("invalid_url")
    host = parts.hostname.lower() + (f":{parts.port}" if parts.port else "")
    return f"https://{host}{parts.path or '/'}"


def account_id(url: str, username: str) -> str:
    return f"{urlsplit(url).netloc}:{username.lower()}"


_ACCOUNT = vol.Schema(
    {
        vol.Required(CONF_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): _PASSWORD,
    }
)


class LokaleNetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LokaleNET."""

    VERSION = 1

    async def _check(self, url: str, username: str, password: str) -> str | None:
        client = create_client(self.hass, url, username, password)
        try:
            await client.validate()
        except LokaleNetAuthError:
            return "invalid_auth"
        except LokaleNetConnectionError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while checking the login")
            return "unknown"
        return None

    def _account_form(
        self, step_id: str, user_input: Mapping[str, Any], errors: dict[str, str]
    ) -> ConfigFlowResult:
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(_ACCOUNT, user_input),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            try:
                url = normalise_url(user_input[CONF_URL])
            except ValueError as err:
                errors[CONF_URL] = str(err)
            else:
                await self.async_set_unique_id(account_id(url, username))
                self._abort_if_unique_id_configured()
                if not (
                    error := await self._check(url, username, user_input[CONF_PASSWORD])
                ):
                    return self.async_create_entry(
                        title=username,
                        data={
                            CONF_URL: url,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                errors["base"] = error
        return self._account_form("user", user_input or {}, errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A new portal address or identifier for an account already set up."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            try:
                url = normalise_url(user_input[CONF_URL])
            except ValueError as err:
                errors[CONF_URL] = str(err)
            else:
                new_id = account_id(url, username)
                if (
                    new_id != entry.unique_id
                    and self.hass.config_entries.async_entry_for_domain_unique_id(
                        DOMAIN, new_id
                    )
                ):
                    errors["base"] = "already_configured"
                elif not (
                    error := await self._check(url, username, user_input[CONF_PASSWORD])
                ):
                    await self._move_entities(entry.entry_id, entry.unique_id, new_id)
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=new_id,
                        title=username,
                        data_updates={
                            CONF_URL: url,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                else:
                    errors["base"] = error
        defaults = user_input or {
            CONF_URL: entry.data[CONF_URL],
            CONF_USERNAME: entry.data[CONF_USERNAME],
        }
        return self._account_form("reconfigure", defaults, errors)

    async def _move_entities(self, entry_id: str, old_id: str, new_id: str) -> None:
        """Carry the entities over to the new account id, so their ids stay the same.

        Entity unique ids start with the account id; without this, the reload would
        create a second set of entities with a numeric suffix and orphan the first.
        """
        if old_id == new_id:
            return
        prefix = f"{old_id}_"

        def move(entity: er.RegistryEntry) -> dict[str, Any] | None:
            if not entity.unique_id.startswith(prefix):
                return None
            return {"new_unique_id": f"{new_id}_{entity.unique_id[len(prefix) :]}"}

        await er.async_migrate_entries(self.hass, entry_id, move)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._check(
                entry.data[CONF_URL],
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not error:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD}),
            description_placeholders={CONF_USERNAME: entry.data[CONF_USERNAME]},
            errors=errors,
        )
