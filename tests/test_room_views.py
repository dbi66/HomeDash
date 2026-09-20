import src.room_views as room_views_module


class FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.query_params = {}

    def container(self, **kwargs):
        return self

    def selectbox(self, *args, **kwargs):
        options = args[1] if len(args) > 1 else kwargs.get("options", [])
        index = kwargs.get("index", 0)
        return options[index] if options else None

    def button(self, *args, **kwargs):
        return False

    def markdown(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def rerun(self):
        return None

    def write(self, *args, **kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_render_room_detail_view_uses_selected_room(monkeypatch):
    fake_st = FakeStreamlit()
    monkeypatch.setattr(room_views_module, "st", fake_st)

    calls = {}

    def fake_render_history(room_name, database_path):
        calls["history_room"] = room_name

    def fake_render_valve_status_table(rows):
        calls["valve_rows"] = rows

    monkeypatch.setattr(room_views_module, "render_history", fake_render_history)
    monkeypatch.setattr(room_views_module, "render_valve_status_table", fake_render_valve_status_table)
    monkeypatch.setattr(room_views_module, "get_room_events", lambda database_path, room_name: [{"recorded_at": "now", "message": "event"}])

    readings = [{
        "room_name": "Kitchen",
        "current_temperature": 20.5,
        "target_temperature": 21.0,
        "humidity": 43,
        "valve_position": 18,
        "recorded_at": "2024-01-01T00:00:00Z",
    }]

    room_views_module.render_room_detail_view(readings, ["Kitchen"], "Kitchen", "fake.db")

    assert calls["history_room"] == "Kitchen"
    assert calls["valve_rows"][0]["room_name"] == "Kitchen"
