"""Runbook 加载器 — 解析 analysis_plan.yaml 并生成 Checklist"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ChecklistItem:
    """Checklist 中的单个分析步骤"""

    id: str
    name: str
    priority: str  # must / should / show
    action: str  # 对应的 tool 名称
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)
    description: str = ""
    status: str = "pending"  # pending / done / skipped

    def is_done(self) -> bool:
        return self.status == "done"

    def is_pending(self) -> bool:
        return self.status == "pending"


@dataclass
class RunbookMeta:
    """指标元信息"""

    metric: str
    display_name: str
    description: str = ""
    related_metrics: list[str] = field(default_factory=list)


class RunbookLoader:
    """加载和管理 Runbook 文件"""

    def __init__(self, runbook_dir: str = "runbooks"):
        self.runbook_dir = runbook_dir

    def load_meta(self, metric: str) -> RunbookMeta | None:
        """加载指标元信息"""
        meta_path = os.path.join(self.runbook_dir, metric, "_meta.yaml")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return RunbookMeta(
            metric=data.get("metric", metric),
            display_name=data.get("display_name", metric),
            description=data.get("description", ""),
            related_metrics=data.get("related_metrics", []),
        )

    def load_analysis_plan(self, metric: str) -> list[ChecklistItem]:
        """加载采集计划，生成 Checklist

        Args:
            metric: 指标名称，对应 runbooks/{metric}/analysis_plan.yaml

        Returns:
            ChecklistItem 列表，所有步骤状态初始化为 pending
        """
        plan_path = os.path.join(self.runbook_dir, metric, "analysis_plan.yaml")
        if not os.path.exists(plan_path):
            return []

        with open(plan_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        checklist = []
        for step in data.get("steps", []):
            item = ChecklistItem(
                id=step["id"],
                name=step["name"],
                priority=step.get("priority", "should"),
                action=step["action"],
                params=step.get("params", {}),
                depends_on=step.get("depends_on", []),
                used_by=step.get("used_by", []),
                description=step.get("description", ""),
                status="pending",
            )
            checklist.append(item)

        return checklist

    def get_available_metrics(self) -> list[str]:
        """获取所有有 runbook 的指标列表"""
        metrics = []
        if not os.path.exists(self.runbook_dir):
            return metrics
        for entry in os.listdir(self.runbook_dir):
            plan_path = os.path.join(self.runbook_dir, entry, "analysis_plan.yaml")
            if os.path.isdir(os.path.join(self.runbook_dir, entry)) and os.path.exists(
                plan_path
            ):
                metrics.append(entry)
        return metrics

    def get_scenario_rule_files(self, metric: str) -> list[str]:
        """获取某指标下所有场景规则文件路径"""
        metric_dir = os.path.join(self.runbook_dir, metric)
        if not os.path.exists(metric_dir):
            return []
        return sorted(glob.glob(os.path.join(metric_dir, "rules_*.yaml")))

    def format_checklist_status(
        self, checklist: list[ChecklistItem]
    ) -> str:
        """将 Checklist 格式化为 Prompt 可读的文本，包含并发提示

        Args:
            checklist: 当前 checklist 状态

        Returns:
            格式化后的文本，可直接注入 System Prompt
        """
        lines = ["## 归因分析清单\n"]

        # 状态统计
        done_count = sum(1 for item in checklist if item.is_done())
        total_count = len(checklist)
        must_done = sum(
            1
            for item in checklist
            if item.priority == "must" and item.is_done()
        )
        must_total = sum(1 for item in checklist if item.priority == "must")
        lines.append(
            f"进度: {done_count}/{total_count} 完成 "
            f"(必要步骤: {must_done}/{must_total})\n"
        )

        # 逐项列出（同时给出明确的 action + params，避免模型凭空猜测参数名）
        for item in checklist:
            icon = "✅" if item.is_done() else "⬜"
            tag = f"[{item.priority.upper()}]"
            lines.append(f"{icon} {tag} {item.name}")
            if item.action:
                if item.params:
                    params_str = ", ".join(
                        f"{k}={v}" for k, v in item.params.items()
                    )
                    lines.append(f"    → 调用: `{item.action}({params_str})`")
                else:
                    lines.append(f"    → 调用: `{item.action}()`")

        # 分析可并行步骤
        ready_steps = self._get_ready_steps(checklist)
        if len(ready_steps) > 1:
            names = "、".join(s.name for s in ready_steps)
            lines.append(f"\n⚡ 以下步骤无依赖关系，可并行执行: {names}")
            lines.append("请在一次响应中同时调用这些工具以提升效率。")
        elif len(ready_steps) == 1:
            step = ready_steps[0]
            lines.append(f"\n📌 建议下一步: {step.name} — {step.description}")

        return "\n".join(lines)

    def _get_ready_steps(
        self, checklist: list[ChecklistItem]
    ) -> list[ChecklistItem]:
        """获取当前可执行的步骤（pending 且所有依赖已完成）"""
        done_ids = {item.id for item in checklist if item.is_done()}
        ready = []
        for item in checklist:
            if not item.is_pending():
                continue
            if all(dep in done_ids for dep in item.depends_on):
                ready.append(item)
        return ready

    def format_pending_must_reminder(
        self, checklist: list[ChecklistItem]
    ) -> str:
        """生成未完成 must 步骤的提醒文本"""
        pending_must = [
            item
            for item in checklist
            if item.priority == "must" and item.is_pending()
        ]
        if not pending_must:
            return ""

        lines = ["⚠️ 以下必要分析步骤尚未完成，请继续执行：\n"]
        for item in pending_must:
            lines.append(f"  - **{item.name}**: {item.description}")
            if item.params:
                params_str = ", ".join(f"{k}={v}" for k, v in item.params.items())
                lines.append(f"    参数: {params_str}")
        return "\n".join(lines)
