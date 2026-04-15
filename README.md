# AIOps Diagnostic Agent

基于 LangGraph 构建的 AIOps 智能归因分析 Agent，采用 **Checklist-Driven** 架构，将业务专家的归因经验通过声明式 YAML Runbook 编码，实现结构化、可审计的指标异常归因。

## 核心特性

- **Checklist-Driven 执行**：归因分析步骤由 YAML 采集计划定义，程序化追踪完成状态，保证不遗漏关键分析
- **采集层与规则层分离**：`analysis_plan.yaml` 统一管理分析步骤（去重），`rules_*.yaml` 独立管理场景匹配规则
- **Evidence Pool 共享结果池**：同一分析步骤只执行一次，多个场景共享结果，避免重复查数
- **并发执行**：通过 `depends_on` 声明步骤间依赖，无依赖步骤支持并发执行
- **三层完整性保障**：Prompt 引导 → 程序化追踪 → 兜底校验，must 步骤 100% 执行
- **ReAct 推理可见**：显式输出 Thought → Action → Observation 过程，便于调试和审计
- **多 LLM 支持**：Claude / OpenAI / 智谱 AI

## 架构

```
Phase 1: 数据采集（Checklist 驱动）
  init_plan → analyze_alert → agent_node ⇄ tool_node
                                ↓
                          update_checklist
                                ↓
                        verify_completeness
                          (must全完成?)
                                ↓
Phase 2: 场景匹配 + 报告
  match_scenarios → generate_report → END
```

### 文件结构

```
├── cli.py                          # CLI 入口
├── runbooks/                       # 归因知识库（业务专家维护）
│   └── play_success_rate/
│       ├── _meta.yaml              # 指标元信息
│       ├── analysis_plan.yaml      # 采集计划（去重后的所有分析步骤）
│       ├── rules_cdn_fault.yaml    # CDN 故障场景规则
│       ├── rules_isp_fault.yaml    # 运营商故障场景规则
│       ├── rules_client_bug.yaml   # 客户端 Bug 场景规则
│       └── rules_network_issue.yaml# 网络问题场景规则
├── src/
│   ├── agent/
│   │   ├── state.py                # Agent 状态定义
│   │   ├── graph.py                # LangGraph 流程图
│   │   ├── nodes.py                # 节点实现
│   │   └── prompts.py              # Prompt 模板
│   ├── knowledge/                  # 知识管理模块
│   │   ├── runbook_loader.py       # YAML 加载 + Checklist 生成
│   │   └── rule_matcher.py         # 场景规则匹配引擎
│   ├── llm/                        # LLM 适配层
│   │   ├── base.py
│   │   ├── claude.py
│   │   ├── openai.py
│   │   └── zhipu.py
│   ├── tools/                      # 分析工具集
│   │   ├── query_metrics.py
│   │   ├── drill_down.py
│   │   ├── contribution.py         # LMDI + 结构贡献分解
│   │   ├── concentration.py        # GINI 系数
│   │   ├── compare_points.py
│   │   ├── search_logs.py
│   │   └── check_changes.py
│   └── data/                       # 模拟数据
│       ├── models.py
│       ├── scenarios.py
│       └── simulator.py
└── tests/
    └── test_tools.py
```

## 快速开始

### 安装

```bash
pip install -e .
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

### 运行

```bash
# 使用 Claude 分析播放成功率下降场景
python cli.py --model claude --scenario play_success_rate_drop

# 使用智谱 AI
python cli.py --model zhipu --scenario play_success_rate_drop
```

## 如何添加新场景

### 1. 为新指标创建目录

```bash
mkdir -p runbooks/your_metric_name
```

### 2. 创建指标元信息

```yaml
# runbooks/your_metric_name/_meta.yaml
metric: your_metric_name
display_name: "你的指标名"
description: "指标描述"
related_metrics: [related_metric_1, related_metric_2]
```

### 3. 创建采集计划

```yaml
# runbooks/your_metric_name/analysis_plan.yaml
metric: your_metric_name
steps:
  - id: step_1
    name: "步骤描述"
    priority: must          # must/should/show
    action: query_metrics   # 对应工具名
    params: { metric: your_metric_name }
    depends_on: []          # 依赖的步骤 id
    used_by: [scenario_1]   # 被哪些场景使用
```

### 4. 创建场景规则

```yaml
# runbooks/your_metric_name/rules_your_scenario.yaml
scenario: your_scenario
display_name: "场景名"
required_evidence: [step_1, step_2]
rules:
  - id: rule_1
    name: "规则名"
    conditions:
      - step: step_1
        field: rate_of_change
        op: ">"
        value: 0.2
    confidence: high
    conclusion: "结论描述"
    suggested_action: "建议操作"
```

## 设计理念

### 从 ProcessConfig 到 Checklist-Driven Agent

本项目源自对传统配置化归因系统的 Agent 化改造：

| 传统配置化系统 | Agent 系统 |
|---|---|
| ProcessConfig JSON 管理归因路径 | analysis_plan.yaml + rules_*.yaml |
| 程序遍历树节点调用函数 | Agent 按 Checklist 调用工具 |
| 多场景树展平去重 | 采集计划天然去重 |
| 并发查数 | depends_on 声明 + 并发工具调用 |
| 结果回填各场景 | Evidence Pool 共享结果池 |
| 规则匹配 | 结构化条件程序匹配 |
| 只走预定义路径 | 预定义路径 + LLM 灵活扩展 |

核心优势：**保留了配置化系统的确定性和完整性，同时获得了 LLM 的灵活推理能力**。

## License

MIT
