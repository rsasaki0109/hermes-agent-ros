# turtlebot_demo

Demo-1: drive turtlesim from natural language via the hermes agent.

## Run

```bash
colcon build --symlink-install
source install/setup.bash
ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=mock
ros2 service call /hermes/ask hermes_msgs/srv/AskAgent "{prompt: '前に進んで'}"
```

## Scenarios

See `scenarios.yaml`. The three baseline prompts:
- "前に進んで" — publishes positive `linear.x` on `/turtle1/cmd_vel`
- "止まって" — publishes zero Twist on `/turtle1/cmd_vel`
- "右に回って" — publishes negative `angular.z` on `/turtle1/cmd_vel`

SafetyFilter clips `linear.x` to 0.5 m/s and `angular.z` to 1.0 rad/s
per `config/safety_rules.yaml`.
