"""结构化 Markdown 归因报告生成器.

从 Agent 最终状态（告警 + checklist + evidence_pool + matched_scenarios + LLM diagnose）
渲染出一份可审计的 Markdown 报告。CLI 和 test_scenarios 都用它输出报告。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

EVIDENCE_MARKER = "===EVIDENCE==="

def _strip_evidence(text: str) -> str:
    if EVIDENCE_MARKER in text:
        return text.split(EVIDENCE_MARKER, 1)[0].rstrip()
    return text


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """同时兼容 dict / pydantic / dataclass 取字段。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_diagnose(messages: list) -> str:
    """从消息列表里找出最后一条 LLM 归因报告（长度阈值过滤 chit-chat）。"""
    for msg in reversed(messages or []):
        content = getattr(msg, "content", "")
        if not content:
            continue
        content = str(content)
        if len(content) < 200:
            continue
        # 只接受 AIMessage，不接受 HumanMessage / ToolMessage
        if getattr(msg, "type", "") == "ai":
            return content
    return ""


def _summarize_evidence(ev: dict) -> str:
    """从一条 evidence 里抽出一句可读的核心发现。"""
    parsed = ev.get("parsed") or {}
    tool = ev.get("tool", "")
    args = ev.get("args", {}) or {}

    if parsed and parsed.get("found") is not False:
        if tool == "query_metric":
            # 维度下钻
            if args.get("dimension") or parsed.get("breakdown"):
                top_name = parsed.get("top1_name")
                top_ratio = parsed.get("top1_contribution")
                if top_name is not None:
                    s = f"top1: **{top_name}**"
                    if isinstance(top_ratio, (int, float)):
                        s += f" (贡献 {top_ratio * 100:.0f}%)"
                    return s
            # 整体查询
            t1 = parsed.get("t1_value")
            t2 = parsed.get("t2_value")
            ratio = parsed.get("delta_ratio_pct")
            trend = parsed.get("trend")
            if t1 is not None and t2 is not None:
                s = f"{t1} → {t2}"
                if ratio is not None:
                    s += f"  Δ={ratio:+.1f}%"
                if trend:
                    s += f"  ({trend})"
                return s
        elif tool == "decompose_metric":
            parts = []
            top = parsed.get("top1_name")
            top_ratio = parsed.get("top1_contribution")
            if top:
                seg = f"主贡献 **{top}**"
                if isinstance(top_ratio, (int, float)):
                    seg += f" ({top_ratio * 100:.0f}%)"
                parts.append(seg)
            gini = parsed.get("gini")
            level = parsed.get("level")
            if gini is not None:
                seg = f"GINI={gini:.2f}"
                if level:
                    seg += f" ({level})"
                parts.append(seg)
            if parts:
                return " · ".join(parts)
        elif tool == "decompose_formula":
            top = parsed.get("top_contributor")
            top_ratio = parsed.get("top1_contribution")
            if top:
                s = f"瓶颈子指标 **{top}**"
                if isinstance(top_ratio, (int, float)):
                    s += f" ({top_ratio * 100:.0f}%)"
                return s
        elif tool == "match_events":
            count = parsed.get("match_count", 0)
            if count == 0:
                return "未命中"
            events = parsed.get("events") or []
            first = events[0].get("description", "") if events else ""
            if len(first) > 80:
                first = first[:80] + "..."
            return f"命中 {count} 条 · {first}" if first else f"命中 {count} 条"
        elif tool == "query_events":
            return f"{parsed.get('count', 0)} 条事件"
        elif tool == "query_logs":
            return f"{parsed.get('count', 0)} 条日志"
    elif parsed.get("found") is False:
        return "(无数据)"

    # fallback：跳过"标题行"取首条实际数据
    result = _strip_evidence(str(ev.get("result", "")))
    for line in result.splitlines():
        line = line.strip()
        if not line or line.endswith(":") or line.endswith("："):
            continue
        return line[:120] + ("..." if len(line) > 120 else "")
    return "(无摘要)"


def render_report(state: dict) -> str:
    """渲染精简归因报告（告警 → 结论 → 证据）。"""
    alert = state.get("alert")
    evidence_pool = state.get("evidence_pool") or {}
    matched = state.get("matched_scenarios") or []
    diagnose = _extract_diagnose(state.get("messages", []))
    stats = state.get("_token_stats") or {}

    lines: list[str] = ["# 归因诊断报告", ""]
    lines.append(f"_生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")

    # ---------- 1. 告警信息 ----------
    if alert is not None:
        lines.append("## 1. 告警信息")
        lines.append("")
        lines.append(f"- **告警 ID**：{_get(alert, 'alert_id', '-')}")
        lines.append(f"- **指标**：`{_get(alert, 'metric_name', '-')}`")
        lines.append(f"- **描述**：{_get(alert, 'description', '-')}")
        lines.append(f"- **级别**：{_get(alert, 'severity', '-')}")
        cur = _get(alert, "current_value", "-")
        base = _get(alert, "baseline_value", "-")
        lines.append(f"- **当前值 / 基线值**：{cur} / {base}")
        lines.append("")

    # ---------- 2. 归因结论（顶部仅展示 badge，完整 yaml 文本挪到附录） ----------
    lines.append("## 2. 归因结论")
    lines.append("")
    full = [m for m in matched if _get(m, "match_score", 0) >= 1.0]
    if full:
        m = full[0]
        badge = (
            f"🎯 **命中场景**：{_get(m, 'scenario_name')} / "
            f"{_get(m, 'rule_name')}（置信度：**{_get(m, 'confidence')}**）"
        )
        if len(full) > 1:
            others = ", ".join(
                f"{_get(x, 'scenario_name')}/{_get(x, 'rule_name')}"
                for x in full[1:]
            )
            badge += f"  · 其他命中：{others}"
        lines.append(badge)
        lines.append("")
        lines.append("_完整规则定义见文末附录；本次带数值的归因结论由下方 LLM 分析给出。_")
    else:
        lines.append("⚠️ **未命中任何已知场景规则**，以下为 LLM 基于证据自由推理的归因结论。")
    lines.append("")

    if diagnose:
        lines.append(diagnose.strip())
        lines.append("")

    # ---------- 3. 支撑证据 ----------
    if evidence_pool:
        lines.append("## 3. 支撑证据")
        lines.append("")
        lines.append("| 步骤 | 工具 | 关键发现 |")
        lines.append("|---|---|---|")
        for step_id, ev in evidence_pool.items():
            tool = ev.get("tool", "-")
            # args 里带上最关键的标识（metric / dimension）
            args = ev.get("args", {}) or {}
            key_args = []
            for k in ("metric", "dimension", "keywords", "level"):
                if k in args:
                    key_args.append(f"{k}={args[k]}")
            args_str = ", ".join(key_args) if key_args else "-"
            summary = _summarize_evidence(ev)
            lines.append(
                f"| `{step_id}` | `{tool}`({args_str}) | {summary} |"
            )
        lines.append("")

    # ---------- 附录 A：规则库定义的通用结论 ----------
    if full:
        lines.append("## 附录 A：命中规则定义（知识库原文）")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>点击展开查看规则库中该场景的预定义结论与建议</summary>")
        lines.append("")
        for m in full:
            lines.append(
                f"### {_get(m, 'scenario_name')} / {_get(m, 'rule_name')}"
            )
            lines.append("")
            lines.append(f"- **置信度**：{_get(m, 'confidence')}")
            lines.append(f"- **通用结论**：{_get(m, 'conclusion')}")
            lines.append(f"- **通用建议**：{_get(m, 'suggested_action')}")
            lines.append("")
        lines.append("</details>")
        lines.append("")

    # ---------- 附录 B：Token 消耗 ----------
    if stats:
        lines.append("---")
        lines.append("")
        lines.append(
            f"_模型 `{stats.get('model', '-')}` | "
            f"输入 {stats.get('total_input', 0)} / "
            f"输出 {stats.get('total_output', 0)} / "
            f"合计 **{stats.get('total', 0)}** tokens_"
        )
        lines.append("")

    return "\n".join(lines)


def save_report(
    state: dict,
    output_dir: str = "output",
    scenario_name: str = "",
) -> str:
    """渲染并写入文件，返回报告路径。"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"report_{scenario_name}_{ts}.md" if scenario_name else f"report_{ts}.md"
    path = Path(output_dir) / base
    path.write_text(render_report(state), encoding="utf-8")
    return str(path)
