# AIOps Diagnostic Agent — 项目规划文档

## 1. 项目定位

### 一句话描述

基于 LangGraph 的 AIOps 智能归因 Agent：输入一条告警事件，Agent 自动执行多步根因分析（指标查询 → 维度下钻 → 贡献度计算 → 集中性判断 → 场景匹配 → 报告生成），最终输出结构化的归因诊断报告。

### 与原始项目的关系

本项目是对字节跳动 `rootcause_http` NVQOS 归因系统的 **Agent 化重新实现**。原系统采用"配置驱动 + FuncMap 分发 + 并发线程"的编排模式，本项目将其升级为 **LLM Agent 驱动的智能编排**：

| 维度 | 原系统 | Agent 版本 |
|---|---|---|
| 编排方式 | ProcessConfig 配置驱动，固定流程 | LLM Agent 动态规划，ReAct 推理循环 |
| 工具选择 | FuncMap 映射表，配置指定函数名 | Agent 基于上下文自主选择 Tool |
| 场景匹配 | Must/Show 树的递归规则匹配 | Agent 综合分析证据后推理判断 |
| 结论生成 | 模板化拼装 ShortMsg/ShowDetail | LLM 生成可读的自然语言归因报告 |
| 扩展方式 | 新增 FuncMap 条目 + 修改配置 | 新增 Tool + 更新 Tool 描述即可 |

### 项目目标

1. **展示 Agent 架构能力**：ReAct loop、Tool Use、多步推理、状态管理
2. **展示业务理解深度**：AIOps 归因的完整业务逻辑，不是玩具 demo
3. **展示工程质量**：多模型支持、模块化设计、可测试、文档完善

---

## 2. 技术选型

| 组件 | 选型 | 理由 |
|---|---|---|
| **语言** | Python 3.11+ | LangGraph 生态、面试主流 |
| **Agent 框架** | LangGraph | 市场认可度最高，状态图模型适合多步归因 |
| **LLM 接口** | 抽象层 + 多模型支持 | 默认 Claude，可切换 OpenAI GPT、本地模型 |
| **数据层** | 模拟数据生成器 | 模拟 NVQOS 指标、日志、变更事件 |
| **前端** | CLI + Markdown 报告 | 快速出成果，后续可加 Streamlit |
| **包管理** | uv 或 poetry | 现代 Python 项目标准 |

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    CLI Interface                     │
│           (告警输入 → 交互式诊断 → 报告输出)             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              LangGraph Agent (核心)                   │
│                                                      │
│  ┌─────────┐    ┌──────────┐    ┌────────────┐      │
│  │ Planner │───▶│ Executor │───▶│ Evaluator  │      │
│  │ (规划)   │    │ (执行工具) │    │ (评估/继续?) │      │
│  └─────────┘    └──────────┘    └────────────┘      │
│       ▲                                │             │
│       └────────────────────────────────┘             │
│                  ReAct Loop                          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   Tool Layer                         │
│                                                      │
│  ┌──────────────┐  ┌───────────────┐                │
│  │ query_metrics│  │ drill_down    │                │
│  │ (指标查询)    │  │ (维度下钻)     │                │
│  ├──────────────┤  ├───────────────┤                │
│  │ compute_     │  │ check_        │                │
│  │ contribution │  │ concentration │                │
│  │ (贡献度计算)  │  │ (集中性判断)   │                │
│  ├──────────────┤  ├───────────────┤                │
│  │ search_logs  │  │ check_changes │                │
│  │ (日志搜索)    │  │ (变更事件检查) │                │
│  ├──────────────┤  ├───────────────┤                │
│  │ generate_    │  │ compare_      │                │
│  │ report       │  │ time_points   │                │
│  │ (报告生成)    │  │ (两点对比)     │                │
│  └──────────────┘  └───────────────┘                │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 Data Layer (模拟)                     │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │ Metrics    │  │ Logs       │  │ Changes    │    │
│  │ Simulator  │  │ Simulator  │  │ Simulator  │    │
│  └────────────┘  └────────────┘  └────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 3.2 LangGraph 状态图设计

这是项目的核心——Agent 的推理流程用 LangGraph 的 StateGraph 实现：

```
                    ┌──────────┐
                    │  START   │
                    │ (接收告警) │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ analyze  │  ← 分析告警上下文，规划诊断步骤
                    │ _alert   │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
              ┌────▶│ execute  │  ← 调用工具（查指标/下钻/算贡献度...）
              │     │ _tool    │
              │     └────┬─────┘
              │          │
              │     ┌────▼─────┐
              │     │ evaluate │  ← 评估结果：是否找到根因？需要更多信息？
              │     │ _result  │
              │     └────┬─────┘
              │          │
              │    ┌─────┴──────┐
              │    │            │
              │  需要更多      已找到根因
              │  信息/下钻      或达到上限
              │    │            │
              └────┘       ┌────▼─────┐
                           │ generate │  ← 生成归因诊断报告
                           │ _report  │
                           └────┬─────┘
                                │
                           ┌────▼─────┐
                           │   END    │
                           └──────────┘
```

### 3.3 对比原系统的映射关系

| 原系统组件 | Agent 版本对应 | 变化 |
|---|---|---|
| `ProcessConfig` 配置解析 | `analyze_alert` 节点 | 从静态配置 → LLM 动态规划 |
| `rebuild_module()` 扁平化 | Agent 内部状态管理 | 从树遍历 → StateGraph 状态流转 |
| `newGetDataFuncMap` 取数分发 | `query_metrics` / `drill_down` Tool | 从 FuncMap → Tool Use |
| `DevotedCompute` 贡献度计算 | `compute_contribution` Tool | 从配置指定 → Agent 自主选择 |
| `RootCauseAnalysis` 集中性判断 | `check_concentration` Tool | 从规则匹配 → LLM 推理判断 |
| `module_match_nvqos()` 场景匹配 | `evaluate_result` 节点 | 从 Must/Show 树 → Agent 综合推理 |
| 结论拼装 + Config 回写 | `generate_report` 节点 | 从模板拼装 → LLM 生成自然语言 |

---

## 4. 模块详细设计

### 4.1 目录结构

```
aiops-diagnostic-agent/
├── README.md                    # 项目说明（架构图 + Quick Start + Demo）
├── pyproject.toml               # 项目配置 & 依赖
├── .env.example                 # 环境变量模板
│
├── src/
│   ├── __init__.py
│   │
│   ├── agent/                   # 核心 Agent 逻辑
│   │   ├── __init__.py
│   │   ├── graph.py             # LangGraph StateGraph 定义
│   │   ├── state.py             # Agent 状态定义（AgentState）
│   │   └── nodes.py             # 各节点逻辑（analyze/execute/evaluate/report）
│   │
│   ├── tools/                   # Agent 可调用的工具集
│   │   ├── __init__.py
│   │   ├── query_metrics.py     # 指标查询（模拟 NVQOS 取数）
│   │   ├── drill_down.py        # 维度下钻分析
│   │   ├── contribution.py      # 贡献度计算（LMDI / 结构归因）
│   │   ├── concentration.py     # 集中性判断（GINI 系数）
│   │   ├── search_logs.py       # 日志搜索
│   │   ├── check_changes.py     # 变更事件检查
│   │   └── compare_points.py    # 两点对比（t1 vs t2）
│   │
│   ├── llm/                     # LLM 抽象层（多模型支持）
│   │   ├── __init__.py
│   │   ├── base.py              # 抽象接口
│   │   ├── claude.py            # Claude (Anthropic) 实现
│   │   └── openai.py            # OpenAI GPT 实现
│   │
│   ├── data/                    # 模拟数据层
│   │   ├── __init__.py
│   │   ├── simulator.py         # 数据模拟器（生成指标/日志/事件）
│   │   ├── scenarios.py         # 预置归因场景（播放成功率下降、卡顿率上升等）
│   │   └── models.py            # 数据模型定义
│   │
│   └── report/                  # 报告生成
│       ├── __init__.py
│       └── markdown.py          # Markdown 格式报告生成
│
├── cli.py                       # CLI 入口
│
├── tests/                       # 测试
│   ├── test_tools.py
│   ├── test_agent.py
│   └── test_scenarios.py
│
└── examples/                    # 示例
    ├── alert_play_rate_drop.json       # 示例告警：播放成功率下降
    ├── alert_buffering_rate_rise.json  # 示例告警：卡顿率上升
    └── sample_report.md                # 示例输出报告
```

### 4.2 Agent 状态设计（state.py）

```python
# 对应原系统的 ProcessConfig + 请求体 + 中间结果
class AgentState(TypedDict):
    # 输入
    alert: dict               # 告警事件（指标名、时间、阈值、业务线等）

    # Agent 推理过程
    plan: list[str]           # 诊断计划（Agent 规划的分析步骤）
    messages: list            # LLM 对话历史
    current_step: int         # 当前步骤
    max_steps: int            # 最大步骤数（防无限循环）

    # 中间结果（对应原系统的 conclusion map）
    evidence: list[dict]      # 已收集的证据列表
    metrics_data: dict        # 查询到的指标数据
    drill_down_results: dict  # 维度下钻结果
    contribution_results: dict # 贡献度计算结果
    concentration_results: dict # 集中性判断结果

    # 输出
    root_causes: list[dict]   # 识别出的根因列表（含分数排序）
    report: str               # 最终报告（Markdown）
    diagnosis_complete: bool  # 是否完成诊断
```

### 4.3 工具设计（对应原系统 FuncMap）

#### Tool 1: query_metrics — 指标查询

对应原系统 `get_data_from_nvqos()` + `query_data_for_two_points()`

```
输入: metric_name, start_time, end_time, filters, aggregate_interval
输出: {t1_value, t2_value, delta, delta_ratio, time_series}
模拟: 根据预置场景生成合理的指标数据
```

#### Tool 2: drill_down — 维度下钻

对应原系统 `generate_nvqos_reqbody_for_dimension_analysis()`

```
输入: metric_name, dimension, time_range, filters
输出: [{dimension_value, t1_value, t2_value, delta, ratio}]
模拟: 按维度拆分后的数据，某些维度值会有明显异常
```

#### Tool 3: compute_contribution — 贡献度计算

对应原系统 `DevotedCompute` FuncMap（LMDI / 结构归因）

```
输入: drill_down_data, method ("lmdi" | "structural")
输出: [{dimension_value, contribution_score, contribution_ratio}]
核心: 实现简化版 LMDI 分解，计算各维度对指标变化的贡献度
```

#### Tool 4: check_concentration — 集中性判断

对应原系统 `RootCauseAnalysis` FuncMap（GINI 系数）

```
输入: contribution_data, threshold
输出: {is_concentrated, gini_coefficient, top_contributors: [{value, ratio}]}
核心: 实现 GINI 系数计算，判断问题是否集中在少数维度
```

#### Tool 5: search_logs — 日志搜索

对应原系统 Kibana 链接生成 + 日志分析

```
输入: keyword, time_range, filters, severity
输出: [{timestamp, level, message, source}]
模拟: 与告警时间相关的异常日志
```

#### Tool 6: check_changes — 变更事件检查

对应原系统事件变更分析

```
输入: time_range, service_name
输出: [{timestamp, change_type, description, author, affected_services}]
模拟: 代码发布、配置变更、扩缩容等事件
```

#### Tool 7: compare_time_points — 两点对比

对应原系统的 t1/t2 两点取数逻辑

```
输入: metric_name, t1, t2, dimensions
输出: {overview: {t1_value, t2_value, delta}, by_dimension: [...]}
核心: 封装两点对比的标准分析流程
```

### 4.4 模拟数据设计（scenarios.py）

预置 3 个典型归因场景，每个场景包含完整的模拟数据：

#### 场景 1：播放成功率下降

```
告警: "播放成功率从 99.2% 下降至 97.8%"
根因: 某 CDN 节点异常 → 特定地区（华南）受影响
证据链:
  - 指标: 播放成功率 -1.4%
  - 维度下钻: region=华南 贡献 80% 的下降
  - 集中性: GINI=0.85, 高度集中
  - 变更事件: CDN 节点配置变更 (10min before alert)
  - 日志: timeout errors spike in cn-south
```

#### 场景 2：卡顿率上升

```
告警: "卡顿率从 3.2% 上升至 5.1%"
根因: 转码参数调整导致特定分辨率质量下降
证据链:
  - 指标: 卡顿率 +1.9%
  - 维度下钻: resolution=1080p 贡献 65%
  - 关联指标: 码率下降 12%
  - 变更事件: 转码配置更新
  - 集中性: GINI=0.72, 中高集中
```

#### 场景 3：首帧耗时劣化

```
告警: "首帧耗时 P95 从 800ms 上升至 1200ms"
根因: DNS 解析异常 + 某运营商链路质量下降
证据链:
  - 指标: 首帧 P95 +400ms
  - 维度下钻: isp=中国电信 贡献 55%, dns_time 贡献 30%
  - 集中性: GINI=0.65, 中等集中（多因素叠加）
  - 日志: DNS resolution timeout
```

### 4.5 LLM 抽象层设计（llm/）

```python
# base.py — 抽象接口
class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages, tools=None, **kwargs) -> LLMResponse: ...

    @abstractmethod
    def get_model_name(self) -> str: ...

# claude.py
class ClaudeLLM(BaseLLM):
    def __init__(self, model="claude-sonnet-4-20250514", api_key=None): ...

# openai.py
class OpenAILLM(BaseLLM):
    def __init__(self, model="gpt-4o", api_key=None): ...

# 使用方式
llm = ClaudeLLM()  # 或 OpenAILLM()
agent = build_graph(llm=llm)
```

---

## 5. Agent 推理示例（预期效果）

```
$ python cli.py --alert examples/alert_play_rate_drop.json

🚨 告警接收: 播放成功率下降 (99.2% → 97.8%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤔 Agent 分析中...

[Step 1] 📊 查询指标数据
  → 调用 query_metrics(metric="play_success_rate", ...)
  → 结果: t1=99.2%, t2=97.8%, delta=-1.4%

[Step 2] 🔍 维度下钻: region
  → 调用 drill_down(dimension="region", ...)
  → 结果: 华南 -3.2%, 华北 -0.1%, 华东 +0.05%

[Step 3] 📈 贡献度计算
  → 调用 compute_contribution(method="lmdi", ...)
  → 结果: 华南贡献 82.3%, 华北贡献 11.2%

[Step 4] 🎯 集中性判断
  → 调用 check_concentration(threshold=0.7, ...)
  → 结果: GINI=0.85, 高度集中于华南地区

[Step 5] 🔄 检查变更事件
  → 调用 check_changes(time_range=[-30min, now], ...)
  → 结果: CDN 节点配置变更 (10min before alert)

[Step 6] 📋 日志搜索
  → 调用 search_logs(keyword="timeout", region="cn-south", ...)
  → 结果: 发现 cn-south CDN 节点 timeout 错误激增

✅ Agent 诊断完成

━━━━━━━━━━━━ 归因诊断报告 ━━━━━━━━━━━━

# 告警归因报告: 播放成功率下降

## 告警概述
- 指标: 播放成功率
- 变化: 99.2% → 97.8% (Δ-1.4%)
- 时间: 2025-01-15 14:30 UTC

## 根因分析
**根因: CDN 华南节点配置变更导致播放成功率下降**
- 置信度: 92%

### 证据链
1. 维度集中性: 华南地区贡献 82.3% 的下降 (GINI=0.85)
2. 变更关联: CDN 节点配置变更发生在告警前 10 分钟
3. 日志佐证: cn-south 节点 timeout 错误从 12/min 激增至 347/min

## 建议操作
1. 【紧急】回滚华南 CDN 节点配置变更
2. 【跟进】检查 CDN 配置变更的灰度策略
3. 【长期】增加 CDN 节点配置变更的自动化回滚机制
```

---

## 6. 开发排期

### Phase 1: 骨架搭建（Day 1-2）

| 任务 | 产出 |
|---|---|
| 项目初始化（pyproject.toml, 目录结构, .env） | 可运行的空项目 |
| LLM 抽象层（base + Claude + OpenAI） | 可切换的 LLM 接口 |
| Agent State 定义 | AgentState TypedDict |
| LangGraph 基础图（4 个节点 + 路由） | 可运行的空 Agent 循环 |

### Phase 2: 工具实现（Day 3-4）

| 任务 | 产出 |
|---|---|
| 模拟数据生成器 + 3 个预置场景 | scenarios.py + simulator.py |
| 实现 7 个 Tools（含 LangChain @tool 装饰器） | tools/ 目录 |
| Tools 单元测试 | test_tools.py |

### Phase 3: Agent 推理逻辑（Day 5-6）

| 任务 | 产出 |
|---|---|
| 完善 nodes.py 各节点逻辑 | 完整的推理循环 |
| System Prompt 设计（归因专家角色设定） | prompt 模板 |
| 报告生成模块 | report/markdown.py |
| 端到端测试：3 个场景全部跑通 | test_scenarios.py |

### Phase 4: CLI + 文档（Day 7）

| 任务 | 产出 |
|---|---|
| CLI 交互界面（Rich 美化输出） | cli.py |
| README（架构图 + Quick Start + Demo 录屏） | README.md |
| 示例输出报告 | examples/sample_report.md |

### Phase 5: 打磨（Day 8-10，可选）

| 任务 | 产出 |
|---|---|
| 增加 Memory 能力（记忆历史归因结果） | 增强型 Agent |
| 增加 Streamlit UI | 可选前端 |
| 增加更多归因场景 | 更多 demo 数据 |
| 性能优化（并行 Tool 调用） | 更快的诊断速度 |

---

## 7. 面试叙事设计

### 面试时怎么讲这个项目

> "我在字节做了 2 年的 AIOps 归因平台，核心是一个配置驱动的多步归因系统。在学习 Agent 架构后，我发现原系统的 FuncMap 动态分发、场景树匹配等设计本质上就是 Agent 的 Tool Use 和多步推理。于是我用 LangGraph 重新实现了一版，把静态的配置驱动升级为 LLM 驱动的智能编排——Agent 可以根据告警上下文动态选择分析工具、自主决定下钻维度、综合多方证据推理根因，而不是依赖人工配置的固定流程。"

### 关键考点准备

| 面试官可能问 | 回答要点 |
|---|---|
| 为什么用 Agent 而不是传统编排？ | 灵活性——新场景不用改配置，Agent 自主推理；原系统每新增场景需要配置 ProcessConfig |
| Agent 会不会瞎跑、效率低？ | 设了 max_steps 限制 + 结构化的 State 管理 + System Prompt 约束分析方向 |
| 贡献度算法是你自己实现的？ | 是的，简化版 LMDI 分解，面试时可以手推公式 |
| 为什么选 LangGraph？ | StateGraph 的显式状态管理适合多步诊断流程，比 chain 更可控 |
| 和原系统比有什么劣势？ | 延迟更高（LLM 推理耗时）、成本更高（API 调用）；适合复杂告警，简单告警用规则更快 |

---

## 8. 非目标（Phase 1 不做）

- ❌ 真实数据源接入
- ❌ 多 Agent 协作
- ❌ 生产级部署（Docker / K8s）
- ❌ 评估系统 / Benchmark
- ❌ Streamlit / Web UI（Phase 2 可选）
- ❌ 分布式 / 高并发

---

## 9. 成功标准

1. **3 个预置场景全部能跑通**，Agent 能自主完成从告警到报告的全流程
2. **推理步骤合理**：不多不少，每一步有明确目的
3. **报告可读**：非技术人员也能理解根因和建议
4. **代码质量**：模块清晰、有类型标注、有测试、有文档
5. **可切换 LLM**：Claude 和 OpenAI 至少各跑通一次
