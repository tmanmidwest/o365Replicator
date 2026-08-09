"""Environment-driven bootstrap settings.

These seed the initial runtime configuration on first launch. Once the app has
run, live settings are read from (and edited in) the database via the web UI, so
these values only matter for the very first boot and for CI defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:////data/o365replicator.db"

    default_email_format: str = "first.last"
    default_email_custom_pattern: str = "{f}{last}"
    default_domain: str = "demo365.local"

    # Legacy/static API key still accepted via X-API-Key alongside managed keys.
    api_key: str = ""

    # --- UI auth ---
    # Optional bootstrap admin. If both are set and no admin exists, one is created
    # on startup. If left blank, the first visit shows a one-time setup screen.
    admin_username: str = ""
    admin_password: str = ""
    session_ttl_hours: int = 12
    # Controls the session cookie's Secure flag:
    #   "auto" (default) -> Secure only when the request arrived over https (via the
    #                       tunnel's X-Forwarded-Proto). Works over both the https
    #                       tunnel AND direct-http testing with no config change.
    #   "true" / "false" -> force it on/off.
    cookie_secure: str = "auto"

    # --- OAuth2 ---
    oauth_token_ttl_seconds: int = 3600

    callback_enabled: bool = False
    callback_url: str = ""
    callback_method: str = "POST"
    callback_auth_header_name: str = ""
    callback_auth_header_value: str = ""


settings = Settings()
