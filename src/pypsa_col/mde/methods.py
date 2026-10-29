"""Four calculation methods (LEAP-equivalent primitives). No eval()."""

from __future__ import annotations


def activity_times_intensity(activity: float, intensity: float) -> float:
    """Method A: E = A × I_final."""
    return float(activity) * float(intensity)


def useful_to_final(useful: float, efficiency: float) -> float:
    """Method B: E_final = U / η. η > 0; heat pumps may have η > 1 (COP)."""
    eta = float(efficiency)
    if eta <= 0:
        raise ValueError("eficiencia debe ser > 0")
    return float(useful) / eta


def share_useful(useful_total: float, share: float) -> float:
    return float(useful_total) * float(share)


def stock_use_intensity(n_units: float, use: float, intensity: float) -> float:
    """Method C: E = N × a × I."""
    return float(n_units) * float(use) * float(intensity)


def liters_from_vkt(vehicles: float, km: float, liters_per_km: float) -> float:
    return float(vehicles) * float(km) * float(liters_per_km)


def kwh_from_vkt(vehicles: float, km: float, kwh_per_km: float, charge_eff: float = 1.0) -> float:
    if charge_eff <= 0:
        raise ValueError("eficiencia de carga debe ser > 0")
    return float(vehicles) * float(km) * float(kwh_per_km) / float(charge_eff)


def pumping_kwh(volume_m3: float, head_m: float, eta: float, rho: float = 1000.0, g: float = 9.81) -> float:
    """E = ρ g V H / η  (J) → kWh."""
    if eta <= 0:
        raise ValueError("η bomba > 0")
    joules = rho * g * volume_m3 * head_m / eta
    return joules / 3.6e6


def interpolate(year: int, y0: int, v0: float, y1: int, v1: float) -> float:
    if y1 == y0:
        return float(v0)
    t = (year - y0) / (y1 - y0)
    return float(v0) + t * (float(v1) - float(v0))


def grow(value: float, rate: float, years: int) -> float:
    return float(value) * (1.0 + float(rate)) ** int(years)


def sequential_measures(base: float, factors: list[float]) -> float:
    """Interactions: 0.90 then 0.80 → 0.72, not 0.70."""
    x = float(base)
    for f in factors:
        x *= float(f)
    return x
