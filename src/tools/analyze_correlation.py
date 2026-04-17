"""Tool C3: 相关性分析 — 判断基础指标与相关指标是否同向异常.

用法：当基础指标（如 play_success_rate）下跌时，常通过观察相关指标
（如 cdn_error_rate、player_error_rate）是否同步异常来佐证假设。
本工具用皮尔逊相关系数衡量两条时间序列的相关性。
"""

import json
import math

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


def _evidence_block(payload: dict) -> str:
    return "\n\n===EVIDENCE===\n" + json.dumps(payload, ensure_ascii=False)


def compute_pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den_x = math.sqrt(sum((xs[i] - mean_x) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ys[i] - mean_y) ** 2 for i in range(n)))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


@tool
def analyze_correlation(base_metric: str, related_metrics: str, threshold: float = 0.7) -> str:
    """分析基础指标与若干相关指标的相关性（皮尔逊系数）。

    输入:
        base_metric: 基础指标，如 play_success_rate
        related_metrics: 逗号分隔的相关指标列表，如 "cdn_error_rate,player_error_rate"
        threshold: 相关性阈值，|r| > threshold 视为强相关（默认 0.7）

    输出: 各相关指标的相关系数、方向（正/负）、是否强相关，以及最强相关项。
    """
    if _simulator is None:
        return "错误：数据模拟器未初始化。" + _evidence_block({})

    base = _simulator.query_metrics(base_metric, 0, 3600)
    if not base.data_points:
        payload = {"base_metric": base_metric, "found": False}
        return f"基础指标 {base_metric} 无数据。" + _evidence_block(payload)

    base_series = [p.value for p in base.data_points]
    names = [s.strip() for s in related_metrics.split(",") if s.strip()]
    if not names:
        return (
            "错误：请提供至少一个相关指标（逗号分隔）。"
            + _evidence_block({"base_metric": base_metric, "found": False})
        )

    results = []
    missing = []
    for name in names:
        other = _simulator.query_metrics(name, 0, 3600)
        if not other.data_points:
            missing.append(name)
            continue
        other_series = [p.value for p in other.data_points]
        m = min(len(base_series), len(other_series))
        r = compute_pearson(base_series[-m:], other_series[-m:])
        delta = other.delta
        results.append({
            "name": name,
            "pearson": round(r, 4),
            "abs_r": abs(r),
            "direction": "positive" if r > 0 else ("negative" if r < 0 else "none"),
            "is_strong": abs(r) >= threshold,
            "t1": other.t1_value,
            "t2": other.t2_value,
            "delta": round(delta, 4),
        })

    if not results:
        payload = {
            "base_metric": base_metric,
            "related_metrics": names,
            "found": False,
            "missing": missing,
        }
        return (
            f"相关指标 {names} 均无数据，无法分析相关性。" + _evidence_block(payload)
        )

    results.sort(key=lambda x: x["abs_r"], reverse=True)
    top = results[0]

    lines = [f"相关性分析 [{base_metric}]:"]
    for r in results:
        flag = "★" if r["is_strong"] else " "
        lines.append(
            f"  {flag} {r['name']}: r={r['pearson']:+.3f} ({r['direction']}), "
            f"Δ={r['delta']:+.3f}"
        )
    if missing:
        lines.append(f"\n  缺失数据的指标: {missing}")

    payload = {
        "base_metric": base_metric,
        "related_metrics": names,
        "found": True,
        "missing": missing,
        "threshold": threshold,
        "top_related": top["name"],
        "top_pearson": top["pearson"],
        "has_strong_correlation": any(r["is_strong"] for r in results),
        "correlations": [
            {k: v for k, v in r.items() if k != "abs_r"} for r in results
        ],
    }
    return "\n".join(lines) + _evidence_block(payload)
