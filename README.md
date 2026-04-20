# hermes-agent-ros

ROS2-native agent framework. LLM agents run as ROS2 nodes and manipulate
topics, services, and actions as "tools".

Design docs live in [`docs/`](./docs). Deep dive: [`docs/architecture.md`](./docs/architecture.md).

## Architecture diagrams

Planner と Executor を分離し、**型付きの `ToolCall`** だけがロボット側に渡ります（GitHub が
[Mermaid](https://github.blog/news-insights/product-news/github-now-supports-mermaid-diagrams/)
を描画します。プレーンな Markdown ビューアではコードブロックのまま表示されることがあります）。

**パッケージ依存（概要）:**

```mermaid
flowchart TB
  bringup[hermes_bringup\nlaunch + config]
  agent[hermes_agent\nAgentNode + ExecutorNode]
  tools[hermes_tools\nToolInterface + adapters]
  msgs[hermes_msgs\nmsg srv action]
  bringup --> agent
  agent --> tools
  agent --> msgs
  tools --> msgs
```

**ランタイム（ノードとデータの流れ・概念図）:**

```mermaid
flowchart LR
  subgraph user["ユーザー / CLI"]
    U[ros2 service call\n/hermes/ask]
  end
  subgraph planner["Planner（hermes_agent）"]
    A[AgentNode]
    L[LLMClient\nmock / ollama / …]
    A --- L
  end
  subgraph executor["Executor（hermes_agent）"]
    E[ExecutorNode]
    R[ToolRegistry]
    S[SafetyFilter]
    E --- R
    E --- S
  end
  subgraph ros["ROS 2 グラフ"]
    T["/turtle1/cmd_vel など"]
  end
  U -->|AskAgent| A
  A -->|ExecutePlan\naction| E
  E -.->|action result| A
  E -->|publish / call| T
```

**ワンショット質問**から **cmd_vel まで**の流れ（turtlesim デモのイメージ）:

```mermaid
sequenceDiagram
  participant U as ユーザー
  participant Ask as /hermes/ask
  participant Ag as AgentNode
  participant LLM as LLM Ollama 等
  participant Ex as ExecutorNode
  participant SF as SafetyFilter
  participant Tool as topic_publisher_tool
  participant Sim as turtlesim
  U->>Ask: prompt 例 前に進んで
  Ask->>Ag: AskAgent
  Ag->>LLM: chat + tool specs
  LLM-->>Ag: tool_calls
  Ag->>Ex: ExecutePlan goal
  Ex->>SF: check ToolCall
  SF-->>Ex: OK / clip / reject
  Ex->>Tool: run args
  Tool->>Sim: Twist on /turtle1/cmd_vel
  Ex-->>Ag: ToolResult
  Ag-->>Ask: reply + executed_calls
  Ask-->>U: AskAgent Response
```

## Web で見る（RViz のブラウザ代替）

公式 **RViz2 をそのまま Web に出す**プロジェクトは保守されていません（代替として Webviz / Foxglove が推奨される流れ）。  
ブラウザでライブトピックを見るには **Foxglove Studio**（[studio.foxglove.dev](https://studio.foxglove.dev/) または [app.foxglove.dev](https://app.foxglove.dev/)）と **`ros-jazzy-foxglove-bridge`** の組み合わせが手軽です。

- turtlesim + hermes のトピック（例: `/turtle1/pose`, `/turtle1/cmd_vel`）を **Raw Messages** / **Plot** パネルで表示可能
- **Playwright でデモ動画**を撮る手順: [`examples/foxglove_turtlesim/README.md`](./examples/foxglove_turtlesim/README.md)

## Packages

| Package | Build type | Purpose |
|---|---|---|
| `hermes_msgs` | `ament_cmake` | ROS2 interfaces (msg/srv/action) |
| `hermes_agent` | `ament_python` | AgentNode (planner) + ExecutorNode + LLM clients |
| `hermes_tools` | `ament_python` | ToolInterface base + generic ROS2 tools |
| `hermes_bringup` | `ament_python` | launch files and runtime config |

## Target

- ROS2 Jazzy (primary)
- Python 3.12+
- `rclpy`, `ament_python`
- Local LLM runtime (Ollama recommended — see `docs/plan.md` §4).
  Cloud LLM backends are deprioritised (ADR-004).

## Quickstart

```bash
colcon build --symlink-install
source install/setup.bash
ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=mock
ros2 service call /hermes/ask hermes_msgs/srv/AskAgent "{prompt: '前に進んで'}"
```

With a local [Ollama](https://ollama.com/) daemon and a **tool-capable**
instruct model, run the same demo against a real LLM. On modest GPUs,
`qwen2.5:3b-instruct` has been used successfully for native tool calls;
`qwen2.5:7b-instruct` is an alternative if you have headroom (cold load
and tool latency can be high).

```bash
export ROS_DOMAIN_ID=224   # use any free id <= 232; avoids DDS port errors
# optional: export ROS_LOCALHOST_ONLY=1
export HERMES_OLLAMA_MODEL=qwen2.5:3b-instruct
ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=ollama
# Slow models: ollama_timeout_sec:=240.0
# turtlebot_demo defaults default_cmd_vel_topic:=/turtle1/cmd_vel so small
# models that omit `topic` still publish to the demo topic.
ros2 service call /hermes/ask hermes_msgs/srv/AskAgent "{prompt: '前に進んで'}"
```

Measured Ollama + turtlesim behaviour (pose, timings, caveats) lives in
[`docs/experiments.md`](./docs/experiments.md).

See `examples/turtlebot_demo/README.md` for the demo.

For picking up this codebase (e.g. in Cursor), start with
[`docs/plan.md`](./docs/plan.md) — handoff covering architecture,
conventions, and optional follow-ups (e.g. `OpenAICompatClient`, prompt
tuning for all three scenarios).

## Tests

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
colcon test --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --verbose
```

Current suite: 63 tests (31 in hermes_tools, 32 in hermes_agent) covering
SafetyFilter, MockClient, ShortTermMemory/ToolLog, all four tool adapters
against real rclpy, and three turtlebot_demo scenarios end-to-end.
