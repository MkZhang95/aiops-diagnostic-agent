"""Agent State 定义 — Phase 2 版本

新增:
- checklist: 分析步骤清单（Checklist-Driven 执行）
- evidence_pool: 共享结果池（采集层与规则层共享数据）
- matched_scenarios: 场景匹配结果
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# ============================================================
# Pydantic 模型（用于结构化数据）
# ============================================================


class AlertEvent(BaseModel):
    """告警事件"""

    alert_id: str = Field(description="告警ID")
    metric_name: str = Field(description="指标名称")
    severity: str = Field(description="告警级别: critical/warning/info")
    description: str = Field(description="告警描述")
    timestamp: str = Field(description="告警触发时间")
    current_value: float = Field(description="当前指标值")
    baseline_value: float = Field(description="基线值")
    tags: dict[str, str] = Field(default_factory=dict, description="标签")


class Evidence(BaseModel):
    """归因证据"""

    source: str = Field(description="证据来源工具")
    finding: str = Field(description="发现描述")
    confidence: str = Field(default="medium", description="置信度: high/medium/low")
    data: dict[str, Any] = Field(default_factory=dict, description="原始数据")


class RootCause(BaseModel):
    """根因"""

    category: str = Field(description="根因分类")
    description: str = Field(description="根因描述")
    confidence: str = Field(description="置信度: high/medium/low")
    evidences: list[str] = Field(default_factory=list, description="支撑证据")
    suggested_action: str = Field(default="", description="建议处理方式")


# ============================================================
# Checklist 相关（Phase 2 新增）
# ============================================================


class ChecklistItemState(BaseModel):
    """Checklist 中单个步骤的状态（存储在 State 中的版本）"""

    id: str
    name: str
    priority: str  # must / should / show
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    description: str = ""
    status: str = "pending"  # pending / done / skipped


class MatchedScenario(BaseModel):
    """匹配到的场景"""

    scenario: str
    scenario_name: str
    rule_id: str
    rule_name: str
    confidence: str
    conclusion: str
    suggested_action: str
    match_score: float
    matched_conditions: list[str] = Field(default_factory=list)
    unmatched_conditions: list[str] = Field(default_factory=list)


# ============================================================
# Agent State
# ============================================================


class AgentState(TypedDict):
    """Agent 状态定义

    Phase 2 架构：
    - messages: LangGraph 消息列表（自动合并）
    - alert: 当前告警事件
    - phase: 当前阶段 (collecting / exploring / diagnosing)
    - checklist: 分析步骤清单（Checklist-Driven）
    - evidence_pool: 共享结果池（step_id → 结果）
    - matched_scenarios: 场景匹配结果
    - evidences: 归因证据（兼容 Phase 1）
    - root_causes: 根因列表
    - iteration: 当前迭代次数
    """

    messages: Annotated[list[AnyMessage], add_messages]
    alert: AlertEvent
    phase: str  # collecting / exploring / diagnosing
    checklist: list[dict]  # ChecklistItemState 序列化后的 dict list
    evidence_pool: dict[str, Any]
    matched_scenarios: list[dict]  # MatchedScenario 序列化后的 dict list
    evidences: list[Evidence]
    root_causes: list[RootCause]
    iteration: int
    tool_calls_valid: bool
