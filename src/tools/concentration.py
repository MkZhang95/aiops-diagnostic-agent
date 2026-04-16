"""Tool: 集中性判断 — 对应原系统 RootCauseAnalysis FuncMap (GINI 系数).

GINI 系数：衡量分布的不均匀程度。
  - 0 = 完全均匀（每个维度贡献相同）
  - 1 = 完全集中（单个维度贡献 100%）

公式：
  排序后，GINI = (2 * Σ(i * x_i)) / (n * Σ(x_i)) - (n + 1) / n

判断标准：
  - GINI > 0.7: 高度集中 → 通常有明确的单一根因
  - 0.4 ≤ GINI ≤ 0.7: 中等集中 → 可能有 2-3 个主要因素
  - GINI < 0.4: 分散 → 系统性问题，非单点故障
"""

from langchain_core.tools import tool


def compute_gini(values: list[float]) -> float:
    """计算 GINI 系数.

    Args:
        values: 各维度贡献度的绝对值列表

    Returns:
        GINI 系数 (0~1)
    """
    if not values or len(values) < 2:
        return 0.0

    # 取绝对值并排序（升序）
    sorted_values = sorted(abs(v) for v in values)
    n = len(sorted_values)
    total = sum(sorted_values)

    if total == 0:
        return 0.0

    # GINI = (2 * Σ(i * x_i)) / (n * Σ(x_i)) - (n + 1) / n
    # 其中 i 从 1 开始
    weighted_sum = sum((i + 1) * v for i, v in enumerate(sorted_values))
    gini = (2 * weighted_sum) / (n * total) - (n + 1) / n

    return max(0.0, min(1.0, gini))  # 钳位到 [0, 1]


@tool
def check_concentration(contribution_data: str, threshold: float = 0.7) -> str:
    """判断问题是否集中在少数维度（GINI 系数分析）。当你已经完成贡献度计算，需要判断问题集中性时使用。

    输入:
        contribution_data: 贡献度数据 JSON 字符串，格式为:
            [{"name": "维度值", "contribution": 贡献度, "ratio": 贡献占比}, ...]
        threshold: 集中性阈值，默认 0.7

    输出: GINI 系数、集中性判断、Top 贡献者列表。
    """
    import json

    try:
        data = json.loads(contribution_data)
    except json.JSONDecodeError:
        return "错误: contribution_data 不是有效的 JSON 格式"

    values = [abs(d.get("contribution", d.get("ratio", 0))) for d in data]
    gini = compute_gini(values)

    # 判断集中程度
    if gini > 0.7:
        level = "高度集中"
        interpretation = "问题高度集中在少数维度，很可能有明确的单一根因"
    elif gini > 0.4:
        level = "中等集中"
        interpretation = "问题在 2-3 个维度上有显著影响，可能是多因素叠加"
    else:
        level = "分散"
        interpretation = "问题分布较均匀，可能是系统性问题而非单点故障"

    # Top 贡献者
    sorted_data = sorted(data, key=lambda x: abs(x.get("ratio", x.get("contribution", 0))), reverse=True)
    top = sorted_data[:3]

    lines = [
        "集中性分析结果:",
        f"  GINI 系数: {gini:.3f}",
        f"  集中程度: {level}",
        f"  阈值: {threshold}",
        f"  是否集中: {'是' if gini > threshold else '否'}",
        f"  解读: {interpretation}",
        "\n  Top 贡献者:",
    ]

    for t in top:
        name = t.get("name", "unknown")
        ratio = t.get("ratio", 0)
        lines.append(f"    - {name}: {ratio:.1f}%")

    return "\n".join(lines)
