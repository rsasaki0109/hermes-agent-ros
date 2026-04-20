"""HTTP client for Ollama's native /api/chat with tool definitions."""
from __future__ import annotations

import json
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import LLMClient, LLMResponse, ToolCallRequest, Turn


class OllamaClient(LLMClient):
    """POST to ``{host}/api/chat`` with OpenAI-style tools on the wire."""

    def __init__(
        self,
        host: str = 'http://localhost:11434',
        model: str = 'qwen2.5:7b-instruct',
        temperature: float = 0.2,
        timeout_sec: float = 120.0,
    ) -> None:
        self._host = host.rstrip('/')
        self._model = model
        self._temperature = float(temperature)
        self._timeout = float(timeout_sec)

    def chat(
        self,
        messages: list[Turn],
        tools: list[dict],
        system: str = '',
    ) -> LLMResponse:
        body: dict[str, Any] = {
            'model': self._model,
            'messages': _turns_to_ollama_messages(messages, system),
            'stream': False,
            'options': {'temperature': self._temperature},
        }
        wrapped = _wrap_tools_for_ollama(tools)
        if wrapped:
            body['tools'] = wrapped

        raw = json.dumps(body).encode('utf-8')
        req = Request(
            f'{self._host}/api/chat',
            data=raw,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(req, timeout=self._timeout) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
        except HTTPError as e:
            err_body = ''
            try:
                err_body = e.read().decode('utf-8', errors='replace')
            except Exception:
                pass
            return LLMResponse(
                message=f'Ollama HTTP {e.code}: {err_body or e.reason}',
            )
        except URLError as e:
            return LLMResponse(message=f'Ollama request failed: {e.reason}')
        except (json.JSONDecodeError, OSError) as e:
            return LLMResponse(message=f'Ollama error: {e}')

        return _parse_chat_response(payload)


def ollama_reachable(host: str = 'http://localhost:11434') -> bool:
    """True if ``GET {host}/api/tags`` succeeds (quick probe for live tests)."""
    h = host.rstrip('/')
    req = Request(f'{h}/api/tags', method='GET')
    try:
        with urlopen(req, timeout=0.75) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def _wrap_tools_for_ollama(specs: list[dict]) -> list[dict]:
    out: list[dict] = []
    for spec in specs:
        out.append({
            'type': 'function',
            'function': {
                'name': spec['name'],
                'description': spec.get('description', ''),
                'parameters': spec.get('input_schema', {'type': 'object'}),
            },
        })
    return out


def _turns_to_ollama_messages(
    messages: list[Turn],
    system: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system:
        out.append({'role': 'system', 'content': system})
    for t in messages:
        if t.role == 'system':
            continue
        if t.role == 'user':
            out.append({'role': 'user', 'content': t.content})
        elif t.role == 'assistant':
            out.append({'role': 'assistant', 'content': t.content})
        elif t.role == 'tool':
            msg: dict[str, Any] = {'role': 'tool', 'content': t.content}
            if t.tool_call_id:
                msg['tool_call_id'] = t.tool_call_id
            if t.tool_name:
                msg['name'] = t.tool_name
            out.append(msg)
    return out


def _parse_chat_response(payload: dict) -> LLMResponse:
    msg = payload.get('message') or {}
    text = msg.get('content')
    if text is not None and not isinstance(text, str):
        text = str(text)

    tool_calls: list[ToolCallRequest] = []
    for tc in msg.get('tool_calls') or []:
        fn = tc.get('function') or {}
        name = fn.get('name')
        if not name:
            continue
        args = _coerce_arguments(fn.get('arguments'))
        tool_calls.append(
            ToolCallRequest(
                call_id=uuid.uuid4().hex,
                tool_name=name,
                args=args,
            ),
        )

    return LLMResponse(message=text or None, tool_calls=tool_calls)


def _coerce_arguments(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
