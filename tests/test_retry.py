from src.retry import retry_call


def test_retry_call_retries_then_returns_value() -> None:
    calls = []
    delays = []

    def operation() -> str:
        calls.append(len(calls))
        if len(calls) < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = retry_call(operation, base_delay_seconds=1, sleep=delays.append, random_value=lambda: 0)

    assert result == "ok"
    assert len(calls) == 3
    assert delays == [1, 2]


def test_retry_call_raises_after_last_attempt() -> None:
    calls = []

    def operation() -> None:
        calls.append(True)
        raise RuntimeError("permanent")

    try:
        retry_call(operation, attempts=2, sleep=lambda _: None)
    except RuntimeError as error:
        assert str(error) == "permanent"
    else:
        raise AssertionError("retry_call did not raise")

    assert len(calls) == 2
