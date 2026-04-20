# Architecture Decisions

## ADR-001: Planner / Executor split (not agent-centric single node)

**Status:** Accepted (2026-04-20).

Options considered:
- A. Agent-centric (single node, LLM + tools + memory)
- B. Distributed tool nodes (every tool is its own node)
- C. Planner / Executor split with in-process tool plugins

**Decision:** C.

**Why not A:** LLM waits block ROS2 callbacks; single trust boundary is
harder; crash kills everything.

**Why not B (yet):** goal/result overhead for every tool call; tf
buffers and QoS get duplicated; MVP effort too large.

**Migration path:** `ToolInterface` is the seam — swap
`InProcessAdapter` for `RemoteNodeAdapter` to move toward option B.

## ADR-002: Target ROS2 Jazzy

**Status:** Accepted (2026-04-20). Superseded design note: originally
Humble was the stated target; switched to Jazzy after the dev
environment review.

All development, tests, and CI run on Jazzy. Python 3.12 is assumed
(Jazzy default). Humble compatibility is no longer a requirement —
Jazzy-specific features may be used freely.

## ADR-003: Tools are coroutines that may block

**Status:** Accepted (2026-04-20).

Tools declare `async def run(...)` to leave room for cooperative
concurrency, but v1 implementations use blocking primitives
(`time.sleep`, `wait_for_server`) inside the coroutine. rclpy's Task
system does not drive an asyncio event loop, so `asyncio.sleep` raises
"no running event loop" when awaited from an action-server callback.

The ExecutorNode runs under `MultiThreadedExecutor` +
`ReentrantCallbackGroup`, so blocking one thread does not starve other
callbacks. If we later add high-throughput concurrent tools, this is
the place to swap in proper async I/O.

## Deferred (not in v1)

- AnthropicClient / OpenAIClient real implementations (T-07).
- Long-term memory / RAG (v1.2).
- Multi-agent / per-tool permission (v2, ties into option B).
- C++ ToolNode implementations (v2).
- tf_lookup / topic_list / node_list / param_get / param_set /
  rosbag_slice tools (v1.1).
