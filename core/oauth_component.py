"""Custom Streamlit Component to bridge OAuth tokens to Python without iframe sandbox restrictions."""

from pathlib import Path
from typing import Any
import streamlit.components.v1 as components

_COMPONENT_PATH = Path(__file__).resolve().parent.parent / "components" / "oauth_bridge"
_oauth_bridge_func = components.declare_component("oauth_bridge", path=str(_COMPONENT_PATH))


def oauth_bridge(logout: bool = False, key: str = "oauth_token_bridge") -> str | None:
    """Read OAuth token from parent window hash or localStorage via Streamlit's native postMessage channel.

    Returns:
        Token string if authenticated, otherwise None.
    """
    try:
        val = _oauth_bridge_func(logout=logout, default=None, key=key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    return None
