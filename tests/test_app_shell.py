from src.app_shell import render_app_header


class FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.query_params = {}
        self.popover_calls = []

    def columns(self, widths):
        return [FakeColumn(), FakeColumn(), FakeColumn()]

    def markdown(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def button(self, *args, **kwargs):
        return False

    def selectbox(self, *args, **kwargs):
        return "Home"

    def popover(self, *args, **kwargs):
        self.popover_calls.append(args[0])
        class Popover:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        return Popover()

    def rerun(self):
        return None


def test_render_app_header_returns_selected_function(monkeypatch):
    import src.app_shell as app_shell_module
    fake_st = FakeStreamlit()
    monkeypatch.setattr(app_shell_module, "st", fake_st)

    def fake_get_latest_data_timestamps(database_path):
        return {"homematic": "2024-01-01T00:00:00Z", "viessmann": "2024-01-01T01:00:00Z"}

    monkeypatch.setattr(app_shell_module, "get_latest_data_timestamps", fake_get_latest_data_timestamps)

    choice = render_app_header("HomeClimate Dashboard", "example.db")

    assert choice == "Home"
    assert fake_st.session_state["navigation-last"] == "Home"
