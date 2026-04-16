"""Tool: 贡献度计算 — 对应原系统 DevotedCompute FuncMap.

支持两种贡献度分解方法，适用于不同的指标公式结构：

1. 结构贡献度拆解法 (Structural Decomposition) — 用于除法指标
   适用于：播放成功率、卡顿率等比率型指标 V = Σ(P_i × V_i)
   其中 P_i 为维度 i 的流量占比，V_i 为维度 i 的指标值

   公式（对每个维度 a）：
     ΔV_a = 0.5×(Pa1+Pa0)×(Va1-Va0) + [0.5×(Va1+Va0) - V0]×(Pa1-Pa0)
            ├── 性能效应 ──────────┘   └── 结构效应 ──────────────────┘
   其中：
     - Pa0/Pa1: 维度 a 在基期/当期的流量占比
     - Va0/Va1: 维度 a 在基期/当期的指标值
     - V0: 总体基线值
   性能效应：平均权重 × 指标值变化（维度本身变好/变差）
   结构效应：(维度均值 - 总体基线) × 权重变化（流量向偏离基线的维度迁移）

2. LMDI 分解法 (Logarithmic Mean Divisia Index) — 用于乘法指标
   适用于：总量 = Σ(S_i × I_i) 形式的乘法分解场景
   如能源消耗 E = Σ(结构占比 × 能源强度)

   公式：
     L(a, b) = (a - b) / (ln(a) - ln(b))
     contribution_i = L(share_i_t2, share_i_t1) × ln(value_i_t2 / value_i_t1)
"""

import math

from langchain_core.tools import tool


def compute_structural(dimension_data: list[dict], v0: float = 0.0) -> list[dict]:
    """结构贡献度拆解法：将总变化分解为性能效应和结构效应.

    公式: ΔV_a = 0.5×(Pa1+Pa0)×(Va1-Va0) + [0.5×(Va1+Va0) - V0]×(Pa1-Pa0)

    Args:
        dimension_data: 各维度数据列表
            [{"name": "cn-south", "t1": 99.3, "t2": 96.1, "p0": 0.35, "p1": 0.38}, ...]
            - t1/t2 (或 va0/va1): 维度在基期/当期的指标值
            - p0/p1: 维度在基期/当期的流量占比（不提供则等权）
        v0: 总体基线值。若不提供则用 Σ(p0_i × t1_i) 计算

    Returns:
        各维度贡献度列表，按贡献绝对值降序
    """
    if not dimension_data:
        return []

    n = len(dimension_data)

    # 检查是否有流量占比数据
    has_proportion = all("p0" in d and "p1" in d for d in dimension_data)
    if not has_proportion:
        # 无占比数据，假设等权且权重不变
        for d in dimension_data:
            d["p0"] = 1.0 / n
            d["p1"] = 1.0 / n

    # 如果没有传入 v0，用基期数据计算
    if v0 == 0.0:
        v0 = sum(d["p0"] * d["t1"] for d in dimension_data)

    contributions = []
    for d in dimension_data:
        pa0, pa1 = d["p0"], d["p1"]
        va0, va1 = d["t1"], d["t2"]

        # 性能效应: 0.5×(Pa1+Pa0)×(Va1-Va0)
        perf_effect = 0.5 * (pa1 + pa0) * (va1 - va0)

        # 结构效应: [0.5×(Va1+Va0) - V0]×(Pa1-Pa0)
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

    # 计算贡献占比
    total_abs = sum(abs(c["contribution"]) for c in contributions)
    if total_abs > 0:
        for c in contributions:
            c["ratio"] = (abs(c["contribution"]) / total_abs) * 100

    contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
    return contributions


def _log_mean(a: float, b: float) -> float:
    """对数均值函数 L(a, b) = (a - b) / (ln(a) - ln(b)).

    边界处理：当 a ≈ b 时，L(a,b) ≈ a（洛必达法则）。
    """
    if a <= 0 or b <= 0:
        return 0.0
    if abs(a - b) < 1e-10:
        return a
    log_diff = math.log(a) - math.log(b)
    if abs(log_diff) < 1e-10:
        return a
    return (a - b) / log_diff


def compute_lmdi(dimension_data: list[dict]) -> list[dict]:
    """LMDI 分解法：用于乘法指标 E = Σ(S_i × I_i).

    Args:
        dimension_data: [{"name": "xx", "t1": 100, "t2": 80}, ...]

    Returns:
        各维度贡献度列表
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
def compute_contribution(dimension_data: str, method: str = "structural") -> str:
    """计算各维度对指标变化的贡献度。当你已经完成维度下钻，需要精确量化各维度贡献时使用。

    支持两种方法：
    - structural（结构贡献度拆解，默认）：适用于比率型指标（播放成功率、卡顿率），将贡献分解为性能效应和结构效应。
    - lmdi（LMDI 分解）：适用于乘法指标（总量 = 结构 × 强度），如能源消耗分析。

    输入:
        dimension_data: 维度数据 JSON 字符串，格式为:
            [{"name": "维度值", "t1": 基线值, "t2": 当前值, "p0": 基期流量占比, "p1": 当期流量占比}, ...]
            p0/p1 可选，不提供时假设等权
        method: "structural"（默认）或 "lmdi"

    输出: 各维度的贡献度分数和贡献占比。
    """
    import json

    try:
        data = json.loads(dimension_data)
    except json.JSONDecodeError:
        return (
            '错误: dimension_data 不是有效的 JSON 格式。请提供格式: '
            '[{"name": "xx", "t1": 99.3, "t2": 96.1}, ...]'
        )

    if method == "lmdi":
        results = compute_lmdi(data)
        method_label = "LMDI 分解法 (乘法指标)"
    else:
        results = compute_structural(data)
        method_label = "结构贡献度拆解法 (除法指标)"

    lines = [f"贡献度分析结果 (方法: {method_label}):"]

    for r in results:
        line = (
            f"  {r['name']}: "
            f"贡献度={r['contribution']:+.4f}, "
            f"贡献占比={r['ratio']:.1f}%"
        )
        if "delta" in r:
            line += f", 指标变化={r['delta']:+.2f}"
        if method == "structural" and "performance_effect" in r:
            line += (
                f"\n    ├ 性能效应={r['performance_effect']:+.4f} "
                f"(维度指标值变化的影响)"
                f"\n    └ 结构效应={r['structure_effect']:+.4f} "
                f"(流量占比迁移的影响)"
            )
        lines.append(line)

    total_c = sum(c["contribution"] for c in results)
    lines.append(f"\n  总贡献度: {total_c:+.4f}")
    lines.append("  验证: 各维度贡献度之和应等于指标总变化量")

    return "\n".join(lines)
