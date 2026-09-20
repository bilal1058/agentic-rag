"""Unit tests for core/theme.py ThemeEngine."""

from unittest.mock import patch
from core.theme import ThemeEngine, get_theme_css, inject_theme


def test_theme_engine_css_generation():
    css = get_theme_css(bg_url="data:image/png;base64,mocked_bg")
    assert isinstance(css, str)
    assert len(css) > 1000

    # Verify typography definitions
    assert "Bebas Neue" in css
    assert "Inter" in css
    assert "Space Mono" in css
    assert "@font-face" in css

    # Verify design tokens & physics motion curves
    assert "--font-sans" in css
    assert "--ease-spring" in css
    assert "--duration-normal" in css
    assert "--duration-instant" in css

    # Verify background url injection
    assert "mocked_bg" in css

    # Verify UI component classes
    assert ".chat-card" in css
    assert ".assistant-card" in css
    assert ".hero" in css


def test_theme_engine_inject_theme_safe():
    with patch("streamlit.markdown") as mock_markdown:
        inject_theme(bg_url="test_bg")
        mock_markdown.assert_called_once()
        args, kwargs = mock_markdown.call_args
        assert "<style>" in args[0]
        assert "</style>" in args[0]
        assert kwargs.get("unsafe_allow_html") is True
