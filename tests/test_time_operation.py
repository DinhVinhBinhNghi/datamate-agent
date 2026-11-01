from pathlib import Path

from datamate.business.time_operation import resolve_with_evidence


def test_resolve_period_operation_has_reproducible_evidence():
    result = resolve_with_evidence(
        "tháng này", "2024-02-29", Path(__file__).resolve().parents[1] / "train" / "calendar.csv", "train"
    )
    assert result["type"] == "date_range"
    assert result["value"] == {"start": "2024-02-01", "end": "2024-02-29"}
    assert result["evidence"]["as_of_date"] == "2024-02-29"
    assert result["evidence"]["inclusive_endpoints"] is True
