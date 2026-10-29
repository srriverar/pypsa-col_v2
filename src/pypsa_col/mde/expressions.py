"""Safe expression tree (no eval). LEAP-like interpolate / growth / multiply."""

from __future__ import annotations

from typing import Any

from .methods import grow, interpolate


class ExprError(ValueError):
    pass


def eval_expr(node: dict[str, Any], env: dict[str, float]) -> float:
    t = node.get("type")
    if t == "const":
        return float(node["value"])
    if t == "reference":
        k = node["variable"]
        if k not in env:
            raise ExprError(f"variable desconocida: {k}")
        return float(env[k])
    if t == "multiply":
        acc = 1.0
        for a in node.get("arguments") or []:
            acc *= eval_expr(a, env)
        return acc
    if t == "add":
        return sum(eval_expr(a, env) for a in node.get("arguments") or [])
    if t == "divide":
        args = node.get("arguments") or []
        if len(args) != 2:
            raise ExprError("divide requiere 2 argumentos")
        den = eval_expr(args[1], env)
        if den == 0:
            raise ExprError("división por cero")
        return eval_expr(args[0], env) / den
    if t == "grow":
        return grow(eval_expr(node["base"], env), float(node["rate"]), int(node["years"]))
    if t == "interpolate":
        return interpolate(
            int(node["year"]),
            int(node["y0"]),
            eval_expr(node["v0"], env),
            int(node["y1"]),
            eval_expr(node["v1"], env),
        )
    if t == "min":
        return min(eval_expr(a, env) for a in node["arguments"])
    if t == "max":
        return max(eval_expr(a, env) for a in node["arguments"])
    raise ExprError(f"tipo no autorizado: {t}")
