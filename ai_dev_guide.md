# AIOps Diagnostic Agent — AI 辅助开发步骤指南

> 本文档将项目开发拆解为可直接丢给 AI 编程工具（Claude Code / Cursor / Copilot）执行的分步 Prompt。
> 按顺序执行，每步完成后验证再进入下一步。

---

## 使用说明

1. **推荐工具**：Claude Code（命令行）或 Cursor（IDE），两者都支持长上下文和代码生成
2. **执行方式**：复制每一步的 Prompt，粘贴给 AI 工具执行
3. **验证方式**：每步执行后运行验证命令，确保通过再进入下一步
4. **出错处理**：如果某步出错，把报错信息贴给 AI，让它修复

---

## 前置准备（你自己做）

```bash
# 1. 创建项目目录
mkdir aiops-diagnostic-agent && cd aiops-diagnostic-agent

# 2. 初始化 git
git init

# 3. 确保 Python 3.11+ 已安装
python3 --version

# 4. 安装 uv（如果没有）
pip install uv
```

---

## Phase 1: 骨架搭建（Day 1-2）

### Step 1.1 — 项目初始化

**Prompt：**

```
我要创建一个 Python 项目：AIOps Diagnostic Agent，基于 LangGraph 的 AIOps 智能归因 Agent。

请帮我完成项目初始化：

1. 创建 pyproject.toml：
   - 项目名: aiops-diagnostic-agent
   - Python >= 3.11
   - 核心依赖: langgraph, langchain-core, langchain-anthropic, langchain-openai, pydantic >= 2.0, rich（CLI美化）, python-dotenv
   - 开发依赖: pytest, pytest-asyncio, ruff
   - 用 uv 管理依赖

2. 创建 .env.example：
   - ANTHROPIC_API_KEY=your-api-key-here
   - OPENAI_API_KEY=your-api-key-here
   - DEFAULT_LLM=claude  # claude 或 openai
   - DEFAULT_MODEL=（Claude 用 claude-sonnet-4-20250514, OpenAI 用 gpt-4o）

3. 创建 .gitignore（Python 项目标准 + .env）

4. 创建完整的目录结构（所有文件先放空的 __init__.py）：
   src/
   ├── __init__.py
   ├── agent/        （graph.py, state.py, nodes.py）
   ├── tools/        （7个工具文件）
   ├── llm/          （base.py, claude.py, openai.py）
   ├── data/         （simulator.py, scenarios.py, models.py）
   └── report/       （markdown.py）
   cli.py
   tests/
   examples/

5. 创建一个简单的 cli.py，运行后打印 "AIOps Diagnostic Agent v0.1.0 - Ready"

请直接生成所有文件。
```

**验证：**
```bash
uv sync && python cli.py
# 应该输出: AIOps Diagnostic Agent v0.1.0 - Ready
```

---

### Step 1.2 — LLM 抽象层

**Prompt：**

```
现在实现 LLM 抽象层，支持 Claude 和 OpenAI 两种模型。

文件：src/llm/base.py, src/llm/claude.py, src/llm/openai.py, src/llm/__init__.py

设计要求：
1. base.py 定义抽象基类 BaseLLM：
   - 属性: model_name
   - 方法: get_chat_model() -> BaseChatModel（返回 LangChain 的 ChatModel）
   - 这里直接返回 LangChain 的 ChatModel 实例即可，不需要自己封装调用逻辑

2. claude.py 实现 ClaudeLLM：
   - 使用 langchain_anthropic.ChatAnthropic
   - 默认模型: claude-sonnet-4-20250514
   - 从环境变量读取 ANTHROPIC_API_KEY

3. openai.py 实现 OpenAILLM：
   - 使用 langchain_openai.ChatOpenAI
   - 默认模型: gpt-4o
   - 从环境变量读取 OPENAI_API_KEY

4. __init__.py 提供工厂函数：
   - get_llm(provider="claude", model=None) -> BaseLLM
   - 根据 provider 参数返回对应实现
   - 支持从 .env 的 DEFAULT_LLM 读取默认值

保持简单，不要过度设计。
```

**验证：**
```bash
python -c "from src.llm import get_llm; llm = get_llm('claude'); print(f'LLM ready: {llm.model_name}')"
# 应该输出: LLM ready: claude-sonnet-4-20250514
```

---

### Step 1.3 — Agent State 定义

**Prompt：**

```
现在定义 Agent 的状态结构。

文件：src/agent/state.py

背景：这个 Agent 用于 AIOps 告警归因，核心流程是：
接收告警 → 查询指标 → 维度下钻 → 计算贡献度 → 判断集中性 → 搜索日志 → 检查变更 → 生成报告

请定义 AgentState（使用 TypedDict，兼容 LangGraph）：

```python
class AgentState(TypedDict):
    # --- 输入 ---
    alert: dict                    # 告警事件信息

    # --- LangGraph 消息 ---
    messages: Annotated[list, add_messages]  # LLM 对话历史（LangGraph 标准）

    # --- 推理控制 ---
    current_step: int              # 当前步骤计数
    max_steps: int                 # 最大步骤数（默认15，防无限循环）

    # --- 中间证据收集 ---
    evidence: list[dict]           # 已收集的证据列表，每条包含 {tool, input, output, summary}

    # --- 最终输出 ---
    root_causes: list[dict]        # 根因列表 [{cause, confidence, evidence_ids}]
    report: str                    # 最终 Markdown 报告
    status: str                    # "running" | "completed" | "failed" | "max_steps_reached"
```

同时定义辅助数据模型（用 Pydantic BaseModel）：
- AlertEvent: metric_name, severity, current_value, baseline_value, timestamp, service, region, filters
- Evidence: tool_name, input_params, output_data, summary, timestamp
- RootCause: description, confidence_score, supporting_evidence, suggested_actions

保持简洁，够用就好。
```

**验证：**
```bash
python -c "from src.agent.state import AgentState; print('State defined')"
```

---

### Step 1.4 — LangGraph 基础图（空壳）

**Prompt：**

```
现在实现 LangGraph 的 StateGraph，先搭空壳，节点逻辑后面再填。

文件：src/agent/graph.py, src/agent/nodes.py

要求：

1. nodes.py 定义 4 个节点函数（先写空壳，只打印日志和更新 state）：
   - analyze_alert(state) → 分析告警，规划诊断方向
   - execute_tool(state) → 调用工具收集证据
   - evaluate_result(state) → 评估已有证据，决定继续还是结束
   - generate_report(state) → 生成最终归因报告

2. graph.py 定义 build_graph(llm) 函数：
   - 创建 StateGraph(AgentState)
   - 添加 4 个节点
   - 定义边：
     START → analyze_alert
     analyze_alert → execute_tool
     execute_tool → evaluate_result
     evaluate_result → 条件路由：
       - 如果 status == "completed" 或 current_step >= max_steps → generate_report
       - 否则 → execute_tool（继续循环）
     generate_report → END
   - 返回编译后的 graph

3. 每个空壳节点内部：
   - 打印当前节点名和 step 数（用 rich 的 console.print）
   - 适当更新 state（比如 current_step + 1）
   - analyze_alert 设置初始 status = "running"
   - generate_report 设置 status = "completed" 并生成一个占位报告

4. 更新 cli.py：
   - 接受一个 --alert 参数（JSON 文件路径）
   - 加载告警 JSON → 构建 graph → 运行 → 打印报告
   - 如果不传 --alert，使用一个硬编码的示例告警

先让整个循环能跑通（空壳），不需要真正调用 LLM。
```

**验证：**
```bash
python cli.py
# 应该看到 4 个节点依次执行的日志输出，最后打印占位报告
```

---

### Step 1.5 — 接入 LLM（让 Agent 真正思考）

**Prompt：**

```
现在把 LLM 接入 Agent 节点，让 analyze_alert 和 evaluate_result 真正使用 LLM 推理。

修改文件：src/agent/nodes.py, src/agent/graph.py

要求：

1. graph.py 的 build_graph(llm) 要把 llm 传给需要的节点（通过闭包或 functools.partial）

2. analyze_alert 节点：
   - 构建 system prompt：你是一个 AIOps 归因专家，擅长分析服务器指标告警...
   - 把告警信息作为 user message 传给 LLM
   - LLM 返回初步分析和建议的诊断步骤
   - 把 LLM 的回复加入 messages

3. execute_tool 节点：
   - 这一步先不实现真正的 tool calling（下一个 Phase 做）
   - 暂时让 LLM 根据当前 messages 决定"下一步想做什么"
   - 把决策加入 messages 和 evidence

4. evaluate_result 节点：
   - 让 LLM 根据已收集的 evidence 判断：
     a) 是否已经找到根因 → status = "completed"
     b) 还需要更多信息 → status = "running"
   - 为了 demo 能跑通，让它在 3 步后自动设为 completed

5. generate_report 节点：
   - 让 LLM 根据所有 evidence 生成一份 Markdown 格式的归因报告
   - 报告结构：告警概述 → 分析过程 → 根因结论 → 建议操作

6. System Prompt 设计要点：
   - 角色：资深 AIOps 归因分析专家
   - 背景：你负责视频云服务的性能指标监控与告警归因
   - 能力：熟悉 LMDI 贡献度分析、GINI 集中性判断、维度下钻等方法
   - 约束：每次只执行一个分析步骤，基于证据推理，不要猜测

确保整个流程能跑通，LLM 能进行基本的推理。
```

**验证：**
```bash
# 先确保 .env 里填了 API Key
cp .env.example .env
# 编辑 .env 填入你的 API Key

python cli.py
# 应该看到 Agent 用 LLM 进行推理，最终输出一份报告
```

**验证成功后，提交一次 git：**
```bash
git add -A && git commit -m "feat: Phase 1 complete - basic agent skeleton with LLM"
```

---

## Phase 2: 工具实现（Day 3-4）

### Step 2.1 — 数据模型与模拟数据

**Prompt：**

```
现在实现模拟数据层，为 Agent 的工具提供数据。

文件：src/data/models.py, src/data/scenarios.py, src/data/simulator.py

背景：这个项目模拟 AIOps 告警归因场景，数据不需要真实，但要合理。

1. models.py — 定义数据模型（Pydantic BaseModel）：
   - MetricDataPoint: timestamp, value, metric_name
   - TimeSeriesData: metric_name, data_points: list[MetricDataPoint], t1_value, t2_value, delta, delta_ratio
   - DimensionBreakdown: dimension_name, dimension_value, t1_value, t2_value, delta, contribution_ratio
   - LogEntry: timestamp, level (INFO/WARN/ERROR), message, source, region
   - ChangeEvent: timestamp, change_type (deployment/config/scaling), description, author, affected_services
   - ContributionResult: dimension_value, contribution_score, contribution_ratio, method
   - ConcentrationResult: is_concentrated, gini_coefficient, top_contributors, threshold_used

2. scenarios.py — 定义 3 个预置场景（每个场景包含完整的模拟数据集）：

   场景 1: play_success_rate_drop
   - 告警: 播放成功率从 99.2% 下降至 97.8%
   - 指标数据: 过去1h的时间序列，在告警时间点明显下降
   - 维度下钻: region 维度中，cn-south 下降 3.2%（贡献82%），其他地区微小波动
   - 日志: cn-south CDN 节点 timeout 错误激增
   - 变更事件: CDN 节点配置变更（告警前10分钟）
   - 根因: CDN 华南节点配置变更导致

   场景 2: buffering_rate_rise
   - 告警: 卡顿率从 3.2% 上升至 5.1%
   - 维度下钻: resolution=1080p 贡献 65%，codec=h265 贡献 25%
   - 关联指标: 码率下降 12%
   - 变更事件: 转码配置更新
   - 根因: 转码参数调整导致 1080p 质量下降

   场景 3: first_frame_latency_degradation
   - 告警: 首帧耗时 P95 从 800ms 上升至 1200ms
   - 维度下钻: isp=中国电信 贡献 55%
   - 日志: DNS resolution timeout 增多
   - 根因: DNS 解析异常 + 运营商链路质量下降

3. simulator.py — 数据模拟器：
   - class DataSimulator：
     - __init__(scenario_name): 加载对应场景
     - query_metrics(metric, start, end, filters) -> TimeSeriesData
     - drill_down(metric, dimension, time_range) -> list[DimensionBreakdown]
     - search_logs(keyword, time_range, severity) -> list[LogEntry]
     - get_changes(time_range, service) -> list[ChangeEvent]
   - 数据要合理但不需要精确，重点是能展示 Agent 的推理过程

每个场景的数据要自洽，确保 Agent 分析后能得出正确的根因结论。
```

**验证：**
```bash
python -c "
from src.data.simulator import DataSimulator
sim = DataSimulator('play_success_rate_drop')
metrics = sim.query_metrics('play_success_rate', 0, 3600)
print(f'Metrics: t1={metrics.t1_value}, t2={metrics.t2_value}, delta={metrics.delta}')
drilldown = sim.drill_down('play_success_rate', 'region', (0, 3600))
for d in drilldown:
    print(f'  {d.dimension_value}: delta={d.delta}, contribution={d.contribution_ratio}')
"
```

---

### Step 2.2 — 实现 7 个 Tools

**Prompt：**

```
现在实现 Agent 的 7 个工具，使用 LangChain 的 @tool 装饰器。

文件：src/tools/ 下的 7 个文件 + __init__.py

所有工具都从 DataSimulator 获取数据。通过一个全局的 simulator 实例来注入数据（工具函数内部访问）。

设计要求：

1. query_metrics.py — 指标查询
   @tool 函数签名: query_metrics(metric_name: str, start_time: int, end_time: int, filters: dict = None) -> str
   功能: 调用 simulator.query_metrics()，返回格式化的指标摘要
   返回示例: "指标 play_success_rate: 基线值 99.2%, 当前值 97.8%, 变化 -1.4% (下降)"

2. drill_down.py — 维度下钻
   @tool: drill_down(metric_name: str, dimension: str, start_time: int, end_time: int) -> str
   功能: 调用 simulator.drill_down()，返回各维度值的变化情况
   返回示例: "按 region 维度下钻:\n  cn-south: -3.2% (贡献 82.3%)\n  cn-north: -0.1% (贡献 11.2%)\n..."

3. contribution.py — 贡献度计算
   @tool: compute_contribution(dimension_data: str, method: str = "lmdi") -> str
   功能: 基于维度下钻数据，计算 LMDI 或结构归因的贡献度
   核心: 实现简化版 LMDI 分解公式
   返回: 各维度值的贡献度排序

4. concentration.py — 集中性判断
   @tool: check_concentration(contribution_data: str, threshold: float = 0.7) -> str
   功能: 计算 GINI 系数，判断问题是否集中
   核心: 实现 GINI 系数计算公式
   返回: "集中性分析: GINI=0.85 (高度集中), Top 贡献者: cn-south (82.3%)"

5. search_logs.py — 日志搜索
   @tool: search_logs(keyword: str, start_time: int, end_time: int, severity: str = "ERROR") -> str
   功能: 调用 simulator.search_logs()
   返回: 格式化的日志条目列表

6. check_changes.py — 变更事件检查
   @tool: check_changes(start_time: int, end_time: int, service_name: str = None) -> str
   功能: 调用 simulator.get_changes()
   返回: 格式化的变更事件列表

7. compare_points.py — 两点对比
   @tool: compare_time_points(metric_name: str, t1: int, t2: int, dimensions: list[str] = None) -> str
   功能: 封装两点对比的标准分析（对应原系统的 t1/t2 两点取数）
   返回: 综合对比报告

__init__.py:
- 导出 get_all_tools(simulator) -> list[BaseTool] 函数
- 提供工具注册与 simulator 注入机制

重要：每个 @tool 函数都要有清晰的 docstring，因为这就是 LLM 看到的工具描述，直接影响 Agent 的工具选择准确性。Docstring 要说明：什么时候用这个工具、输入是什么、输出是什么。
```

**验证：**
```bash
python -c "
from src.data.simulator import DataSimulator
from src.tools import get_all_tools
sim = DataSimulator('play_success_rate_drop')
tools = get_all_tools(sim)
print(f'Loaded {len(tools)} tools:')
for t in tools:
    print(f'  - {t.name}: {t.description[:60]}...')
"
# 应该列出 7 个工具及其描述
```

---

### Step 2.3 — 贡献度 & 集中性算法核心实现

**Prompt：**

```
现在完善 compute_contribution 和 check_concentration 工具中的核心算法。

这两个算法是项目的技术亮点，面试时会被追问，需要实现真实的计算逻辑。

1. LMDI 贡献度分解（简化版）:
   - 背景: LMDI (Logarithmic Mean Divisia Index) 用于分解指标变化的贡献来源
   - 输入: 各维度在 t1、t2 时刻的值
   - 公式:
     对于维度 i 的贡献度:
     L(a, b) = (a - b) / (ln(a) - ln(b))  # 对数均值函数
     contribution_i = L(share_i_t2, share_i_t1) * ln(value_i_t2 / value_i_t1)
     其中 share_i = value_i / total_value
   - 输出: 各维度的贡献度值和贡献占比
   - 边界处理: 值为 0 时的保护、对数为 0 时的处理

2. GINI 系数计算:
   - 输入: 各维度的贡献度值列表
   - 公式:
     排序后，GINI = (2 * sum(i * x_i) / (n * sum(x_i))) - (n + 1) / n
   - 输出: GINI 系数 (0~1)
   - 判断标准: > 0.7 高度集中, 0.4~0.7 中等集中, < 0.4 分散

请在 src/tools/contribution.py 和 src/tools/concentration.py 中实现这两个算法。
确保有足够的注释说明公式含义，面试时可以直接看代码讲解。

同时在 tests/test_tools.py 中添加这两个算法的单元测试：
- 测试 LMDI: 给定已知的 t1/t2 数据，验证贡献度之和约等于总变化量
- 测试 GINI: 完全均匀分布 → GINI ≈ 0; 完全集中 → GINI ≈ 1
```

**验证：**
```bash
python -m pytest tests/test_tools.py -v
# 所有测试应该通过
```

**提交：**
```bash
git add -A && git commit -m "feat: Phase 2 complete - tools and simulated data"
```

---

## Phase 3: Agent 推理逻辑（Day 5-6）

### Step 3.1 — 完善 Agent 节点（接入真实 Tool Calling）

**Prompt：**

```
现在把 7 个工具接入 Agent 的 LangGraph 图，实现真正的 Tool Calling 循环。

修改文件：src/agent/graph.py, src/agent/nodes.py

要求：

1. graph.py 改造：
   - build_graph(llm, simulator) 接收 simulator 参数
   - 获取所有 tools: tools = get_all_tools(simulator)
   - 将 tools 绑定到 LLM: llm_with_tools = llm.get_chat_model().bind_tools(tools)
   - 使用 LangGraph 的标准 tool calling 模式：
     - agent_node: 调用 llm_with_tools，根据 messages 决定调用哪个 tool
     - tool_node: 使用 ToolNode(tools) 执行工具调用
   - 路由逻辑:
     - agent_node 输出包含 tool_calls → 走 tool_node
     - agent_node 输出不包含 tool_calls → 走 evaluate_result
     - evaluate_result → 如果需要继续 → agent_node; 否则 → generate_report

2. 更新后的图结构：
   START → analyze_alert → agent_node → 条件路由 →
     有 tool_calls → tool_node → agent_node（循环）
     无 tool_calls → evaluate_result → 条件路由 →
       需要继续 → agent_node
       已完成 → generate_report → END

3. analyze_alert 节点:
   - 构建详细的 system prompt（见下方）
   - 把告警信息格式化为 user message
   - 返回更新后的 messages

4. evaluate_result 节点:
   - 检查已执行的步骤数
   - 如果 current_step >= max_steps → status = "max_steps_reached"
   - 否则让 Agent 继续

5. generate_report 节点:
   - 在 messages 中追加一条指令："请根据以上所有分析结果，生成一份结构化的归因诊断报告"
   - 调用 LLM 生成报告
   - 报告格式: Markdown，包含告警概述、分析过程、根因结论、置信度、建议操作

6. System Prompt (关键):
```
你是一位资深的 AIOps 归因分析专家，负责视频云服务的性能指标告警根因定位。

## 你的工作流程
1. 收到告警后，先查询指标数据了解整体变化情况
2. 对变化显著的指标进行维度下钻，找出哪些维度贡献了主要变化
3. 使用 LMDI 贡献度分析量化各维度的影响程度
4. 使用 GINI 系数判断问题是否集中在少数维度
5. 搜索相关日志和变更事件，寻找关联证据
6. 综合所有证据，推理出根因并给出建议

## 规则
- 每次只调用一个工具，分析结果后再决定下一步
- 优先使用数据和证据推理，不要猜测
- 如果某个维度贡献度超过 50%，重点分析该维度
- GINI > 0.7 说明问题高度集中，通常意味着有明确的单一根因
- 变更事件如果与告警时间高度相关（前后30分钟内），是重要的根因线索
- 当你认为已经收集到足够的证据来确定根因时，停止调用工具并给出结论
```

确保整个 tool calling 循环能正常工作。
```

**验证：**
```bash
python cli.py
# 应该看到 Agent 自动调用各种工具，最后输出归因报告
# 观察 Agent 的推理过程是否合理
```

---

### Step 3.2 — 完善 CLI 交互体验

**Prompt：**

```
现在完善 CLI 交互体验，让输出更美观、更易读。

修改文件：cli.py

使用 rich 库美化输出，要求：

1. 启动时显示项目 banner（ASCII art 或简单 logo）

2. 接收参数：
   - --alert: 告警 JSON 文件路径
   - --scenario: 预置场景名（play_success_rate_drop / buffering_rate_rise / first_frame_latency_degradation）
   - --llm: 模型选择（claude / openai，默认从 .env 读取）
   - --max-steps: 最大步骤数（默认 15）
   - --verbose: 详细模式（显示完整 tool 输入输出）
   - 如果两个都不传，显示交互式菜单让用户选择场景

3. 运行过程中实时显示：
   - 🚨 告警信息（用 rich.Panel）
   - 每个步骤用 [Step N] + emoji 标识：
     📊 查询指标 / 🔍 维度下钻 / 📈 贡献度计算 / 🎯 集中性判断 / 📋 日志搜索 / 🔄 变更检查
   - 工具调用用 rich.Spinner 显示加载状态
   - 工具结果用缩进显示摘要

4. 最终报告：
   - 用 rich.Markdown 渲染报告
   - 同时保存为 output/report_{timestamp}.md 文件
   - 显示保存路径

5. 统计信息：
   - 总步骤数、总耗时、调用的工具列表
```

**验证：**
```bash
python cli.py --scenario play_success_rate_drop --verbose
# 应该看到美化后的输出，包含完整的推理过程和报告
```

---

### Step 3.3 — 三个场景端到端测试

**Prompt：**

```
现在确保 3 个预置场景全部能端到端跑通，并输出正确的归因结论。

文件：tests/test_scenarios.py

要求：

1. 为每个场景编写集成测试：
   - test_scenario_play_success_rate_drop: Agent 应该能识别出"CDN华南节点"相关的根因
   - test_scenario_buffering_rate_rise: Agent 应该能识别出"转码配置"相关的根因
   - test_scenario_first_frame_latency_degradation: Agent 应该能识别出"DNS/运营商"相关的根因

2. 测试验证：
   - Agent 能正常完成（status 为 completed 或 max_steps_reached）
   - 报告不为空
   - 至少使用了 3 个不同的工具
   - evidence 列表不为空

3. 如果发现某个场景跑不通或归因不准，调整：
   - 模拟数据：让数据信号更明显
   - System Prompt：增加引导
   - 工具描述：让 LLM 更容易选对工具

注意：这些测试需要调用真实 LLM API，标记为 @pytest.mark.integration，
可以用 pytest -m integration 单独运行。

同时创建 examples/ 目录下的 3 个示例告警 JSON 文件。
```

**验证：**
```bash
# 运行集成测试（需要 API Key）
python -m pytest tests/test_scenarios.py -v -m integration

# 手动跑 3 个场景
python cli.py --scenario play_success_rate_drop
python cli.py --scenario buffering_rate_rise
python cli.py --scenario first_frame_latency_degradation
```

**提交：**
```bash
git add -A && git commit -m "feat: Phase 3 complete - full agent reasoning with tool calling"
```

---

## Phase 4: 文档与打磨（Day 7）

### Step 4.1 — README

**Prompt：**

```
现在编写项目的 README.md，这是面试官看到的第一个文件，必须高质量。

文件：README.md

结构：

1. 项目标题 + 一句话描述 + badges（Python version, License）

2. 项目亮点（3-4 个 bullet points）：
   - 基于 LangGraph 的多步推理 Agent
   - 真实 AIOps 归因算法（LMDI、GINI）
   - 多模型支持（Claude / OpenAI）
   - 完整的诊断报告生成

3. 架构图（用 Mermaid 语法，可在 GitHub 直接渲染）：
   - 整体架构（CLI → Agent → Tools → Data）
   - LangGraph 状态图（节点和边的流转）

4. Quick Start（5步以内跑通）：
   - clone → install → config .env → run demo

5. 核心设计：
   - Agent 推理循环说明
   - 工具列表及用途
   - 归因算法简介（LMDI、GINI，带公式）

6. 项目结构（目录树）

7. 预置场景说明

8. Demo 输出示例（截取一段典型的运行输出）

9. 技术栈

10. License: MIT

风格：简洁专业，重点突出，不要废话。面试官 30 秒内要能理解项目是做什么的。
```

---

### Step 4.2 — 代码质量检查

**Prompt：**

```
请对整个项目做一次代码质量检查和优化：

1. 类型标注：确保所有函数都有完整的类型标注
2. Docstring：所有公开函数和类都有 docstring
3. 错误处理：添加必要的 try/except，特别是 LLM 调用和工具执行
4. 代码格式：用 ruff 检查并修复格式问题
5. 移除未使用的 import 和变量
6. 确保 .env.example 中的说明完整
7. 确保所有测试能通过

运行：
- ruff check src/ cli.py --fix
- ruff format src/ cli.py
- python -m pytest tests/ -v（不含 integration 测试）
```

**最终验证：**
```bash
# 格式检查
ruff check src/ cli.py

# 单元测试
python -m pytest tests/ -v -k "not integration"

# 端到端运行
python cli.py --scenario play_success_rate_drop

# 确保 README 中的 Quick Start 步骤可执行
```

**最终提交：**
```bash
git add -A && git commit -m "feat: Phase 4 complete - docs, tests, and polish"
```

---

## 汇总：完整执行检查清单

| # | 步骤 | 验证方式 | 预计耗时 |
|---|---|---|---|
| 1.1 | 项目初始化 | `python cli.py` 打印 Ready | 15 min |
| 1.2 | LLM 抽象层 | import 成功 | 15 min |
| 1.3 | Agent State | import 成功 | 10 min |
| 1.4 | LangGraph 空壳图 | cli.py 跑通空循环 | 30 min |
| 1.5 | 接入 LLM | Agent 能用 LLM 推理 | 30 min |
| 2.1 | 模拟数据层 | simulator 返回数据 | 45 min |
| 2.2 | 7 个 Tools | 工具列表打印成功 | 45 min |
| 2.3 | LMDI + GINI 算法 | 单元测试通过 | 30 min |
| 3.1 | Agent Tool Calling | 完整推理循环跑通 | 60 min |
| 3.2 | CLI 美化 | 美观的交互输出 | 30 min |
| 3.3 | 3 场景测试 | 全部场景跑通 | 45 min |
| 4.1 | README | 文档完整可读 | 30 min |
| 4.2 | 代码质量 | ruff + pytest 全过 | 20 min |

**总计：约 6-7 小时有效开发时间**（每步含 AI 生成 + 你的验证 + 调整）

---

## 常见问题处理

### AI 生成的代码报错怎么办？
直接把报错信息贴给 AI："运行后报错：[错误信息]，请修复"

### LLM 工具选择不准怎么办？
贴给 AI："Agent 在 XX 场景下选择了 XX 工具，但应该选择 XX。请优化 System Prompt 或工具描述"

### 模拟数据不合理怎么办？
贴给 AI："场景 XX 的模拟数据中，XX 数据不够明显，Agent 无法正确归因。请调整数据让信号更强"

### 步骤之间上下文怎么传递？
每开始新的一步时，先告诉 AI："我们正在开发 AIOps Diagnostic Agent 项目，当前项目结构是 [贴目录树]，上一步已完成 [XX]，现在做 [XX]"
