"""Tool C1: 维度贡献度分解 + GINI 集中度.

合并原 analyze_contribution + analyze_concentration：
  - 用结构贡献度拆解法 (Structural Decomposition) 计算各维度对指标变化的贡献
  - 用 GINI 系数衡量贡献的集中程度
  - 一次调用同时给出 top1_contribution / gini / level

适用于比率型指标（播放成功率、卡顿率等 V = Σ(P_i × V_i) 结构）。
乘法指标请用 decompose_formula（LMDI）。
"""

import json

from langchain_core.tools import tool

from src.data.simulator import DataSimulator


def _evidence_block(payload: dict) -> str:
    return "\n\n===EVIDENCE===\n" + json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 纯计算函数（供单元测试和工具共用）
# ---------------------------------------------------------------------------


def compute_gini(values: list[float]) -> float:
    """GINI 系数：衡量分布不均匀程度.

    - 0 = 完全均匀
    - 1 = 完全集中在单一维度

    公式: GINI = (2 * Σ(i * x_i)) / (n * Σ(x_i)) - (n + 1) / n
    """
    if not values or len(values) < 2:
        return 0.0

    sorted_values = sorted(abs(v) for v in values)
    n = len(sorted_values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0

    weighted_sum = sum((i + 1) * v for i, v in enumerate(sorted_values))
    gini = (2 * weighted_sum) / (n * total) - (n + 1) / n
    return max(0.0, min(1.0, gini))


def compute_structural(dimension_data: list[dict], v0: float = 0.0) -> list[dict]:
    """结构贡献度拆解法.

    ΔV_a = 0.5×(Pa1+Pa0)×(Va1-Va0)  +  [0.5×(Va1+Va0) - V0]×(Pa1-Pa0)
           └── 性能效应 ─────────┘   └── 结构效应 ─────────────────┘

    Args:
        dimension_data: [{"name", "t1", "t2", "p0"?, "p1"?}, ...]
            无 p0/p1 时回退等权
        v0: 总体基线；0 时用 Σ(p0_i × t1_i) 计算
    """
    if not dimension_data:
        return []

    n = len(dimension_data)
    has_proportion = all("p0" in d and "p1" in d for d in dimension_data)
    if not has_proportion:
        for d in dimension_data:
            d["p0"] = 1.0 / n
            d["p1"] = 1.0 / n

    if v0 == 0.0:
        v0 = sum(d["p0"] * d["t1"] for d in dimension_data)

    contributions = []
    for d in dimension_data:
        pa0, pa1 = d["p0"], d["p1"]
        va0, va1 = d["t1"], d["t2"]

        perf_effect = 0.5 * (pa1 + pa0) * (va1 - va0)
        struct_effect = (0.5 * (va1 + va0) - v0) * (pa1 - pa0)
        total_effect = perf_effect + struct_effect

        contributions.append({
            "name": d["name"],
            "contribution": total_effect,
            "performance_effect": perf_effect,
            "structure_effect": struct_effect,
            "delta": va1 - va0,
            "proportion_change": pa1 - pa0,
            "ratio": 0.0,
        })

    total_abs = sum(abs(c["contribution"]) for c in contributions)
    if total_abs > 0:
        for c in contributions:
            c["ratio"] = (abs(c["contribution"]) / total_abs) * 100

    contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
    return contributions


def _classify(gini: float) -> tuple[str, str]:
    if gini > 0.7:
        return "高度集中", "问题高度集中在少数维度，通常有明确的单一根因"
    if gini > 0.4:
        return "中等集中", "问题在 2-3 个维度上有显著影响，可能是多因素叠加"
    return "分散", "问题分布较均匀，可能是系统性问题而非单点故障"


# ---------------------------------------------------------------------------
# 工具入口
# ---------------------------------------------------------------------------


def make_decompose_metric_tool(simulator: DataSimulator):
    """Create a decompose_metric tool bound to one diagnostic data source."""

    @tool("decompose_metric")
    def decompose_metric(metric: str, dimension: str, threshold: float = 0.7) -> str:
        """维度贡献度分解 + GINI 集中度分析（比率型指标）。

        工具内部会自动从数据源拉取 `metric` 在 `dimension` 维度的下钻数据，
        用结构贡献度拆解法计算每个维度值的贡献，并用 GINI 系数判断集中度。

        输入:
            metric: 指标名
            dimension: 维度名（isp / region / app_version / ...）
            threshold: GINI 集中性阈值（默认 0.7）

        输出: 各维度贡献 + GINI 系数 + 集中程度解读 + Top 贡献者。
        """
        breakdowns = simulator.drill_down(metric, dimension, (0, 3600))
        if not breakdowns:
            payload = {"metric": metric, "dimension": dimension, "found": False}
            return (
                f"指标 {metric} 在维度 {dimension} 无下钻数据，无法分解。"
                + _evidence_block(payload)
            )

        dim_data = [
            {"name": b.dimension_value, "t1": b.t1_value, "t2": b.t2_value}
            for b in breakdowns
        ]
        contributions = compute_structural(dim_data)

        # GINI 基于贡献占比（scenarios 数据里的 contribution_ratio 和结构分解出的 ratio 等价）
        gini = compute_gini([c["ratio"] for c in contributions])
        level, interpretation = _classify(gini)
        is_concentrated = gini > threshold

        top1 = contributions[0] if contributions else {"name": "", "ratio": 0.0}
        top1_contribution = round(top1["ratio"] / 100.0, 4) if contributions else 0.0

        lines = [
            f"维度分解 [{metric} / {dimension}]:",
            f"  GINI 系数   = {gini:.3f} ({level}, 阈值 {threshold})",
            f"  是否集中    = {'是' if is_concentrated else '否'}",
            f"  解读        = {interpretation}",
            "",
            "  维度贡献（按贡献绝对值降序）:",
        ]
        for c in contributions:
            lines.append(
                f"    {c['name']}: "
                f"贡献={c['contribution']:+.4f} "
                f"(占比 {c['ratio']:.1f}%, 指标变化 {c['delta']:+.2f})"
            )

        payload = {
            "metric": metric,
            "dimension": dimension,
            "found": True,
            "gini": round(gini, 4),
            "level": level,
            "is_concentrated": is_concentrated,
            "top1_name": top1["name"],
            "top1_contribution": top1_contribution,
            "total_contribution": round(
                sum(c["contribution"] for c in contributions), 4
            ),
            "contributions": [
                {
                    "name": c["name"],
                    "contribution": round(c["contribution"], 4),
                    "ratio_pct": round(c["ratio"], 2),
                    "delta": round(c["delta"], 4),
                }
                for c in contributions
            ],
        }
        return "\n".join(lines) + _evidence_block(payload)

    return decompose_metric
