# hermes-agent-ros — implementation plan and Cursor handoff

Single-file handoff document. Readers: whoever picks this up next in
Cursor (or any editor) and wants to continue building. Complementary
docs: `architecture.md` (design), `decisions.md` (ADRs),
`interfaces.md` (contracts), `experiments.md` (results log).

Last reviewed: 2026-04-21.

---

## 0. TL;DR

- ROS2 Jazzy, Python 3.12, 4 ament packages (`hermes_msgs`,
  `hermes_agent`, `hermes_tools`, `hermes_bringup`).
- Planner (`AgentNode`) + Executor (`ExecutorNode`) over
  `hermes_msgs/ExecutePlan` action. SafetyFilter is the single trust
  boundary.
- 4 tools implemented (`topic_publisher`, `topic_subscriber`,
  `service_call`, `action_client`). 1 demo (turtlesim, 3 scenarios).
- 59 tests green under `colcon test`. Live turtlesim demo works with
  the rule-based `MockClient`.
- **Next job:** replace the stub `AnthropicClient` with a local-LLM
  backend (Ollama preferred). See §5.

Build / test / run once:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --verbose                    # expect 59 tests green
ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=mock
ros2 service call /hermes/ask hermes_msgs/srv/AskAgent "{prompt: '前に進んで'}"
```

---

## 1. Architecture recap

```
┌──────────────┐  /hermes/execute_plan (action)   ┌──────────────┐
│ AgentNode    │ ───────────────────────────────▶ │ ExecutorNode │
│  LLMClient   │                                  │ ToolRegistry │◀─ in-proc
│  ShortTerm   │ ◀──── feedback / result ──────── │ SafetyFilter │   tool plugins
│  ToolLog     │                                  │ rclpy clients│
└──────────────┘                                  └──────────────┘
       ▲                                                  │
       │ /hermes/ask (srv)                                ▼
       user                                      /turtle1/cmd_vel, ...
```

- Everything between the LLM and the robot is typed with
  `hermes_msgs/ToolCall` + `ToolResult`.
- `ToolInterface` is the tool contract. Tools in v1 run in-process
  inside the Executor; the seam is deliberately thin so each tool
  can later be promoted to its own ROS2 node without touching the
  Planner (see ADR-001).

Key paths to read first, in this order, to get the model in your head:

1. `src/hermes_msgs/action/ExecutePlan.action`
2. `src/hermes_tools/hermes_tools/base.py` (ToolInterface / Adapter / Context)
3. `src/hermes_agent/hermes_agent/safety_filter.py`
4. `src/hermes_agent/hermes_agent/executor_node.py`
5. `src/hermes_agent/hermes_agent/agent_node.py`
6. `src/hermes_agent/hermes_agent/llm/base.py` + `mock_client.py`

---

## 2. What is done (task ledger)

| ID | Task | Files | Tests |
|---|---|---|---|
| T-01 | Monorepo scaffolding | all package.xml / setup.py / resource/ | build only |
| T-02 | hermes_msgs | msg/*, srv/*, action/* | import smoke |
| T-03 | ToolInterface base | `hermes_tools/base.py` | 6 |
| T-04 | ToolRegistry + tools.yaml | `hermes_tools/registry.py` | 5 |
| T-05 | schemas.py (rosidl ↔ JSON schema) | `hermes_tools/schemas.py` | 6 |
| T-06 | LLMClient + MockClient | `llm/base.py`, `llm/mock_client.py` | 5 |
| T-08 | SafetyFilter | `hermes_agent/safety_filter.py` | 9 |
| T-09 | ExecutorNode | `hermes_agent/executor_node.py` | 3 |
| T-10 | AgentNode + planner | `hermes_agent/agent_node.py` | 3 |
| T-11 | topic_subscriber_tool | `hermes_tools/topic_subscriber_tool.py` | 3 |
| T-12 | topic_publisher_tool | `hermes_tools/topic_publisher_tool.py` | 3 |
| T-13 | service_call_tool | `hermes_tools/service_call_tool.py` | 3 |
| T-14 | action_client_tool | `hermes_tools/action_client_tool.py` | 3 |
| T-15 | Memory (ShortTerm + ToolLog) | `hermes_agent/memory/*` | 5 |
| T-16 | agent.launch.py | `hermes_bringup/launch/agent.launch.py` | manual |
| T-17 | turtlebot_demo launch + prompts | `turtlebot_demo.launch.py`, `system_prompt.md` | manual |
| T-18 | E2E 3-scenario tests | `test/test_scenarios_e2e.py` | 3 |
| T-19 | CI workflow | `.github/workflows/ci.yml` | — |
| T-20 | Docs | `docs/*` | — |

Total: 59 tests green. See `experiments.md` for live demo records.

---

## 3. What is not done

### 3.1 T-07 is being redirected

Originally T-07 was `AnthropicClient`. We are switching to **local LLMs**
(see §4 below). The file `src/hermes_agent/hermes_agent/llm/anthropic_client.py`
stays as a stub — keep it for future cloud-fallback use but do not invest
effort there in v1.

### 3.2 New tasks (Cursor picks these up)

| ID | Task | Unblocks |
|---|---|---|
| T-21 | Pick and install a local LLM runtime (§4) | everything below |
| T-22 | `OllamaClient` — native `/api/chat` with tool use | live LLM demo |
| T-23 | (optional) `OpenAICompatClient` — generic `/v1/chat/completions` | LM Studio / vLLM / llama-server users |
| T-24 | Wire `llm:=ollama` / `llm:=openai-compat` through `agent.launch.py` | runtime swap |
| T-25 | `experiments.md` entry: live local-LLM run of the 3 scenarios | validation |
| T-26 | Tune `system_prompt.md` for the chosen local model if needed | passes the 3 scenarios |
| T-27 | (optional) JSON-mode / forced-tool fallback for weaker models | robustness |

Full specs in §6.

---

## 4. Local LLM plan

### 4.1 Runtime options

| Runtime | Protocol | Tool use | Notes |
|---|---|---|---|
| **Ollama** | native `/api/chat` + OpenAI-compat `/v1/chat/completions` | yes (since Ollama 0.3+) | easiest, one apt/brew install, manages model files |
| llama.cpp `llama-server` | OpenAI-compat `/v1` | partial, depends on model / chat template | maximum control, no extra runtime |
| LM Studio | OpenAI-compat `/v1` | yes (recent builds) | GUI-first, handy for model experiments |
| vLLM | OpenAI-compat `/v1` | yes | GPU-heavy; best for high throughput |

Recommendation: **Ollama** for the first pass. One install, caches
models under `~/.ollama/`, and the Python client is a thin HTTP
wrapper. If Ollama tool use is flaky on the chosen model, fall back to
`OpenAICompatClient` against LM Studio or `llama-server`.

### 4.2 Model choice

Tool use needs a model that (a) reliably emits the expected function
call schema and (b) handles Japanese prompts. Candidates:

- `qwen2.5:7b-instruct` — strong on tool use, multilingual incl. JP,
  fits on a 12 GB GPU.
- `llama3.1:8b-instruct` — good tool use, good JP, slightly weaker
  than Qwen at structured output in our experience.
- `hermes-3-llama-3.1:8b` — Nous Research fine-tune specifically tuned
  for tool use (fits the repo's spiritual lineage).
- `deepseek-r1:7b` — reasoning model, use only if tool-use fine-tune
  is available; not a first choice.

Pick one, pin the tag in `agent_params.yaml`, record it in the
experiment log.

### 4.3 Tool use protocol (Ollama native)

Ollama's `/api/chat` accepts a `tools` array in the same shape as the
OpenAI function-calling schema:

```json
{
  "model": "qwen2.5:7b-instruct",
  "messages": [
    {"role": "system", "content": "<system prompt>"},
    {"role": "user", "content": "前に進んで"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "topic_publisher_tool",
        "description": "...",
        "parameters": { "<json schema>" }
      }
    }
  ],
  "stream": false
}
```

Response:

```json
{
  "message": {
    "role": "assistant",
    "content": "前進します",
    "tool_calls": [{
      "function": {
        "name": "topic_publisher_tool",
        "arguments": { "topic": "/turtle1/cmd_vel", ... }
      }
    }]
  }
}
```

Map one-to-one to `LLMResponse(message=..., tool_calls=[ToolCallRequest])`.
`ToolRegistry.specs()` already returns the input/output schemas we need;
just wrap each one in `{"type": "function", "function": {...}}`.

---

## 5. Handoff notes for Cursor

### 5.1 Environment

- ROS2 **Jazzy** under `/opt/ros/jazzy`. `source setup.bash` first or
  nothing works.
- Python **3.12**. `rclpy`, `rosidl_runtime_py`, `pyyaml` are required.
- Optional: `ollama` CLI + Python package for T-22. Install with
  `curl -fsSL https://ollama.com/install.sh | sh` and `pip install
  ollama`. Do **not** put `ollama` in `package.xml` — keep it a pip
  dependency so the repo still builds without an LLM runtime.

### 5.2 Conventions used in this repo

- Every tool is `async def run(args, ctx)` but uses blocking
  primitives (`time.sleep`, `wait_for_server`) inside. rclpy's Task
  system does **not** drive an asyncio loop; `asyncio.sleep` hangs
  from an action-server callback. See ADR-003.
- Integration fixtures that init/shutdown rclpy are `scope='module'`.
  Function-scoped init/shutdown triggers FastRTPS shared-memory port
  collisions (`Failed init_port fastrtps_port7009`).
- Comments are intentionally sparse. Only the "why" when it is
  non-obvious — no "this publishes to X" narration.
- No `Co-Authored-By` in commits (user preference).

### 5.3 Where to put new code

- New tool → `hermes_tools/hermes_tools/<name>_tool.py`, add to
  `_default_modules` in `registry.py`, add to `tools.yaml`, add
  integration test with `scope='module'` rclpy fixture.
- New LLM client → `hermes_agent/hermes_agent/llm/<name>_client.py`
  subclass of `LLMClient`. Register in `agent_node.main` (or better,
  in a small factory keyed off a param).
- New safety rule → edit `safety_filter.py` **and** add a rule to
  `config/safety_rules.yaml`. Cover with a unit test that reads a
  temp yaml.

### 5.4 Known quirks / gotchas

- `ros:jazzy-ros-base` does **not** ship `example_interfaces` or
  `std_srvs` by default. CI installs them explicitly; do the same on
  fresh dev machines.
- turtlesim publishes `/turtle1/pose` with **best-effort** QoS. To
  read it from the CLI: `ros2 topic echo --qos-reliability best_effort /turtle1/pose`.
- `MockClient` emits `linear.x = 1.0` and the `SafetyFilter` clips it
  to `0.5`. If you widen the limit in `safety_rules.yaml`, update the
  matching assertion in `test_scenarios_e2e.py`.

### 5.5 Commit style

One logical change per commit. Imperative subject (≤ 72 chars),
body explains the *why* not the *what*. Examples already in the
history are representative. Do **not** squash; the existing log
tells the design story.

---

## 6. Detailed specs for the next tasks

### T-21. Install Ollama and pull a model

Input: this plan.
Output: a local Ollama daemon serving `http://localhost:11434` and at
least one tool-use-capable model pulled.

Steps:
1. `curl -fsSL https://ollama.com/install.sh | sh`
2. `systemctl --user enable --now ollama` (or `ollama serve &`)
3. `ollama pull qwen2.5:7b-instruct` (or alternative from §4.2)
4. Smoke test: `curl http://localhost:11434/api/chat -d '{"model":
   "qwen2.5:7b-instruct", "messages":[{"role":"user","content":"hi"}],
   "stream": false}'`

Done when: the curl returns a non-empty `message.content`.

### T-22. `OllamaClient` implementation

Input: §4.3 protocol reference; `ToolRegistry.specs()` output shape
(see `test_registry.py::test_specs_sorted`).

Output: `src/hermes_agent/hermes_agent/llm/ollama_client.py` exposing
`class OllamaClient(LLMClient)`.

Constructor:
```python
OllamaClient(
    host: str = 'http://localhost:11434',
    model: str = 'qwen2.5:7b-instruct',
    temperature: float = 0.2,
    timeout_sec: float = 30.0,
)
```

`chat(messages, tools, system='')` must:
1. Build the Ollama messages array: prepend `{"role": "system", ...}`
   if `system` is non-empty, then map `Turn.role` ∈
   `{'user','assistant','tool'}` directly. For `tool` turns include
   `{"role":"tool", "tool_call_id": t.tool_call_id, "content": t.content}`.
2. Build the tools array by wrapping each `ToolRegistry.specs()` entry
   into `{"type":"function","function":{"name":..., "description":...,
   "parameters": spec["input_schema"]}}`.
3. POST to `{host}/api/chat` with `stream=false`.
4. Parse the response: `message.content` → `LLMResponse.message`;
   `message.tool_calls[*]` → `ToolCallRequest(call_id=uuid4, tool_name=
   function.name, args=function.arguments)`.

Tests (`test/test_ollama_client.py`):
- Mock `httpx.post` (or `requests.post`) to return a canned response;
  assert the request body has the expected `tools` and that the
  parsed `LLMResponse` contains a `ToolCallRequest` for
  `topic_publisher_tool` with the right args.
- Mark a live-server test with
  `@pytest.mark.skipif(not ollama_reachable(), reason='...')` so CI
  without Ollama passes.

Done when: unit tests pass; `python -c "from hermes_agent.llm.ollama_client
import OllamaClient; print(OllamaClient().chat([...], [...]))"` returns
a sensible structure against a live daemon.

### T-23 (optional). `OpenAICompatClient`

Same shape as T-22 but POST to `{base_url}/v1/chat/completions` and
parse `choices[0].message.tool_calls`. Useful for LM Studio, vLLM,
`llama-server`. Skip unless the Ollama path hits a wall.

### T-24. Wire `llm` launch arg

Edit `src/hermes_bringup/launch/agent.launch.py` so the `llm` arg is
read by a tiny factory in `agent_node.main`:

```python
def _make_llm(provider: str) -> LLMClient:
    if provider == 'mock': return MockClient()
    if provider == 'ollama': return OllamaClient(model=os.environ.get(
        'HERMES_OLLAMA_MODEL', 'qwen2.5:7b-instruct'))
    if provider == 'openai-compat': return OpenAICompatClient(...)
    raise ValueError(f'unknown llm provider: {provider!r}')
```

Read the node parameter `llm_provider` and pass it in. Keep `mock` as
the default so the existing test suite is unaffected.

### T-25. Live local-LLM demo run

Input: §6 T-24 complete, turtlesim installed.
Output: a new dated entry in `docs/experiments.md` with:
- Model tag (e.g. `qwen2.5:7b-instruct`)
- The three prompts from `scenarios.yaml`
- Observed `/turtle1/pose` deltas
- Time-to-first-tool-call in seconds
- Any failure modes (wrong tool chosen, wrong args, timeouts)

Done when: at least the `forward` scenario succeeds end-to-end with a
real local model. Document stop and turn-right results even if they
fail — that is the point of the log.

### T-26. Tune system prompt if the model struggles

Edit `examples/turtlebot_demo/prompts/system_prompt.md`. If the model
fabricates topics or picks the wrong tool, add:
- An explicit example ToolCall JSON in the prompt
- A "You must call exactly one tool per turn unless stopping" rule
- A cap on `duration_sec` consistent with `safety_rules.yaml`

Update `docs/experiments.md` with the before/after pass counts.

### T-27 (optional). JSON-mode / forced-tool fallback

If Ollama's `tool_calls` output is unreliable for the chosen model,
switch to constrained JSON output: add `format: 'json'` to the
request and change the system prompt to instruct the model to emit

```json
{"tool_name": "...", "args": {...}}
```

Parse that manually into `ToolCallRequest`. Gate this behind a
constructor flag `json_mode=True` so both paths coexist.

---

## 7. Unchanged deferrals (still not in v1)

- AnthropicClient / OpenAIClient cloud backends (deprioritised).
- Long-term memory / RAG (v1.2).
- Multi-agent / per-tool permission (v2, ties into ADR-001 option B).
- C++ ToolNode implementations (v2).
- `tf_lookup`, `topic_list`, `node_list`, `param_get`, `param_set`,
  `rosbag_slice` tools (v1.1).

---

## 8. Acceptance criteria for the local-LLM milestone

The milestone is done when **all** of the following are true:

1. `colcon test` still reports 59+ tests, 0 failures.
2. `ros2 launch hermes_bringup turtlebot_demo.launch.py llm:=ollama`
   brings up a working stack against a local Ollama daemon.
3. `ros2 service call /hermes/ask ...` with `前に進んで` results in
   `/turtle1/cmd_vel` publishes that move the simulated turtle at
   least 0.3 m in `x`.
4. `docs/experiments.md` has an entry dated 2026-04-?? with the
   model tag and the three-scenario results.
5. `README.md` `llm:=mock` example is augmented with an
   `llm:=ollama` example.

That is the ship bar for v1.0.
