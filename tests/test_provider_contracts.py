from src.provider_contracts import ProviderResult, ProviderStatus


def test_provider_result_marks_success_and_failure() -> None:
    ok = ProviderResult.success({"daily": {"time": ["2026-09-20"]}})
    failure = ProviderResult.failure("Weather service unavailable", status=ProviderStatus.DEGRADED)

    assert ok.status == ProviderStatus.OK
    assert ok.value == {"daily": {"time": ["2026-09-20"]}}
    assert failure.status == ProviderStatus.DEGRADED
    assert failure.error == "Weather service unavailable"


def test_provider_status_is_standardized() -> None:
    assert ProviderStatus.OK.value == "ok"
    assert ProviderStatus.DEGRADED.value == "degraded"
    assert ProviderStatus.ERROR.value == "error"
