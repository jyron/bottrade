from __future__ import annotations

from bottrade import Results


def test_models_allow_forward_compatible_fields() -> None:
    results = Results.model_validate(
        {
            "final_equity": 100000,
            "return_pct": 0,
            "trade_count": 0,
            "liquidated": False,
            "future_metric": 42,
        }
    )

    assert results.model_dump()["future_metric"] == 42
