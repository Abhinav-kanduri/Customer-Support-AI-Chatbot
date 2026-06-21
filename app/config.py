"""Central place to load every environment variable the app needs.

All modules should import their settings from here instead of calling
``os.environ`` directly, so there is a single source of truth and missing
variables fail loudly at startup with a clear message with configuration instructions.
"""

import logging
import os

from dotenv import load_dotenv

# Configure logging here because this module is imported before anything else
# (app.main imports it first), so the load messages below are captured.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("app.config")

# Load variables from a local .env file in development. On Railway (or any
# host that injects real environment variables) this is a harmless no-op.
if load_dotenv():
    logger.info("Loaded environment variables from .env file")
else:
    logger.info("No .env file found; using environment variables from the host")


def _mask(value: str) -> str:
    """Hide the secret part of a value so it is safe to log."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]} (len={len(value)})"


def _require(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.environ.get(name)
    if not value:
        logger.error("MISSING required environment variable: %s", name)
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in your .env file locally, or in Railway "
            f"(Shared Variables → share with the service)."
        )
    logger.info("Loaded %s = %s", name, _mask(value))
    return value


def _optional(name: str, default: str | None = None) -> str | None:
    """Return an optional environment variable, or a default if unset."""
    value = os.environ.get(name, default)
    if value:
        logger.info("Loaded %s = %s", name, _mask(value))
    else:
        logger.warning("Optional environment variable not set: %s", name)
    return value


logger.info("Loading environment configuration...")

# --- Required ---------------------------------------------------------------
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")
DATABASE_URL: str = _require("DATABASE_URL")

# --- Supabase (optional until auth is wired up) -----------------------------
SUPABASE_URL: str | None = _optional("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY: str | None = _optional("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_JWKS_URL: str | None = _optional("SUPABASE_JWKS_URL")

logger.info("Environment configuration loaded successfully")
