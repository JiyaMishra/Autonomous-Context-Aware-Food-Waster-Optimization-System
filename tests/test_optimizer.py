import pytest
from backend.app.optimizer import optimize_batches


def test_rounds_to_full_batch_with_buffer():
    result = optimize_batches(101, batch_size=25, minimum_buffer_pct=0.05)
    assert result["batches"] == 5
    assert result["recommended_portions"] == 125
    assert result["expected_buffer_portions"] == 24


def test_zero_forecast_requires_no_batches():
    assert optimize_batches(0)["batches"] == 0


@pytest.mark.parametrize("args", [(-1, 25, .05), (10, 0, .05), (10, 25, .8)])
def test_invalid_optimizer_inputs(args):
    with pytest.raises(ValueError):
        optimize_batches(*args)
