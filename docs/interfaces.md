# Interfaces

Canonical source for the contracts between packages. Code must match
this document; when they disagree, update code first and this doc in the
same PR.

## ROS2 interfaces (hermes_msgs)

| Kind | Name | Topic / Service / Action |
|---|---|---|
| srv | `AskAgent` | `/hermes/ask` |
| action | `ExecutePlan` | `/hermes/execute_plan` |
| msg | `ToolCall` | embedded in AskAgent / ExecutePlan |
| msg | `ToolResult` | embedded in ExecutePlan |
| msg | `AgentStatus` | `/hermes/agent_status` (topic) |

See the `.msg` / `.srv` / `.action` files in `src/hermes_msgs/` for the
exact fields.

## Python core classes

- `hermes_agent.agent_node.AgentNode` — PlannerNode. Owns LLM and the
  `AskAgent` server. Dispatches `ExecutePlan` action goals.
- `hermes_agent.executor_node.ExecutorNode` — `ExecutePlan` action
  server. Runs each `ToolCall` through SafetyFilter and ToolRegistry.
- `hermes_agent.safety_filter.SafetyFilter` — `check(ToolCall) -> (ok,
  sanitized, reason)`. Rules loaded from `safety_rules.yaml`.
- `hermes_agent.llm.base.LLMClient` — abstract. `chat(messages, tools)
  -> LLMResponse`.
- `hermes_tools.base.ToolInterface` — ABC. `name`, `description`,
  `input_schema`, `output_schema`, `validate(args) -> args`,
  `async run(args, ctx) -> dict`.
- `hermes_tools.base.ROS2ToolAdapter` — ToolInterface subclass with
  rclpy helpers (`_resolve_msg_type`, `_dict_to_msg`, `_msg_to_dict`,
  `_make_qos`).
- `hermes_tools.base.ToolContext` — value object
  `{ros_node, tf_buffer, deadline, logger}`.
- `hermes_tools.registry.ToolRegistry` — loads `tools.yaml`, exposes
  `get(name)`, `specs()` (LLM-facing schema list).

## Tool schemas (v1)

### topic_subscriber_tool
- input: `{topic, msg_type, duration_sec<=5.0, max_samples<=100, qos}`
- output: `{samples: [{stamp, data}], count, dropped}`

### topic_publisher_tool
- input: `{topic, msg_type, payload, rate_hz?<=50, duration_sec?<=10}`
- output: `{published, status, error?}`

### service_call_tool
- input: `{service, srv_type, request, timeout_sec<=5}`
- output: `{response, status, error?}`

### action_client_tool
- input: `{action, action_type, goal, feedback, timeout_sec<=30}`
- output: `{result, status, feedback_log?}`
