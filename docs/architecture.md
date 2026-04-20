# Architecture

Planner / Executor split (design option C).

```
┌──────────────┐  /hermes/plan (action)   ┌──────────────┐
│ PlannerNode  │ ───────────────────────▶ │ ExecutorNode │
│  (AgentNode) │                          │  ToolRegistry│◀─ tool plugins
│  LLM         │ ◀─── feedback/result ─── │  SafetyFilter│
└──────────────┘                          │  rclpy       │
       ▲                                  └──────────────┘
       │ /hermes/ask (srv)                        │
       │                                          ▼
       user                              /cmd_vel, tf, ...
```

## Key separations

- **PlannerNode** owns LLM I/O, memory, and user-facing `/hermes/ask`.
- **ExecutorNode** owns ToolRegistry, SafetyFilter, and all rclpy client
  objects. It is the single trust boundary where every ToolCall is
  validated before touching the robot.
- **hermes_msgs** is the typed contract between the two.

## Why this split

1. A single, auditable safety boundary (every ToolCall goes through
   Executor).
2. LLM latency and non-determinism are isolated from the real-time path.
3. Planner can live on a different host (cloud LLM) without changing the
   tool contract.

See `decisions.md` for alternatives and why they were not chosen for v1.
