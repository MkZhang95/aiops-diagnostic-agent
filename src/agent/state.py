"""Agent state definition for LangGraph."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# --- Pydantic models for structured data ---


class AlertEvent(BaseModel):
    """告警事件."""

    metric_name: str
    severity: str = "critical"
    current_value: float = 0.0
    baseline_value: float = 0.0
    timestamp: int = 0
    service: str = ""
    region: str = ""
    filters: dict = Field(default_factory=dict)
    description: str = ""


class Evidence(BaseModel):
    """分析过程中收集的证据."""

    tool_name: str
    input_params: dict
    output_data: str
    summary: str
    timestamp: int = 0


class RootCause(BaseModel):
    """根因结论."""

    description: str
    confidence_score: float = 0.0
    supporting_evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)


# --- LangGraph Agent State ---


class AgentState(TypedDict):
    """LangGraph Agent 状态定义.

    对应原系统的 ProcessConfig + 请求体 + 中间结果。
    """

    # 输入
    alert: dict

    # LangGraph 消息（LLM 对话历史）
    messages: Annotated[list, add_messages]

    # 推理控制
    current_step: int
    max_steps: int

    # 中间证据收集
    evidence: list[dict]

    # 最终输出
    root_causes: list[dict]
    report: str
    status: str  # "running" | "completed" | "failed" | "max_steps_reached"
