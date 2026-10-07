"""Constants for the LokaleNET integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "lokalenet"

CONF_URL = "url"

DEFAULT_URL = "https://mmsoft.com.pl/lokale.php"

# Administrators import bank statements a few times a week at most, so polling more often
# only adds logins to the portal's history without bringing anything new.
SCAN_INTERVAL = timedelta(hours=6)
