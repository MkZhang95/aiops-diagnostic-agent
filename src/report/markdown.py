"""结构化 Markdown 归因报告生成器.

从 Agent 最终状态（告警 + checklist + evidence_pool + matched_scenarios + LLM diagnose）
渲染出一份可审计的 Markdown 报告。CLI 和 test_scenarios 都用它输出报告。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

EVIDENCE_MARKER = "===EVIDENCE==="

_STATUS_ICON = {
    "done": "✅",
    "pending": "⏸️",
    "skipped": "➖",
    "in_progress": "⏳",
}

_PRIORITY_ORDER = {"must": 0, "should": 1, "show": 2}


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


def render_report(state: dict) -> str:
    """把 state 渲染为 Markdown 字符串（纯函数，方便单测）。"""
    alert = state.get("alert")
    checklist = state.get("checklist") or []
    evidence_pool = state.get("evidence_pool") or {}
    matched = state.get("matched_scenarios") or []
    diagnose = _extract_diagnose(state.get("messages", []))

    lines: list[str] = ["# 归因诊断报告", ""]
    lines.append(f"_生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")

    # ---------- 告警信息 ----------
    if alert is not None:
        lines.append("## 告警信息")
        lines.append("")
        lines.append(f"- **告警 ID**：{_get(alert, 'alert_id', '-')}")
        lines.append(f"- **指标**：`{_get(alert, 'metric_name', '-')}`")
        lines.append(f"- **描述**：{_get(alert, 'description', '-')}")
        lines.append(f"- **级别**：{_get(alert, 'severity', '-')}")
        cur = _get(alert, "current_value", "-")
        base = _get(alert, "baseline_value", "-")
        lines.append(f"- **当前值 / 基线值**：{cur} / {base}")
        lines.append("")

    # ---------- 采集清单状态 ----------
    if checklist:
        lines.append("## 采集清单执行状态")
        lines.append("")
        items = sorted(
            checklist,
            key=lambda x: (
                _PRIORITY_ORDER.get(_get(x, "priority", "show"), 9),
                _get(x, "id", ""),
            ),
        )
        total = len(items)
        done = sum(1 for x in items if _get(x, "status") == "done")
        must_total = sum(1 for x in items if _get(x, "priority") == "must")
        must_done = sum(
            1 for x in items
            if _get(x, "priority") == "must" and _get(x, "status") == "done"
        )
        lines.append(
            f"整体 {done}/{total} 完成，其中 must 级 {must_done}/{must_total}。"
        )
        lines.append("")
        lines.append("| 状态 | 优先级 | 步骤 ID | 工具 | 名称 |")
        lines.append("|---|---|---|---|---|")
        for item in items:
            status = _get(item, "status", "pending")
            icon = _STATUS_ICON.get(status, "❔")
            lines.append(
                f"| {icon} {status} | {_get(item, 'priority', '-')} "
                f"| `{_get(item, 'id', '-')}` | `{_get(item, 'action', '-')}` "
                f"| {_get(item, 'name', '-')} |"
            )
        lines.append("")

    # ---------- 证据池摘要 ----------
    if evidence_pool:
        lines.append("## 证据池摘要")
        lines.append("")
        for step_id, ev in evidence_pool.items():
            tool = ev.get("tool", "-")
            result = _strip_evidence(str(ev.get("result", "")))
            if len(result) > 600:
                result = result[:600] + "\n... (truncated)"
            lines.append(f"### `{step_id}` — tool: `{tool}`")
            lines.append("")
            lines.append("```")
            lines.append(result or "(空)")
            lines.append("```")
            lines.append("")

    # ---------- 场景规则匹配 ----------
    if matched:
        full = [m for m in matched if _get(m, "match_score", 0) >= 1.0]
        partial = [
            m for m in matched
            if 0 < _get(m, "match_score", 0) < 1.0
        ]
        lines.append("## 场景规则匹配（LLM 归因参考）")
        lines.append("")
        if full:
            lines.append("### ✅ 完全匹配")
            lines.append("")
            for m in full:
                lines.append(
                    f"- **{_get(m, 'scenario_name')} / {_get(m, 'rule_name')}** "
                    f"（置信度：{_get(m, 'confidence')}）"
                )
                lines.append(f"  - 结论：{_get(m, 'conclusion')}")
                lines.append(f"  - 建议：{_get(m, 'suggested_action')}")
            lines.append("")
        if partial:
            lines.append("### ⚠️ 部分匹配")
            lines.append("")
            for m in partial:
                score = _get(m, "match_score", 0)
                lines.append(
                    f"- {_get(m, 'scenario_name')} / {_get(m, 'rule_name')} "
                    f"(score={score:.2f})"
                )
            lines.append("")
        if not full and not partial:
            lines.append("未匹配到任何已知场景。")
            lines.append("")

    # ---------- LLM 归因分析 ----------
    if diagnose:
        lines.append("## LLM 归因分析")
        lines.append("")
        lines.append(diagnose.strip())
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
