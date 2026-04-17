"""Tool C2: 公式拆解 (LMDI) — 适用于乘法指标.

对形如 E = Σ(S_i × I_i) 的乘法/加性组合指标，用 LMDI 分解法量化各子指标
对整体变化的贡献。调用方需要在分析计划里明确公式，即 `sub_metrics` 列表
对应公式中各项的子指标名。

比率型指标（播放成功率 = Σ(占比 × 分维度成功率)）请用 decompose_metric。
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


def _log_mean(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 0.0
    if abs(a - b) < 1e-10:
        return a
    log_diff = math.log(a) - math.log(b)
    if abs(log_diff) < 1e-10:
        return a
    return (a - b) / log_diff


def compute_lmdi(dimension_data: list[dict]) -> list[dict]:
    """LMDI 分解法：E = Σ(S_i × I_i).

    contribution_i = L(share_i_t2, share_i_t1) × ln(value_i_t2 / value_i_t1)
    """
    if not dimension_data:
        return []

    total_t1 = sum(d["t1"] for d in dimension_data)
    total_t2 = sum(d["t2"] for d in dimension_data)

    if total_t1 == 0 or total_t2 == 0:
        return [{"name": d["name"], "contribution": 0, "ratio": 0} for d in dimension_data]

    contributions = []
    for d in dimension_data:
        t1, t2 = d["t1"], d["t2"]
        if t1 <= 0 or t2 <= 0:
            contributions.append({"name": d["name"], "contribution": 0.0, "ratio": 0.0})
            continue

        share_t1 = t1 / total_t1
        share_t2 = t2 / total_t2
        lm = _log_mean(share_t2, share_t1)
        contribution = lm * math.log(t2 / t1)

        contributions.append({
            "name": d["name"],
            "contribution": contribution,
            "ratio": 0.0,
        })

    total_abs = sum(abs(c["contribution"]) for c in contributions)
    if total_abs > 0:
        for c in contributions:
            c["ratio"] = (abs(c["contribution"]) / total_abs) * 100

    contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
    return contributions


@tool
def decompose_formula(metric: str, sub_metrics: str) -> str:
    """按公式对乘法型指标做 LMDI 拆解。

    适用场景：播放流程由多个独立成功率相乘/叠加组成，
    如 play_success_rate ≈ cdn_success_rate × decode_success_rate × network_success_rate。
    当分析计划里指定了 formula 时调用本工具，量化每个子指标的贡献。

    输入:
        metric: 父指标名（用于记录，不参与计算）
        sub_metrics: 逗号分隔的子指标名，如 "cdn_success_rate,decode_success_rate,network_success_rate"

    输出: 各子指标的 LMDI 贡献度 + 贡献占比 + Top 贡献子指标。
    """
    if _simulator is None:
        return "错误：数据模拟器未初始化。" + _evidence_block({})

    names = [s.strip() for s in sub_metrics.split(",") if s.strip()]
    if not names:
        return (
            "错误：请提供至少一个子指标（逗号分隔）。"
            + _evidence_block({"metric": metric, "found": False})
        )

    dim_data = []
    missing = []
    for name in names:
        data = _simulator.query_metrics(name, 0, 3600)
        if not data.data_points:
            missing.append(name)
            continue
        dim_data.append({"name": name, "t1": data.t1_value, "t2": data.t2_value})

    if not dim_data:
        payload = {
            "metric": metric,
            "sub_metrics": names,
            "found": False,
            "missing": missing,
        }
        return (
            f"子指标 {names} 均无数据，无法做公式拆解。" + _evidence_block(payload)
        )

    results = compute_lmdi(dim_data)

    lines = [f"公式拆解 (LMDI) [{metric}]:"]
    for r in results:
        lines.append(
            f"  {r['name']}: 贡献={r['contribution']:+.4f} "
            f"(占比 {r['ratio']:.1f}%)"
        )
    if missing:
        lines.append(f"\n  缺失子指标数据: {missing}")

    top1 = results[0] if results else {"name": "", "contribution": 0.0, "ratio": 0.0}
    total_c = sum(r["contribution"] for r in results)

    payload = {
        "metric": metric,
        "sub_metrics": names,
        "found": True,
        "missing": missing,
        "top_contributor": top1["name"],
        "top1_contribution": round(top1["ratio"] / 100.0, 4),
        "total_contribution": round(total_c, 4),
        "contributions": [
            {
                "name": r["name"],
                "contribution": round(r["contribution"], 4),
                "ratio_pct": round(r["ratio"], 2),
            }
            for r in results
        ],
    }
    return "\n".join(lines) + _evidence_block(payload)
