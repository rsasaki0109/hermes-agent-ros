# Experiments

Record LLM evaluation runs and demo results here. One section per
experiment, newest at the top.

---

## 2026-04-21 — Ollama on turtlesim (tool path + robustness fixes)

**LLM runtime:** Ollama `http://127.0.0.1:11434`  
**Model:** `qwen2.5:3b-instruct` (pulled on this host). `llama3.2:1b` answers
quickly but tool args are unreliable; `qwen3:4b` often stalled on `/api/chat`
(0 bytes / 180s); `qwen2.5:7b-instruct` cold-started ~90s then tool calls
could still hang in trials.

**Stack:** `ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=ollama`
with `HERMES_OLLAMA_MODEL=qwen2.5:3b-instruct`, `ollama_timeout_sec:=180.0`,
`ROS_DOMAIN_ID=224` (must be **≤232** for Fast DDS), optional
`ROS_LOCALHOST_ONLY=1` to avoid foreign `/hermes/ask` servers on the LAN.

### 確認済み事実

- `curl /api/chat` with tools: `qwen2.5:3b-instruct` returns well-formed
  `tool_calls` for 「前に進んで」 (wall ~22s including model load on first run).
- `turtlebot_demo` passes **`default_cmd_vel_topic:=/turtle1/cmd_vel`** into
  the agent so small models that omit `topic` still pass SafetyFilter.
- Duplicate node names on the default domain (e.g. two `/hermes_agent`) were
  observed when a manual launch and pytest shared discovery; pytest now picks
  a **random `ROS_DOMAIN_ID` in [200,230]** per session unless
  `HERMES_TEST_ROS_DOMAIN_ID` is set, and clears `ROS_LOCALHOST_ONLY`.
- JSON `null` for optional tool fields (e.g. `rate_hz`) no longer fails
  validation: optional object properties equal to `null` are dropped before
  schema checks (`hermes_tools/base.py`).
- **Executor crash (pre-fix, reproduced):** `geometry_msgs__msg__vector3__convert_from_py`
  assertion when the LLM emitted JSON **integers** for Vector3 components.
  **Fix:** when assigning into an existing float64 slot, coerce `int`→`float`
  in `_assign_fields`. Covered by `test_publish_accepts_int_components_for_float64_fields`.
- One logged manual run hit that crash on the first forward plan; subsequent
  asks returned `(executor unavailable)` because the executor process had died.

### Post-fix E2E — one session (same launch, 2026-04-21)

Measured `/turtle1/pose` (`ros2 topic echo ... --qos-reliability best_effort`)
before/after each `ros2 service call /hermes/ask` with `session_id:=e2e`.
Wall time is full service round-trip (Ollama + ExecutePlan + tool).

| Step | Prompt | wall [s] | `ok` | x before → after | θ before → after | Notes |
|------|--------|----------|------|------------------|------------------|-------|
| 1 | 前に進んで | 7.13 | true | 5.544 → 5.826 | 0 → 0 | **Δx ≈ +0.282 m**; tool had `linear.x=0.1`, `duration_sec=2`, `rate_hz=5`, `topic=/turtle1/cmd_vel`. Plan §8 asked **≥0.3 m** — not met on this run. |
| 2 | 止まって | 4.58 | true | 5.826 → 5.826 | 0 → 0 | Δ pose 0; zero `Twist` tool executed (`ok`). |
| 3 | 右に回って | 4.03 | true | 5.826 → 5.826 | 0 → 0 | **`executed_calls=[]`** — model returned no tool call; turtle did not turn. |

**推測:** Step 3 is a planner/model issue (multi-turn + weak 3B tool discipline),
not an executor regression.

### 次アクション

- For **Δx ≥ 0.3 m**: raise commanded `linear.x` / duration in prompt or
  `system_prompt.md`, or use a stronger model.
- For **turn_right**: retry with a fresh `session_id`, tune prompt, or
  stronger model; optional **T-26** / **T-27** from `docs/plan.md`.
- `colcon test`: **63** tests (**31** `hermes_tools` + **32** `hermes_agent`).

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
