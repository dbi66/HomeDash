from src.heat_pump_inventory_view import render_viessmann_inventory


def test_heat_pump_inventory_view_is_importable() -> None:
    assert callable(render_viessmann_inventory)
