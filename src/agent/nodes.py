"""Agent 节点定义 — Phase 2 版本

两阶段架构:
  Phase 1 (采集): init_plan → analyze_alert → agent_node ⇄ tool_node
                  → update_checklist → verify_completeness → (自由探索)
  Phase 2 (归因): match_scenarios → diagnose → END
"""

from __future__ import annotations

import json
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.prompts import DIAGNOSE_PROMPT, FREE_EXPLORE_PROMPT, SYSTEM_PROMPT
from src.knowledge.rule_matcher import RuleMatcher
from src.knowledge.runbook_loader import ChecklistItem, RunbookLoader

# ============================================================
# Phase 1: 数据采集节点
# ============================================================


def make_init_plan(runbook_dir: str = "runbooks"):
    """创建 init_plan 节点工厂

    功能：解析 analysis_plan.yaml → 生成 Checklist → 写入 State
    这是一个程序化节点，不涉及 LLM 调用。
    """
    loader = RunbookLoader(runbook_dir)

    def init_plan(state: dict) -> dict:
        alert = state["alert"]
        metric = alert.metric_name

        # 加载采集计划
        checklist_items = loader.load_analysis_plan(metric)

        if not checklist_items:
            # 没有预定义的 runbook，返回空 checklist，Agent 自由推理
            return {
                "checklist": [],
                "evidence_pool": {},
                "matched_scenarios": [],
                "phase": "collecting",
                "iteration": 0,
            }

        # 转为 dict 存入 State
        checklist = [
            {
                "id": item.id,
                "name": item.name,
                "priority": item.priority,
                "action": item.action,
                "params": item.params,
                "depends_on": item.depends_on,
                "description": item.description,
                "status": "pending",
            }
            for item in checklist_items
        ]

        # 生成初始引导消息
        meta = loader.load_meta(metric)
        metric_display = meta.display_name if meta else metric
        intro = (
            f"已加载 **{metric_display}** 的归因分析计划，"
            f"共 {len(checklist)} 个分析步骤 "
            f"(其中 {sum(1 for c in checklist if c['priority'] == 'must')} 个必要步骤)。"
        )

        return {
            "messages": [SystemMessage(content=intro)],
            "checklist": checklist,
            "evidence_pool": {},
            "matched_scenarios": [],
            "phase": "collecting",
            "iteration": 0,
        }

    return init_plan


def make_analyze_alert(llm):
    """创建 analyze_alert 节点 — 分析告警并启动归因

    修复 Phase 1 的 SystemMessage 重复问题：
    SystemMessage 只在这里设置一次，后续节点不再重复注入。
    """
    loader = RunbookLoader()

    def analyze_alert(state: dict) -> dict:
        alert = state["alert"]
        checklist = state.get("checklist", [])

        # 构建 System Prompt（包含 Checklist）
        checklist_text = ""
        if checklist:
            items = [
                ChecklistItem(
                    id=c["id"],
                    name=c["name"],
                    priority=c["priority"],
                    action=c["action"],
                    params=c.get("params", {}),
                    depends_on=c.get("depends_on", []),
                    description=c.get("description", ""),
                    status=c.get("status", "pending"),
                )
                for c in checklist
            ]
            checklist_text = "\n\n" + loader.format_checklist_status(items)

        system_content = SYSTEM_PROMPT + checklist_text

        # 告警描述
        alert_desc = (
            f"## 告警信息\n\n"
            f"- **告警ID**: {alert.alert_id}\n"
            f"- **指标**: {alert.metric_name}\n"
            f"- **级别**: {alert.severity}\n"
            f"- **描述**: {alert.description}\n"
            f"- **当前值**: {alert.current_value}\n"
            f"- **基线值**: {alert.baseline_value}\n"
            f"- **时间**: {alert.timestamp}\n"
        )

        return {
            "messages": [
                SystemMessage(content=system_content),
                HumanMessage(content=alert_desc),
            ],
        }

    return analyze_alert


def make_agent_node(llm, tools):
    """创建 agent_node 节点 — LLM 根据 Checklist 调用工具

    每次执行时动态更新 Checklist 状态到 Prompt 中，
    提示可并行执行的步骤。
    """
    model = llm.get_chat_model().bind_tools(tools)
    loader = RunbookLoader()

    def agent_node(state: dict) -> dict:
        checklist = state.get("checklist", [])
        iteration = state.get("iteration", 0)

        # 如果有 checklist，动态构建当前状态提示
        if checklist:
            items = [
                ChecklistItem(
                    id=c["id"],
                    name=c["name"],
                    priority=c["priority"],
                    action=c["action"],
                    params=c.get("params", {}),
                    depends_on=c.get("depends_on", []),
                    description=c.get("description", ""),
                    status=c.get("status", "pending"),
                )
                for c in checklist
            ]
            checklist_status = loader.format_checklist_status(items)

            # 注入 checklist 状态作为系统提示
            checklist_msg = SystemMessage(
                content=(
                    f"--- 当前分析进度 (第 {iteration + 1} 轮) ---\n\n"
                    f"{checklist_status}\n\n"
                    "请严格按照清单执行分析，优先完成所有 MUST 级别步骤。\n"
                    "每一步先输出 **Thought:** （你的推理过程），再执行工具调用。\n"
                    "当多个步骤可并行时，在一次响应中同时调用多个工具。"
                )
            )
            messages = state["messages"] + [checklist_msg]
        else:
            messages = state["messages"]

        # 调用 LLM
        response = model.invoke(messages)

        return {
            "messages": [response],
            "iteration": iteration + 1,
        }

    return agent_node


def update_checklist(state: dict) -> dict:
    """更新 Checklist 状态 + 写入 Evidence Pool

    这是一个程序化节点（不调用 LLM），功能：
    1. 从最近的消息中提取 tool_calls 和 tool 返回结果
    2. 匹配 checklist 中的步骤，标记为 done
    3. 将工具返回结果写入 evidence_pool（共享结果池）
    """
    checklist = state.get("checklist", [])
    evidence_pool = state.get("evidence_pool", {})

    # 提取最近一轮的 tool 调用和结果
    tool_calls_info = _extract_recent_tool_info(state["messages"])

    if not tool_calls_info:
        return {}

    # 匹配 checklist 中的步骤
    for item in checklist:
        if item["status"] == "done":
            continue

        for tc_name, tc_args, tc_result in tool_calls_info:
            if _matches_step(tc_name, tc_args, item):
                item["status"] = "done"

                # 结果写入 Evidence Pool
                evidence_pool[item["id"]] = {
                    "tool": tc_name,
                    "args": tc_args,
                    "result": tc_result,
                    "parsed": _parse_tool_result(tc_result),
                    "timestamp": datetime.now().isoformat(),
                }
                break

    # 自由探索阶段的工具调用也写入 evidence_pool（不在 checklist 中的调用）
    for tc_name, tc_args, tc_result in tool_calls_info:
        # 检查该调用是否已被 checklist 匹配
        already_matched = any(
            _matches_step(tc_name, tc_args, item)
            for item in checklist
            if item["status"] == "done"
        )
        if not already_matched:
            # 自由探索的调用，用工具名+参数生成唯一 key
            extra_id = f"extra_{tc_name}_{len(evidence_pool)}"
            evidence_pool[extra_id] = {
                "tool": tc_name,
                "args": tc_args,
                "result": tc_result,
                "parsed": _parse_tool_result(tc_result),
                "timestamp": datetime.now().isoformat(),
            }

    return {
        "checklist": checklist,
        "evidence_pool": evidence_pool,
    }


def verify_completeness(state: dict) -> dict:
    """验证必要步骤是否全部完成

    程序化节点，通过 phase 字段控制路由：
    - phase = "collecting": 有遗漏 must 步骤，回到 agent_node 继续
    - phase = "exploring": must 步骤全完成，进入自由探索模式
    - phase = "diagnosing": 采集结束，进入 Phase 2 归因
    """
    checklist = state.get("checklist", [])
    iteration = state.get("iteration", 0)
    phase = state.get("phase", "collecting")

    # 如果已经处于自由探索阶段，说明 agent 已经完成了自由探索
    # （上一轮 agent_node 没有 tool_calls，走到 verify → 说明 agent 主动结束）
    if phase == "exploring":
        return {"phase": "diagnosing"}

    if not checklist:
        # 没有 checklist（自由推理模式），检查是否有足够工具调用
        tool_count = sum(
            1
            for msg in state["messages"]
            if hasattr(msg, "tool_calls") and msg.tool_calls
        )
        if tool_count >= 3:
            return {"phase": "diagnosing"}
        return {"iteration": iteration}

    pending_must = [
        item for item in checklist if item["priority"] == "must" and item["status"] == "pending"
    ]

    if not pending_must:
        # 所有 must 步骤完成，进入自由探索模式
        return {
            "messages": [SystemMessage(content=FREE_EXPLORE_PROMPT)],
            "phase": "exploring",
        }

    # 防止无限循环
    if iteration >= 10:
        return {"phase": "exploring"}

    # 有遗漏，构造提醒消息
    loader = RunbookLoader()
    items = [
        ChecklistItem(
            id=c["id"],
            name=c["name"],
            priority=c["priority"],
            action=c["action"],
            params=c.get("params", {}),
            depends_on=c.get("depends_on", []),
            description=c.get("description", ""),
            status=c.get("status", "pending"),
        )
        for c in checklist
    ]
    reminder = loader.format_pending_must_reminder(items)

    return {
        "messages": [SystemMessage(content=reminder)],
        "iteration": iteration,
    }


# ============================================================
# Phase 2: 场景匹配 + 报告生成
# ============================================================


def make_match_scenarios(runbook_dir: str = "runbooks"):
    """创建 match_scenarios 节点 — 程序化场景规则匹配"""
    matcher = RuleMatcher(runbook_dir)

    def match_scenarios(state: dict) -> dict:
        alert = state["alert"]
        evidence_pool = state.get("evidence_pool", {})

        matched = matcher.match_all_scenarios(alert.metric_name, evidence_pool)

        # 转为 dict 存入 State
        matched_dicts = [
            {
                "scenario": r.scenario,
                "scenario_name": r.scenario_name,
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "confidence": r.confidence,
                "conclusion": r.conclusion,
                "suggested_action": r.suggested_action,
                "match_score": r.match_score,
                "matched_conditions": r.matched_conditions,
                "unmatched_conditions": r.unmatched_conditions,
            }
            for r in matched
        ]

        # 格式化匹配结果注入消息
        match_text = matcher.format_match_results(matched)
        return {
            "matched_scenarios": matched_dicts,
            "messages": [SystemMessage(content=match_text)],
        }

    return match_scenarios


def make_diagnose(llm):
    """创建 diagnose 节点 — LLM 综合 evidence + 规则参考进行归因判断

    规则匹配结果作为参考依据注入，LLM 做最终归因推理：
    - 有匹配规则 → LLM 验证是否合理，可采纳/修正/否决
    - 无匹配规则 → LLM 自由推理，可能发现新故障模式
    """
    model = llm.get_chat_model()

    def diagnose(state: dict) -> dict:
        alert = state["alert"]
        evidence_pool = state.get("evidence_pool", {})
        matched_scenarios = state.get("matched_scenarios", [])

        # 构建归因判断 Prompt
        evidence_summary = _format_evidence_summary(evidence_pool)
        scenario_summary = _format_scenario_summary(matched_scenarios)

        diagnose_prompt = DIAGNOSE_PROMPT.format(
            alert_id=alert.alert_id,
            metric_name=alert.metric_name,
            description=alert.description,
            current_value=alert.current_value,
            baseline_value=alert.baseline_value,
            evidence_summary=evidence_summary,
            scenario_summary=scenario_summary,
        )

        # P0-3: 不传完整消息历史，只传精简的归因 Prompt。
        # evidence_summary / scenario_summary 已包含所有必要上下文。
        response = model.invoke([HumanMessage(content=diagnose_prompt)])

        return {"messages": [response]}

    return diagnose


# ============================================================
# 辅助函数
# ============================================================


def _extract_recent_tool_info(
    messages: list,
) -> list[tuple[str, dict, str]]:
    """从消息列表中提取最近一轮的工具调用信息

    Returns:
        [(tool_name, tool_args, tool_result), ...]
    """
    results = []

    # 从后往前找最近的 AI message (with tool_calls) 和对应的 tool results
    tool_results_map: dict[str, str] = {}

    for msg in reversed(messages):
        # ToolMessage: 工具返回结果
        if msg.type == "tool":
            tool_results_map[msg.tool_call_id] = msg.content

        # AIMessage with tool_calls: 工具调用请求
        elif msg.type == "ai" and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "")
                tc_name = tc.get("name", "")
                tc_args = tc.get("args", {})
                tc_result = tool_results_map.get(tc_id, "")
                results.append((tc_name, tc_args, tc_result))
            break  # 只处理最近一轮

    return results


def _matches_step(tool_name: str, tool_args: dict, step: dict) -> bool:
    """检查一次工具调用是否匹配 checklist 中的某个步骤

    匹配逻辑：
    1. 工具名称必须匹配
    2. step 中定义的 params 的每个 key-value 都必须在 tool_args 中出现
    """
    if tool_name != step["action"]:
        return False

    step_params = step.get("params", {})
    for key, value in step_params.items():
        if str(tool_args.get(key, "")) != str(value):
            return False

    return True


EVIDENCE_MARKER = "===EVIDENCE==="


def _parse_tool_result(result_str: str) -> dict:
    """从工具返回中解析结构化证据。

    约定：所有工具在返回文本末尾追加一个证据块：
        ...人类可读文本...
        ===EVIDENCE===
        {"key": value, ...}

    解析方式：按 marker split，取后半段 JSON.loads。
    命中不了就返回 {}，不做兜底的文本正则猜测——
    规则匹配宁可不命中也不能命中错误字段。
    """
    if not isinstance(result_str, str) or EVIDENCE_MARKER not in result_str:
        return {}

    try:
        json_str = result_str.split(EVIDENCE_MARKER, 1)[1].strip()
        data = json.loads(json_str)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IndexError):
        return {}


def _format_evidence_summary(evidence_pool: dict) -> str:
    """格式化 Evidence Pool 为报告摘要"""
    if not evidence_pool:
        return "暂无分析数据。"

    lines = []
    for step_id, evidence in evidence_pool.items():
        tool = evidence.get("tool", "unknown")
        result = str(evidence.get("result", ""))
        # 剥离给规则引擎用的 JSON 证据块，只保留人类可读部分
        if EVIDENCE_MARKER in result:
            result = result.split(EVIDENCE_MARKER, 1)[0].rstrip()
        if len(result) > 500:
            result = result[:500] + "..."
        lines.append(f"### {step_id}\n- 工具: {tool}\n- 结果: {result}\n")

    return "\n".join(lines)


def _format_scenario_summary(matched_scenarios: list[dict]) -> str:
    """格式化场景匹配结果为报告摘要"""
    if not matched_scenarios:
        return "未匹配到已知故障场景。"

    lines = []
    full_matches = [s for s in matched_scenarios if s.get("match_score", 0) == 1.0]
    partial_matches = [s for s in matched_scenarios if 0 < s.get("match_score", 0) < 1.0]

    if full_matches:
        lines.append("### 完全匹配的场景")
        for s in full_matches:
            lines.append(
                f"- **{s['scenario_name']} / {s['rule_name']}** "
                f"(置信度: {s['confidence']})"
            )
            lines.append(f"  结论: {s['conclusion']}")
            lines.append(f"  建议: {s['suggested_action']}")

    if partial_matches:
        lines.append("### 部分匹配的场景（供参考）")
        for s in partial_matches:
            lines.append(
                f"- **{s['scenario_name']} / {s['rule_name']}** "
                f"(匹配度: {s['match_score']:.0%})"
            )

    return "\n".join(lines)
