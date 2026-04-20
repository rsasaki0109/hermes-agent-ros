# Experiments

Record LLM evaluation runs and demo results here. One section per
experiment, newest at the top.

---

## 2026-04-20 — Demo-1 (turtlebot_demo) baseline, MockClient

**Commit:** (initial scaffolding, pre-commit)
**LLM:** MockClient (rule-based, deterministic)
**Stack:** AgentNode + ExecutorNode in-process, ReentrantCallbackGroup
on MultiThreadedExecutor, in-proc `topic_publisher_tool`.

### Scenario results

| Scenario | Prompt | Expected | Observed | Pass |
|---|---|---|---|---|
| forward | 前に進んで | linear.x>0 on /turtle1/cmd_vel | linear.x=0.5 (clipped from 1.0) | 3/3 |
| stop | 止まって | all-zero Twist | linear=(0,0,0), angular=(0,0,0) | 3/3 |
| turn_right | 右に回って | angular.z<0 | angular.z=-1.0 | 3/3 |

All three scenarios run with `REPEAT=3` inside the E2E test. The full
hermes_agent pytest suite (24 tests, covering SafetyFilter, MockClient,
ExecutorNode integration, AgentNode integration, and the three scenarios)
completes in ~23s.

### Observations

- `topic_publisher_tool` uses blocking `time.sleep` inside an `async def`
  coroutine. rclpy's Task system does not drive an asyncio loop, so
  pure-asyncio primitives (`asyncio.sleep`) hang with
  `RuntimeError: no running event loop`. This is fine because
  MultiThreadedExecutor + ReentrantCallbackGroup keep other callbacks
  responsive while the publisher blocks one thread.
- FastRTPS shared-memory port collisions appeared when many rclpy
  contexts were created and destroyed rapidly in a single pytest
  process. Fixed by making integration fixtures `scope='module'`.

### Deferred for follow-up

- No real LLM results yet (T-07 AnthropicClient is still a stub).
- No measurement of end-to-end latency. Instrumented `/hermes/agent_status`
  timestamps are available now (T-15 landed) but not yet recorded.

### 2026-04-20 addendum — live hardware-free demo

Ran `ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=mock` with
turtlesim on this machine. Pose telemetry observed:

| Prompt | Δx [m] | Δθ [rad] |
|---|---|---|
| 前に進んで | +1.32 | 0 |
| 右に回って | 0 | -2.91 |
| 止まって | 0 | 0 (velocities returned to 0) |

The response for "前に進んで" included the surfaced clipping note
`safety_note=linear.x clipped 1.000 -> 0.500`, confirming the trust
boundary works end-to-end.

### 2026-04-20 addendum — full tool suite

After T-11/T-13/T-14 landed, tool integration coverage is: publisher,
subscriber, service_call (std_srvs/Trigger), action_client
(example_interfaces/Fibonacci with feedback). Total 59 tests pass via
`colcon test` (see T-19).
