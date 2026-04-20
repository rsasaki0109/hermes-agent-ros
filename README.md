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
