"""Acceptance tests for Motor A (spec §23)."""

from pypsa_col.mde.emissions import combustion_from_pj
from pypsa_col.mde.expressions import eval_expr
from pypsa_col.mde.methods import (
    activity_times_intensity,
    kwh_from_vkt,
    liters_from_vkt,
    sequential_measures,
    stock_use_intensity,
    useful_to_final,
)


def test_method_a():
    assert activity_times_intensity(100, 2) == 200


def test_method_b():
    assert useful_to_final(100, 0.5) == 200


def test_method_c():
    assert stock_use_intensity(100, 10_000, 0.1) == 100_000


def test_buses_diesel():
    assert liters_from_vkt(100, 60_000, 0.40) == 2_400_000


def test_buses_electric_grid():
    assert abs(kwh_from_vkt(100, 60_000, 1.20, 0.90) - 8_000_000) < 1e-6


def test_interactions():
    assert sequential_measures(100, [0.9, 0.8]) == 72


def test_emissions_10tj():
    # 10 TJ = 0.01 PJ; 50_000 kg/TJ would be 500 t — use diesel FE 74100
    em = combustion_from_pj("Diesel", 0.01)
    assert abs(em["CO2_fosil_t"] - 741.0) < 0.1


def test_anexo_gold_cells():
    from pypsa_col.mde.equivalence import compare_gold, function_suite

    g = compare_gold()
    assert bool(g.ok.all()), g
    s = function_suite()
    assert int(s.ok.sum()) == len(s)


def test_safe_expr():
    node = {
        "type": "multiply",
        "arguments": [
            {"type": "reference", "variable": "hogares"},
            {"type": "const", "value": 2.0},
        ],
    }
    assert eval_expr(node, {"hogares": 100}) == 200
