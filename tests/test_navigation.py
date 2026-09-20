from src.navigation import PAGES, apply_navigation


class QueryParams(dict):
    def clear(self):
        super().clear()

    def update(self, values):
        super().update(values)


def test_navigation_pages_are_complete() -> None:
    assert PAGES == ("Home", "Raumdetail", "Raumbericht", "Alle Diagramme", "Wärmepumpe", "Wetter", "Einstellungen")


def test_navigation_updates_session_and_query_state() -> None:
    session = {"selected_room": "Bad oben"}
    query = QueryParams()

    state = apply_navigation("Raumdetail", session, query)

    assert state.room == "Bad oben"
    assert session["view"] == "detail"
    assert query == {"room": "Bad oben", "view": "detail"}
