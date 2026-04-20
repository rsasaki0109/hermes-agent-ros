# hermes-agent-ros

ROS2-native agent framework. LLM agents run as ROS2 nodes and manipulate
topics, services, and actions as "tools".

Design docs live in [`docs/`](./docs). Reference architecture: Planner /
Executor split (see `docs/architecture.md`).

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

With a local [Ollama](https://ollama.com/) daemon and a pulled tool-capable model
(e.g. `ollama pull qwen2.5:7b-instruct`), run the same demo against the real LLM:

```bash
export HERMES_OLLAMA_MODEL=qwen2.5:7b-instruct   # optional if you use this default
ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=ollama
# Slow local models: raise HTTP timeout (seconds), e.g. ollama_timeout_sec:=240.0
ros2 service call /hermes/ask hermes_msgs/srv/AskAgent "{prompt: '前に進んで'}"
```

See `examples/turtlebot_demo/README.md` for the demo.

For picking up this codebase (e.g. in Cursor), start with
`docs/plan.md` — single-file handoff covering architecture, current
status, conventions, and the remaining Cursor-ready tasks (T-21
through T-27 for the local-LLM milestone).

## Tests

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
colcon test --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --verbose
```

Current suite: 62 tests (30 in hermes_tools, 32 in hermes_agent) covering
SafetyFilter, MockClient, ShortTermMemory/ToolLog, all four tool adapters
against real rclpy, and three turtlebot_demo scenarios end-to-end.
