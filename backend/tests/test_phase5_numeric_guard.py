from backend.explainability.explanation_engine import numeric_guard


def test_numeric_guard_accepts_number_from_full_deterministic_payload():
    fact_table = [
        {
            "fact_id": "F1",
            "path": "result.current_stock",
            "value": 18,
        }
    ]

    payload = {
        "current_stock": 18,
        "scenario": {
            "service_level_pct": 100.0,
            "execution_cost": 572.5,
        },
    }

    ok, unexpected = numeric_guard(
        "Service level is 100.0% and execution cost is 572.5.",
        fact_table,
        payload,
    )

    assert ok is True
    assert unexpected == []


def test_numeric_guard_still_rejects_invented_number():
    fact_table = [
        {
            "fact_id": "F1",
            "path": "result.current_stock",
            "value": 18,
        }
    ]

    payload = {
        "current_stock": 18,
        "scenario": {
            "service_level_pct": 100.0,
            "execution_cost": 572.5,
        },
    }

    ok, unexpected = numeric_guard(
        "Execution cost is 99999.",
        fact_table,
        payload,
    )

    assert ok is False
    assert "99999" in unexpected