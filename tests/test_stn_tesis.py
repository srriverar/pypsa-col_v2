"""El Modelo STN + 18-subarea reconstruction from the published tesis extract."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def stn():
    pytest.importorskip("pypsa")
    from pypsa_col.stn_tesis import build_stn_physical

    return build_stn_physical(ROOT)


@pytest.fixture(scope="module")
def clustered(stn):
    from pypsa_col.stn_tesis import build_clustered18

    return build_clustered18(ROOT, stn)


def test_stn_is_voltage_split_not_proyecto_base(stn):
    assert len(stn.buses) >= 140
    assert len(stn.lines) >= 180
    assert len(stn.transformers) >= 15
    assert set(stn.buses.v_nom.unique()) <= {220.0, 230.0, 500.0}
    assert (stn.buses.v_nom == 500.0).sum() >= 10
    # r,x must be ohm, not Ω/km (the dumped nc stored per-km by mistake)
    assert float(stn.lines.x.median()) > 1.0
    assert "subarea" in stn.buses.columns
    assert stn.buses["subarea"].nunique() == 18


def test_clustered_has_eighteen_subareas(clustered):
    assert len(clustered.buses) == 18
    assert len(clustered.links) >= 20
    assert (clustered.links.p_min_pu == -1).all()
    gens = clustered.generators[clustered.generators.carrier != "load shedding"]
    assert gens.p_nom.sum() > 5_000


def test_gui_exposes_three_required_models():
    from pypsa_col.gui_core import NETWORKS

    assert "stn-tesis" in NETWORKS
    assert "clustered-18" in NETWORKS
    assert "dashboard-sin" in NETWORKS
    labels = " ".join(v["label"] for v in NETWORKS.values())
    assert "El Modelo STN" in labels
    assert "18 subáreas" in labels
    assert "7 nodos" in labels
