from src.settings_view import render_settings_dialog


def test_settings_view_is_importable() -> None:
    assert callable(render_settings_dialog)
