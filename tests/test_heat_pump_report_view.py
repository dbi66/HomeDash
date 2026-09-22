from src.heat_pump_report_view import render_heat_pump_report, render_heat_pump_report_page
from src.heat_pump_rendering import render_clear_heat_pump_schema, render_heat_pump_schema


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


def test_heat_pump_schema_renders_richer_visual_status_and_legend(monkeypatch) -> None:
    class Snapshot:
        model = "Vitocal 250-A"
        device_id = "abc-123"
        online = True
        features = {"data": []}

    captured = {}

    def fake_embed(markup, height):
        captured["markup"] = markup
        captured["height"] = height

    monkeypatch.setattr("src.heat_pump_rendering.render_embedded_html", fake_embed)

    render_heat_pump_schema(Snapshot())
    render_clear_heat_pump_schema(Snapshot())

    combined = "\n".join(captured["markup"] for _ in [0])
    assert "schema-legend" in combined
    assert "schema-status-pill" in combined
    assert "Betriebsstatus" in combined
    assert "Datenstand" in combined
