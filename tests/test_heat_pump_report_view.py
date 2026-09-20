from src.heat_pump_report_view import render_heat_pump_report, render_heat_pump_report_page


def test_heat_pump_report_page_delegates_to_renderer() -> None:
    calls = []

    def renderer(snapshot, history):
        calls.append((snapshot, history))

    snapshot = object()
    history = [{"recorded_at": "now"}]
    render_heat_pump_report_page(snapshot, history, renderer)

    assert calls == [(snapshot, history)]


def test_heat_pump_report_renderer_uses_snapshot_sections() -> None:
    class Snapshot:
        model = "Test HP"
        device_id = "abc-123"
        online = True
        features = {"data": []}

    assert callable(render_heat_pump_report)
    assert render_heat_pump_report(Snapshot(), []) is None
