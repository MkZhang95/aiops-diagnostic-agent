"""集成测试 — 端到端场景验证

验证 Agent 在模拟数据场景下的完整执行流程：
  init_plan → 数据采集 → 自由探索 → 场景匹配 → 归因判断

标记为 integration，需要 LLM API 才能运行：
  pytest -m integration
"""

import time

import pytest

from src.agent import build_graph
from src.agent.state import AlertEvent
from src.data import DataSimulator, list_scenarios
from src.llm import get_llm
from src.tools import get_all_tools


def _make_alert_event(alert_dict: dict) -> AlertEvent:
    """将场景 alert dict 转为 AlertEvent"""
    return AlertEvent(
        alert_id=alert_dict.get("alert_id", f"test_{int(time.time())}"),
        metric_name=alert_dict["metric_name"],
        severity=alert_dict.get("severity", "warning"),
        description=alert_dict.get("description", ""),
        timestamp=str(alert_dict.get("timestamp", "")),
        current_value=alert_dict.get("current_value", 0),
        baseline_value=alert_dict.get("baseline_value", 0),
        tags=alert_dict.get("tags", {}),
    )


def _run_scenario(scenario_name: str) -> dict:
    """执行一个完整的场景分析，返回最终 state"""
    simulator = DataSimulator(scenario_name)
    alert_event = _make_alert_event(simulator.alert)

    llm = get_llm()
    tools = get_all_tools(simulator)
    graph = build_graph(llm, tools=tools)

    result = graph.invoke({
        "messages": [],
        "alert": alert_event,
        "phase": "collecting",
        "checklist": [],
        "evidence_pool": {},
        "matched_scenarios": [],
        "evidences": [],
        "root_causes": [],
        "iteration": 0,
    })

    return result


@pytest.mark.integration
class TestScenarioPlaySuccessRate:
    """场景 1: 播放成功率下降 — CDN 华南节点配置变更"""

    def test_full_run(self):
        result = _run_scenario("play_success_rate_drop")

        # 1. 流程完成：phase 应为 diagnosing
        assert result.get("phase") == "diagnosing"

        # 2. Evidence Pool 非空：至少采集了数据
        evidence_pool = result.get("evidence_pool", {})
        assert len(evidence_pool) >= 3, f"evidence 不足: {len(evidence_pool)}"

        # 3. 消息列表中有工具调用
        tool_call_count = sum(
            1
            for msg in result["messages"]
            if hasattr(msg, "tool_calls") and msg.tool_calls
        )
        assert tool_call_count >= 3, f"工具调用次数不足: {tool_call_count}"

        # 4. 最终报告非空（最后一条 AI 消息应是归因报告）
        last_ai_msgs = [
            msg for msg in result["messages"]
            if hasattr(msg, "content") and msg.content and len(msg.content) > 100
        ]
        assert len(last_ai_msgs) > 0, "未生成归因报告"


@pytest.mark.integration
class TestScenarioBufferingRate:
    """场景 2: 卡顿率上升 — 转码配置调整"""

    def test_full_run(self):
        result = _run_scenario("buffering_rate_rise")

        assert result.get("phase") == "diagnosing"

        evidence_pool = result.get("evidence_pool", {})
        assert len(evidence_pool) >= 3

        tool_call_count = sum(
            1
            for msg in result["messages"]
            if hasattr(msg, "tool_calls") and msg.tool_calls
        )
        assert tool_call_count >= 3

        last_ai_msgs = [
            msg for msg in result["messages"]
            if hasattr(msg, "content") and msg.content and len(msg.content) > 100
        ]
        assert len(last_ai_msgs) > 0


@pytest.mark.integration
class TestScenarioFirstFrameLatency:
    """场景 3: 首帧耗时劣化 — DNS 解析异常"""

    def test_full_run(self):
        result = _run_scenario("first_frame_latency_degradation")

        assert result.get("phase") == "diagnosing"

        evidence_pool = result.get("evidence_pool", {})
        assert len(evidence_pool) >= 3

        tool_call_count = sum(
            1
            for msg in result["messages"]
            if hasattr(msg, "tool_calls") and msg.tool_calls
        )
        assert tool_call_count >= 3

        last_ai_msgs = [
            msg for msg in result["messages"]
            if hasattr(msg, "content") and msg.content and len(msg.content) > 100
        ]
        assert len(last_ai_msgs) > 0


class TestScenarioData:
    """验证场景数据完整性（不需要 LLM）"""

    def test_all_scenarios_loadable(self):
        """所有场景都能成功加载"""
        for name in list_scenarios():
            simulator = DataSimulator(name)
            alert = simulator.alert
            assert "metric_name" in alert
            assert "current_value" in alert

    def test_alert_event_conversion(self):
        """alert dict 能正确转为 AlertEvent"""
        for name in list_scenarios():
            simulator = DataSimulator(name)
            event = _make_alert_event(simulator.alert)
            assert event.metric_name
            assert event.current_value != event.baseline_value

    def test_scenarios_have_expected_root_cause(self):
        """所有场景都有预期根因"""
        from src.data.scenarios import SCENARIOS

        for name, data in SCENARIOS.items():
            assert "expected_root_cause" in data, f"{name} 缺少 expected_root_cause"
