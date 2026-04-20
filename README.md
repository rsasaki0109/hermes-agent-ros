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
- `rclpy`, `ament_python`, `anthropic` (optional)

## Quickstart

```bash
colcon build --symlink-install
source install/setup.bash
ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=mock
ros2 service call /hermes/ask hermes_msgs/srv/AskAgent "{prompt: '前に進んで'}"
```

See `examples/turtlebot_demo/README.md` for the demo.
