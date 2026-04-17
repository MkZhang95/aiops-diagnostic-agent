"""Tool C4: 事件匹配 — 判断时间窗口内是否有与异常吻合的变更事件.

比 query_events 多一步：按关键词/服务/类型精确匹配变更，并判断变更是否
落在异常窗口内，用于验证「是否是发版/配置变更引发」这类假设。
"""

import json

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


def _evidence_block(payload: dict) -> str:
    return "\n\n===EVIDENCE===\n" + json.dumps(payload, ensure_ascii=False)


@tool
def match_events(
    keywords: str = "",
    event_type: str = "",
    service: str = "",
) -> str:
    """在异常窗口内匹配特定类型/关键词的变更事件。

    与 query_events 的区别：query_events 偏列表/统计，match_events 偏命中判定，
    返回 `matched`（是否有命中）供规则直接使用。

    输入:
        keywords: 可选，在 description 中匹配的关键词，逗号分隔（任一命中即视为匹配）
        event_type: 可选，事件类型过滤（deployment/config/scaling）
        service: 可选，服务名过滤

    输出: 命中事件列表 + 是否命中 + 命中数。
    """
    if _simulator is None:
        return "错误：数据模拟器未初始化。" + _evidence_block({})

    changes = _simulator.get_changes(0, 3600, service or None)
    if event_type:
        changes = [ch for ch in changes if ch.change_type == event_type]

    kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if kw_list:
        changes = [
            ch for ch in changes
            if any(kw in ch.description.lower() for kw in kw_list)
        ]

    if not changes:
        payload = {
            "keywords": kw_list,
            "event_type": event_type,
            "service": service,
            "matched": False,
            "match_count": 0,
        }
        return "未命中任何变更事件。" + _evidence_block(payload)

    lines = ["命中的变更事件:"]
    matched = []
    for ch in changes:
        lines.append(
            f"  [{ch.change_type.upper()}] {ch.description}\n"
            f"         执行者: {ch.author} | 影响服务: {', '.join(ch.affected_services)}"
        )
        matched.append({
            "type": ch.change_type,
            "description": ch.description,
            "author": ch.author,
            "services": list(ch.affected_services),
        })
    lines.append(f"\n  共命中 {len(matched)} 条")

    payload = {
        "keywords": kw_list,
        "event_type": event_type,
        "service": service,
        "matched": True,
        "match_count": len(matched),
        "events": matched,
    }
    return "\n".join(lines) + _evidence_block(payload)
