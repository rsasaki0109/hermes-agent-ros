# Experiments

Record LLM evaluation runs and demo results here. One section per
experiment, newest at the top.

---

## 2026-04-21 — Ollama integration smoke (T-22 wiring), `qwen3:4b`

**Commit:** (post `OllamaClient` + launch `llm:=ollama`; see git log)
**LLM runtime:** Ollama HTTP at `http://127.0.0.1:11434`
**Model tag:** `qwen3:4b` via `HERMES_OLLAMA_MODEL` (machine default; not the
plan’s `qwen2.5:7b-instruct` pin)
**Stack:** `ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=ollama`
with `ROS_DOMAIN_ID=224` to avoid cross-talk with unrelated nodes on the host.

### 確認済み事実

- `GET /api/tags` returned a model list including `qwen3:4b`.
- `OllamaClient` unit tests (mocked HTTP) pass under `colcon test`; full suite
  **62** tests green (`hermes_tools` 30 + `hermes_agent` 32).
- With default client timeout **30 s**, `ros2 service call /hermes/ask ...`
  returned `reply='Ollama error: timed out'`, `executed_calls=[]`, `ok=True`
  (no tool call path — LLM returned an error string only).
- Direct `curl` to `/api/chat` with the same model showed **no response body
  within 180 s** in one trial (connection stall / inference not completing in
  that window). **Inference:** Ollama or the loaded model was not producing
  timely completions on this host during the measurement; not a ROS-side
  finding.

### 未確認 / 要確認

- End-to-end turtle motion with a **live** tool call from Ollama (forward /
  stop / turn_right) once `/api/chat` returns within timeout.
- Repeat with `qwen2.5:7b-instruct` (or another tool-stable model) and, if
  needed, `ollama_timeout_sec` above 120 s.

### 次アクション

- Restore Ollama health (`ollama ps`, restart daemon, or free GPU/RAM), then
  re-run the three prompts in `examples/turtlebot_demo/scenarios.yaml` and
  record Δpose.
- Launch now accepts `ollama_timeout_sec` (default **120**) alongside
  `ollama_host`.

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
