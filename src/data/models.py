"""Data models for the diagnostic agent."""

from pydantic import BaseModel, Field


class MetricDataPoint(BaseModel):
    """单个指标数据点."""

    timestamp: int
    value: float
    metric_name: str = ""


class TimeSeriesData(BaseModel):
    """时间序列指标数据."""

    metric_name: str
    data_points: list[MetricDataPoint] = Field(default_factory=list)
    t1_value: float  # 基线值
    t2_value: float  # 当前值
    delta: float  # 变化量
    delta_ratio: float  # 变化率 (%)


class DimensionBreakdown(BaseModel):
    """维度下钻结果."""

    dimension_name: str
    dimension_value: str
    t1_value: float
    t2_value: float
    delta: float
    contribution_ratio: float  # 贡献占比 (%)


class LogEntry(BaseModel):
    """日志条目."""

    timestamp: int
    level: str  # INFO / WARN / ERROR
    message: str
    source: str = ""
    region: str = ""


class ChangeEvent(BaseModel):
    """变更事件."""

    timestamp: int
    change_type: str  # deployment / config / scaling
    description: str
    author: str = ""
    affected_services: list[str] = Field(default_factory=list)


class ContributionResult(BaseModel):
    """贡献度计算结果."""

    dimension_value: str
    contribution_score: float
    contribution_ratio: float  # %
    method: str = "lmdi"


class ConcentrationResult(BaseModel):
    """集中性判断结果."""

    is_concentrated: bool
    gini_coefficient: float
    top_contributors: list[dict] = Field(default_factory=list)
    threshold_used: float = 0.7
