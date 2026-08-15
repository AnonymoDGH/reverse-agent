"""Puente Anthropic-compatible sobre qwen-reverse.

qwen-reverse 0.1.4 incluye un endpoint Anthropic básico, pero no conserva
bloques tool_use/tool_result ni system prompts estructurados. Este puente usa
su API Python pública y completa esas traducciones para el bucle de agentes.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from qwen_reverse import create_chat, fetch_models, QwenError, QwenAuthError, QwenRateLimitError

app = FastAPI(title="Reverse Agent Bridge", version="2.0.0")


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    out: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            out.append(str(block.get("text", "")))
        elif kind == "thinking":
            # El razonamiento anterior no debe reinyectarse como instrucción.
            continue
        elif kind == "tool_result":
            value = text_of(block.get("content", ""))
            out.append(f"Resultado de herramienta {block.get('tool_use_id', '')}:\n{value}")
        elif kind in ("image", "document"):
            out.append(f"[{kind} adjunto]")
    return "\n".join(out)


def translate_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    system = text_of(body.get("system"))
    if system:
        messages.append({"role": "system", "content": system})
    for message in body.get("messages") or []:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "assistant" and isinstance(content, list):
            tool_calls = []
            text_parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(str(block.get("text", "")))
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id") or f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                        },
                    })
            translated = {"role": "assistant", "content": "\n".join(text_parts)}
            if tool_calls:
                translated["tool_calls"] = tool_calls
            messages.append(translated)
        else:
            messages.append({"role": role, "content": text_of(content)})
    return messages


def translate_tools(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        },
    } for tool in (body.get("tools") or [])]


def embedded_tool_calls(value: Any, real_names: set[str] | None = None) -> list[dict[str, Any]] | None:
    """Extrae llamadas aunque Qwen agregue texto antes o después del JSON.

    qwen-reverse exige que toda la respuesta sea JSON; Qwen a veces produce el
    objeto correcto seguido por una frase, y a veces emite VARIAS llamadas en
    el mismo turno (p.ej. Read + Bash encadenados) o deja el `{` inicial
    fragmentado por el streaming. Esta rutina recoge todas las llamadas.
    """
    if not isinstance(value, str):
        return None
    # Formato primario del bridge. La etiqueta evita que el backend web de
    # Qwen intente ejecutar por sí mismo nombres de herramientas locales.
    local_calls = []
    for match in re.finditer(r"<qwen_local_tool>\s*([\s\S]*?)\s*</qwen_local_tool>", value, re.IGNORECASE):
        try:
            call = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            continue
        arguments = call.get("arguments") or {}
        local_calls.append({
            "index": len(local_calls), "id": f"call_{uuid.uuid4().hex}", "type": "function",
            "function": {"name": call["name"], "arguments": json.dumps(arguments, ensure_ascii=False)},
        })
    if local_calls:
        return local_calls
    # Formato alternativo observado en conversaciones de varias herramientas:
    # [Tool call: Edit]\n{"file_path": ...}
    marked = []
    marker_re = re.compile(r"\[Tool call:\s*([^\]]+)\]\s*", re.IGNORECASE)
    markers = list(marker_re.finditer(value))
    for index, marker in enumerate(markers):
        section_end = markers[index + 1].start() if index + 1 < len(markers) else len(value)
        section = value[marker.end():section_end].lstrip()
        try:
            arguments, _ = json.JSONDecoder().raw_decode(section)
        except json.JSONDecodeError:
            continue
        if isinstance(arguments, dict):
            marked.append({
                "index": len(marked), "id": f"call_{uuid.uuid4().hex}", "type": "function",
                "function": {"name": marker.group(1).strip(), "arguments": json.dumps(arguments, ensure_ascii=False)},
            })
    if marked:
        return marked

    def is_valid_name(name: object) -> bool:
        return (
            isinstance(name, str)
            and bool(name)
            and (
                re.match(r"^local_tool_\d+$", name) is not None
                or (real_names is not None and name in real_names)
            )
        )

    def build(name: object, arguments: Any, keep_id: str | None = None) -> dict[str, Any] | None:
        if not is_valid_name(name) and keep_id is None:
            return None
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass
        return {
            "id": keep_id or f"call_{uuid.uuid4().hex}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments or {}, ensure_ascii=False)},
        }

    # Escaneo genérico, SIN parar tras la primera llamada: recoge `{...}`,
    # `[...]`, envoltorios `{"tool_calls":[...]}` y objetos sueltos contiguos,
    # en orden de aparición.
    decoder = json.JSONDecoder()
    found: list[tuple[int, dict[str, Any]]] = []
    scan_pos = 0
    length = len(value)
    while scan_pos < length:
        if value[scan_pos] not in "{[":
            scan_pos += 1
            continue
        seg = value[scan_pos:]
        try:
            candidate, end = decoder.raw_decode(seg)
        except json.JSONDecodeError:
            try:
                candidate, end = decoder.raw_decode(_close_json_tail(seg))
            except json.JSONDecodeError:
                scan_pos += 1
                continue
        if isinstance(candidate, dict):
            wrapped = candidate.get("tool_calls")
            if isinstance(wrapped, list):
                # Envoltura estilo Anthropic/Qwen nativo: el nombre viaja sin
                # restricción (la tool real se traduce después con alias_map).
                for item in wrapped:
                    if isinstance(item, dict) and isinstance(item.get("name"), str):
                        found.append((scan_pos, {"name": item["name"], "arguments": item.get("arguments") if "arguments" in item else item.get("input", {})}))
            elif (
                isinstance(candidate.get("name"), str)
                and candidate["name"] != ""
                and ("arguments" in candidate or "input" in candidate)
                and (
                    re.match(r"^local_tool_\d+$", candidate["name"]) is not None
                    or (real_names is not None and candidate["name"] in real_names)
                )
            ):
                # Protocolo plano (como qwen-reverse-agent): {"name":"Bash",
                # "arguments":{...}} suelto al final; solo si es una tool real.
                found.append((scan_pos, {
                    "name": candidate["name"],
                    "arguments": candidate.get("arguments") if "arguments" in candidate else candidate.get("input", {}),
                }))
            # Objetos sin nombre (p.ej. {"file_path":...}) se ignoran y el
            # escaneo continúa tras ellos: puede haber más llamadas después.
        elif isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    found.append((scan_pos, {"name": item["name"], "arguments": item.get("arguments") if "arguments" in item else item.get("input", {})}))
        scan_pos += max(end, 1)

    if not found:
        # Último rescate: fragmentos del protocolo plano con el `{` inicial
        # perdido por el streaming (p.ej. `},"name":"Bash"` o `":"Read"` a
        # mitad de mensaje), o la llamada truncada sin su llave de cierre.
        fragment_re = re.compile(r"(?::|[^\w])?\s*\"([A-Za-z_][A-Za-z0-9_]*)\"\s*,\s*\"arguments\"\s*:")
        seen_fingerprints = set()
        for match in fragment_re.finditer(value):
            name = match.group(1)
            if not is_valid_name(name):
                continue
            try:
                arguments, _ = decoder.raw_decode(value[match.end():])
            except json.JSONDecodeError:
                try:
                    arguments, _ = decoder.raw_decode(_close_json_tail(value[match.end():]))
                except json.JSONDecodeError:
                    continue
            if not isinstance(arguments, dict):
                continue
            fingerprint = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            found.append((match.start(), {"name": name, "arguments": arguments}))

    if not found:
        return None
    found.sort(key=lambda item: item[0])
    normalized = []
    for index, (_, call) in enumerate(found):
        normalized.append({
            "index": index,
            "id": f"call_{uuid.uuid4().hex}",
            "type": "function",
            "function": {"name": call["name"], "arguments": json.dumps(call["arguments"] or {}, ensure_ascii=False)},
        })
    return normalized or None


def model_name(body: dict[str, Any]) -> str:
    requested = str(body.get("model") or "")
    if requested.startswith("qwen"):
        return requested.removesuffix("-thinking")
    return os.getenv("QWEN_MODEL", "qwen3.8-max-thinking").removesuffix("-thinking")


ZEN_BASE_URL = os.getenv("ZEN_BASE_URL", "https://opencode.ai/zen/v1")


def zen_api_key() -> str | None:
    """Key de OpenCode Zen: env ZEN_API_KEY, o la key guardada de opencode local."""
    key = os.getenv("ZEN_API_KEY") or os.getenv("OPEN_CODE_API_KEY")
    if key:
        return key
    candidates = [
        os.path.expanduser("~/.local/share/opencode/auth.json"),
        os.path.expandvars("%USERPROFILE%\\.local\\share\\opencode\\auth.json"),
    ]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as handle:
                auth = json.load(handle)
            entry = auth.get("opencode") or auth.get("zen")
            if isinstance(entry, dict) and isinstance(entry.get("key"), str):
                return entry["key"]
        except (OSError, ValueError):
            continue
    return None


def provider_for(body: dict[str, Any]) -> tuple[str, str]:
    """Decide backend y modelo efectivo.

    Reglas:
    - modelo pedido o QWEN_MODEL con prefijo "opencode/" -> OpenCode Zen.
    - cualquier modelo pedido que no sea qwen (p.ej. claude-*, gpt-*, deepseek-*)
      -> Zen si hay key disponible.
    - resto -> qwen web.
    """
    requested = str(body.get("model") or "")
    env_model = os.getenv("QWEN_MODEL", "qwen3.8-max-thinking")
    if requested.startswith("opencode/"):
        return "zen", requested.removeprefix("opencode/")
    if env_model.startswith("opencode/"):
        return "zen", env_model.removeprefix("opencode/")
    if requested and not requested.startswith("qwen") and zen_api_key():
        return "zen", requested
    if not requested.startswith("qwen") and zen_api_key():
        return "zen", env_model.removesuffix("-thinking")
    return "qwen", model_name(body)


def tool_aliases(tools: list[dict[str, Any]]) -> dict[str, str]:
    return {
        f"local_tool_{index}": tool["function"].get("name", "")
        for index, tool in enumerate(tools)
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict)
    }


def tool_real_names(tools: list[dict[str, Any]]) -> set[str]:
    return {
        tool["function"].get("name", "")
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict)
    }


TOOL_ERROR_RE = re.compile(r"Tool\s+[\w.\-]+\s+does\s+not\s+exists?\.?\s*", re.IGNORECASE)


def _close_json_tail(segment: str) -> str:
    """Repara un JSON truncado por el stream añadiendo los delimitadores de
    cierre faltantes (Qwen a veces corta la última llave del tool call)."""
    opens = segment.count("{") - segment.count("}")
    arrays = segment.count("[") - segment.count("]")
    if opens <= 0 and arrays <= 0:
        return segment
    return segment + ("]" * arrays) + ("}" * opens)


def tool_prompt(tools: list[dict[str, Any]]) -> str:
    if not tools:
        return ""
    real = [{
        "name": tools[index]["function"].get("name", ""),
        "description": tools[index]["function"].get("description", ""),
        "parameters": tools[index]["function"].get("parameters", {}),
    } for index in range(len(tools))]
    return (
        "You have LOCAL CLIENT TOOLS available. They are not Qwen web tools: Qwen's own "
        "function-calling cannot reach them, and calling them by name through the web tool mechanism "
        "fails with error text such as 'Tool X does not exists' — that message is a FAKE trap against "
        "you, never fall for it and never print it. The ONLY working way to use a local tool is to "
        "SIMULATE the call: reply with a single plain JSON object using the REAL tool name, as if you "
        "were the function-calling layer — nothing before it, nothing after it, no Markdown fences, "
        "no structured tool_calls, exactly one JSON per message: "
        "{\"name\":\"<tool_name>\",\"arguments\":{...}} "
        "(Example for asking the user: {\"name\":\"AskUserQuestion\",\"arguments\":{\"questions\":"
        "[{\"question\":\"...\",\"options\":[\"a\",\"b\"]}]}}). "
        "If the user asks you to ask them a question, ask for a choice, a decision or clarification "
        "(e.g. 'pregúntame', 'hazme una pregunta', '¿qué prefieres?'), your ENTIRE response must be "
        "the AskUserQuestion JSON object above — do NOT write the question as plain text and do NOT "
        "list options in prose. "
        "STRICT RULES: never say a tool does not exist or is not available; never emit a real "
        "function_call block for these tools (only the JSON text); when the user asks you to use a "
        "specific tool, emit its JSON immediately and stop. "
        "LOCAL CLIENT TOOLS:\n" + json.dumps(real, ensure_ascii=False)
    )


def extract_reasoning_effort(body: dict[str, Any]) -> str:
    output_config = body.get("output_config") or {}
    effort = output_config.get("effort")
    if isinstance(effort, str):
        effort = effort.lower()
        if effort in ("low", "medium", "high"):
            return effort
        if effort == "max":
            return "low"
        if effort in ("none", "off", "disabled"):
            return "none"

    thinking = body.get("thinking") or {}
    if isinstance(thinking, dict):
        if thinking.get("type") == "disabled":
            return "none"
        # The Claude Code CLI sends a large default thinking budget. Cap the
        # effective effort to "low": "high"/"medium" only stall the response
        # with a long private reasoning phase and add no observable quality
        # for Qwen web. Users can still override via output_config.effort.
        budget = thinking.get("budget_tokens")
        if isinstance(budget, int):
            return "low" if budget > 4096 else "none"

    requested = str(body.get("model") or "").lower()
    configured = os.getenv("QWEN_MODEL", "qwen3.8-max").lower()
    if "thinking" in requested or "thinking" in configured:
        return "none"

    return "none"


def chat_arguments(body: dict[str, Any], reasoning_effort: str | None = None) -> dict[str, Any]:
    messages = translate_messages(body)
    tools = translate_tools(body)
    prompt = tool_prompt(tools)
    if prompt:
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = prompt + "\n\n" + str(messages[0].get("content") or "")
        else:
            messages.insert(0, {"role": "system", "content": prompt})
    return {
        "model": model_name(body),
        "messages": messages,
        "token": os.getenv("QWEN_TOKEN") or None,
        # Tool prompting/parsing is implemented here. Passing tools to
        # qwen-reverse activates its weaker "human intermediary" prompt and
        # can make Qwen fabricate "Tool X does not exist" responses.
        "tools": None,
        "stream": True,
        "reasoning_effort": reasoning_effort if reasoning_effort is not None else extract_reasoning_effort(body),
        "emit_tool_calls": False,
    }


def context_chars(body: dict[str, Any]) -> int:
    chars = len(text_of(body.get("system")))
    for message in body.get("messages") or []:
        chars += len(text_of(message.get("content")))
    return chars


def empty_retry_delays() -> list[float]:
    raw = os.getenv("QWEN_EMPTY_RETRY_DELAYS", "")
    if raw:
        try:
            parsed = [float(part.strip()) for part in raw.split(",") if part.strip()]
            if parsed:
                return parsed
        except ValueError:
            pass
    return [2.0, 4.0, 8.0, 15.0, 30.0]


async def collect_qwen_events(
    body: dict[str, Any],
    attempts: int | None = None,
    retry_delays: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Obtiene una respuesta completa y reintenta respuestas vacías.

    El backend web devuelve ocasionalmente un stream `done` sin contenido al
    enfriarse un límite. Eso no debe convertirse en una respuesta exitosa
    vacía. Los reintentos alternan el reasoning_effort ("none" en intentos
    impares) porque el modo con razonamiento a veces traba al backend con
    contexto largo, mientras que sin él responde de inmediato.
    """
    attempts = attempts if attempts is not None else int(os.getenv("QWEN_EMPTY_RETRIES", "5"))
    delays = list(retry_delays) if retry_delays else empty_retry_delays()
    if not delays:
        delays = [10.0]
    base_effort = extract_reasoning_effort(body)
    last_error: Exception | None = None
    for attempt in range(attempts):
        events: list[dict[str, Any]] = []
        effort = base_effort if attempt % 2 == 0 else "none"
        try:
            async for event in create_chat(**chat_arguments(body, reasoning_effort=effort)):
                events.append(event)
        except (QwenError, QwenAuthError, QwenRateLimitError) as error:
            last_error = error
        useful = any(
            event.get("type") in ("tool_calls", "image") or
            (event.get("type") in ("content", "reasoning") and str(event.get("data") or "").strip())
            for event in events
        )
        if useful:
            reasoning = "".join(str(e.get("data") or "") for e in events if e.get("type") == "reasoning")
            content = "".join(str(e.get("data") or "") for e in events if e.get("type") == "content")
            collapsed: list[dict[str, Any]] = []
            if reasoning:
                collapsed.append({"type": "reasoning", "data": reasoning})
            recovered = embedded_tool_calls(content, real_names=tool_real_names(translate_tools(body)))
            if recovered:
                alias_map = tool_aliases(translate_tools(body))
                for call in recovered:
                    function = call.get("function") or {}
                    function["name"] = alias_map.get(function.get("name"), function.get("name"))
                collapsed.append({"type": "tool_calls", "data": recovered})
            elif content:
                collapsed.append({"type": "content", "data": content})
            collapsed.extend(e for e in events if e.get("type") in ("tool_calls", "usage"))
            collapsed.append({"type": "done", "data": None})
            return collapsed
        if not last_error:
            last_error = QwenError(_empty_response_message(body, attempts, effort))
        if attempt + 1 < attempts:
            delay = delays[min(attempt, len(delays) - 1)]
            await asyncio.sleep(delay)
    raise last_error or QwenError(_empty_response_message(body, attempts, base_effort))


def _empty_response_message(body: dict[str, Any], attempts: int, effort: str) -> str:
    chars = context_chars(body)
    tokens = max(1, chars // 4)
    hint = (
        " reducí el contexto (el history pesa ~{tokens} tokens; /clear o achicar "
        "archivos ya leídos pueden bastar)" if tokens > 120_000 else
        " esperá un momento y reintentá" if tokens < 60_000 else
        " probá esperar un rato o achicar el contexto con /clear"
    )
    return (
        f"Qwen devolvió una respuesta vacía tras {max(1, attempts)} intentos "
        f"(context ~{tokens} tokens, reasoning_effort={effort or 'none'}). "
        f"El backend de streaming devolvió done sin contenido;{hint}."
    )


def zen_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Traduce mensajes Anthropic a chat completions OpenAI, conservando ids.

    Los bloques tool_result se convierten en mensajes con role "tool" y
    tool_call_id apuntando al id del tool_use original; los bloques de texto
    de ese mismo mensaje de usuario quedan como mensaje user aparte.
    """
    messages: list[dict[str, Any]] = []
    system = text_of(body.get("system"))
    if system:
        messages.append({"role": "system", "content": system})
    for message in body.get("messages") or []:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "assistant" and isinstance(content, list):
            tool_calls = []
            text_parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(str(block.get("text", "")))
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block.get("id") or f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                        },
                    })
            if tool_calls:
                messages.append({"role": "assistant", "content": "\n".join(text_parts) or None, "tool_calls": tool_calls})
            else:
                messages.append({"role": "assistant", "content": "\n".join(text_parts)})
        elif role == "user" and isinstance(content, list):
            tool_results = []
            text_parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    tool_results.append(block)
                elif block.get("type") == "text":
                    text_parts.append(str(block.get("text", "")))
            if text_parts:
                messages.append({"role": "user", "content": "\n".join(text_parts)})
            for block in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id") or f"call_{uuid.uuid4().hex}",
                    "content": text_of(block.get("content", "")),
                })
        else:
            messages.append({"role": role, "content": text_of(content)})
    return messages


def zen_chat_arguments(body: dict[str, Any]) -> dict[str, Any]:
    provider, model = provider_for(body)
    payload: dict[str, Any] = {
        "model": model,
        "messages": zen_messages(body),
        "stream": True,
    }
    tools = translate_tools(body)
    if tools:
        payload["tools"] = tools
    if isinstance(body.get("max_tokens"), int):
        payload["max_tokens"] = body["max_tokens"]
    effort = extract_reasoning_effort(body)
    if effort and effort != "none":
        payload["reasoning_effort"] = effort
    return payload


async def live_zen_anthropic_stream(body: dict[str, Any]):
    """Traduce un stream de chat completions de OpenCode Zen a SSE Anthropic."""
    import aiohttp
    key = zen_api_key()
    if not key:
        yield sse("error", {"type": "error", "error": {
            "type": "authentication_error",
            "message": "Falta la API key de OpenCode Zen. Configurá ZEN_API_KEY (o tené la key "
                       "de opencode en ~/.local/share/opencode/auth.json).",
        }})
        return
    _, zen_model = provider_for(body)
    payload = zen_chat_arguments(body)
    display_model = str(body.get("model") or zen_model)
    message_id = f"msg_{uuid.uuid4().hex}"
    yield sse("message_start", {"type": "message_start", "message": {
        "id": message_id, "type": "message", "role": "assistant",
        "model": display_model, "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }})
    index = 0
    open_blocks: dict[str, int] = {}
    stop_reason = "end_turn"
    usage = {"input_tokens": 0, "output_tokens": 0}
    has_received_data = False
    pending_tools: dict[int, dict[str, Any]] = {}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{ZEN_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                if resp.status not in (200, 201):
                    error_text = (await resp.text())[:500]
                    kind = "authentication_error" if resp.status == 401 else "rate_limit_error" if resp.status == 429 else "api_error"
                    yield sse("error", {"type": "error", "error": {
                        "type": kind,
                        "message": f"OpenCode Zen {resp.status}: {error_text or 'sin detalle'}",
                    }})
                    return
                async for raw in resp.content:
                    for line in raw.decode("utf-8", errors="replace").splitlines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(chunk, dict):
                            continue
                        usage_chunk = chunk.get("usage")
                        if isinstance(usage_chunk, dict):
                            usage = {
                                "input_tokens": usage_chunk.get("prompt_tokens", 0),
                                "output_tokens": usage_chunk.get("completion_tokens", 0),
                            }
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        finish_reason = choices[0].get("finish_reason")
                        text_delta = str(delta.get("content") or "") if delta.get("content") is not None else ""
                        reasoning = str(delta.get("reasoning_content") or "") if delta.get("reasoning_content") is not None else ""
                        tool_deltas = delta.get("tool_calls") or []
                        if reasoning:
                            has_received_data = True
                            if "thinking" not in open_blocks:
                                open_blocks["thinking"] = index
                                yield sse("content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "thinking", "thinking": "", "signature": "opencode-zen"}})
                                index += 1
                            yield sse("content_block_delta", {"type": "content_block_delta", "index": open_blocks["thinking"], "delta": {"type": "thinking_delta", "thinking": reasoning}})
                        if text_delta:
                            has_received_data = True
                            if "text" not in open_blocks:
                                open_blocks["text"] = index
                                yield sse("content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}})
                                index += 1
                            yield sse("content_block_delta", {"type": "content_block_delta", "index": open_blocks["text"], "delta": {"type": "text_delta", "text": text_delta}})
                        for tc in tool_deltas:
                            if not isinstance(tc, dict):
                                continue
                            t_index = tc.get("index", len(pending_tools))
                            slot = pending_tools.setdefault(t_index, {"id": None, "name": "", "arguments": ""})
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                slot["name"] = fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"] += fn["arguments"]
                            has_received_data = True
                        if finish_reason:
                            break
            for slot in pending_tools.values():
                name = slot["name"] or "tool"
                try:
                    args = json.loads(slot["arguments"]) if slot["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                stop_reason = "tool_use"
                tool_index = index
                index += 1
                yield sse("content_block_start", {"type": "content_block_start", "index": tool_index, "content_block": {
                    "type": "tool_use", "id": slot["id"] or f"toolu_{uuid.uuid4().hex}", "name": name, "input": {},
                }})
                if args:
                    yield sse("content_block_delta", {"type": "content_block_delta", "index": tool_index, "delta": {
                        "type": "input_json_delta", "partial_json": json.dumps(args, ensure_ascii=False),
                    }})
                yield sse("content_block_stop", {"type": "content_block_stop", "index": tool_index})
        except Exception as exc:
            import sys
            import traceback
            print(f"[qwen-bridge zen exception] {exc}", file=sys.stderr, flush=True)
            if os.getenv("QWEN_BRIDGE_DEBUG"):
                print("[qwen-bridge zen traceback]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
            yield sse("error", {"type": "error", "error": {
                "type": "api_error",
                "message": f"OpenCode Zen Engine Error: {exc}",
            }})
            return

    if not has_received_data and not pending_tools:
        yield sse("error", {"type": "error", "error": {
            "type": "api_error", "message": "OpenCode Zen devolvió una respuesta vacía.",
        }})
        return
    for block_index in open_blocks.values():
        yield sse("content_block_stop", {"type": "content_block_stop", "index": block_index})
    yield sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": usage})
    yield sse("message_stop", {"type": "message_stop"})


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def live_anthropic_stream(body: dict[str, Any]):
    import sys
    alias_map = tool_aliases(translate_tools(body))
    real_names = tool_real_names(translate_tools(body))
    message_id = f"msg_{uuid.uuid4().hex}"
    model = body.get("model") or os.getenv("QWEN_MODEL", "qwen3.8-max")
    yield sse("message_start", {"type": "message_start", "message": {
        "id": message_id, "type": "message", "role": "assistant",
        "model": model, "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }})
    index = 0
    open_blocks: dict[str, int] = {}
    stop_reason = "end_turn"
    usage = {"input_tokens": 0, "output_tokens": 0}
    has_received_data = False
    # Un tool_call de Qwen llega fragmentado en N event_redirects; ningún chunk
    # individual contiene el JSON completo. Retenemos un "tail" hasta que
    # embedded_tool_calls pueda reconocer el objeto completo, sin que eso
    # retrase el texto normal (que no parece JSON y se libera de inmediato).
    stream_tail = ""
    MAX_JSON_TAIL = 6000

    def tail_could_be_json(value: str) -> bool:
        stripped = value.lstrip()
        first = stripped[:1]
        return (
            first in "{[\""
            or stripped.startswith("<qwen_local")
            or stripped.startswith("_tool")
            or stripped.startswith("name")
            or first == ":"
        )

    def clean_local_markers(value: str) -> str:
        # Elimina fragmentos residuales del cierre de la envoltura local
        # (p.ej. "</qwen_local_tool>", "</qwen_local", "_tool>", o el
        # prefijo malformado "<qwen_local{" sin su parte "_tool").
        if "qwen_local" not in value and "</qwen" not in value and "_tool>" not in value:
            return value
        value = re.sub(r"<\s*/?\s*qwen_local(?:_tool)?[^\n{]*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"</?qwen_local\b", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*_tool>\s*", "", value, flags=re.IGNORECASE)
        return value

    try:
        async for event in create_chat(**chat_arguments(body)):
            kind, data = event.get("type"), event.get("data")
            if kind == "content" and isinstance(data, str):
                data = TOOL_ERROR_RE.sub("", data)
                data = clean_local_markers(data)
                stream_tail += data
                recovered_calls = embedded_tool_calls(stream_tail, real_names=real_names)
                if recovered_calls:
                    kind, data = "tool_calls", recovered_calls
                    stream_tail = ""
                elif tail_could_be_json(stream_tail) and len(stream_tail) <= MAX_JSON_TAIL:
                    # JSON potencial aún incompleto: retén hasta parsearlo
                    continue
                else:
                    data, stream_tail = stream_tail, ""

            if kind in ("reasoning", "content"):
                has_received_data = True
                if kind == "content" and isinstance(data, str):
                    data = TOOL_ERROR_RE.sub("", data)
                block_kind = "thinking" if kind == "reasoning" else "text"
                if block_kind not in open_blocks:
                    open_blocks[block_kind] = index
                    initial = {"type": "thinking", "thinking": "", "signature": "qwen-reverse"} if block_kind == "thinking" else {"type": "text", "text": ""}
                    yield sse("content_block_start", {"type": "content_block_start", "index": index, "content_block": initial})
                    index += 1
                delta = {"type": "thinking_delta", "thinking": data} if block_kind == "thinking" else {"type": "text_delta", "text": data}
                yield sse("content_block_delta", {"type": "content_block_delta", "index": open_blocks[block_kind], "delta": delta})
            elif kind == "tool_calls":
                has_received_data = True
                stop_reason = "tool_use"
                for call in data or []:
                    fn = call.get("function") or {}
                    name = alias_map.get(fn.get("name") or call.get("name") or "", fn.get("name") or call.get("name") or "")
                    raw_args = fn.get("arguments", call.get("input", {}))
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError:
                        parsed_args = {}
                    tool_index = index
                    index += 1
                    yield sse("content_block_start", {"type": "content_block_start", "index": tool_index, "content_block": {
                        "type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}", "name": name, "input": {},
                    }})
                    yield sse("content_block_delta", {"type": "content_block_delta", "index": tool_index, "delta": {
                        "type": "input_json_delta", "partial_json": json.dumps(parsed_args, ensure_ascii=False),
                    }})
                    yield sse("content_block_stop", {"type": "content_block_stop", "index": tool_index})
            elif kind == "usage" and isinstance(data, dict):
                usage = {"input_tokens": data.get("input_tokens", 0), "output_tokens": data.get("output_tokens", 0)}
            elif kind == "done":
                break
    except Exception as exc:
        import sys
        import traceback
        print(f"[qwen-bridge live_stream exception] {exc}", file=sys.stderr, flush=True)
        print("[qwen-bridge live_stream traceback]\n" + traceback.format_exc(), file=sys.stderr, flush=True)

    # Flush final: un tail retenido al cerrar el stream no debe perderse.
    # Si es una llamada (posiblemente truncada, reparable con _close_json_tail)
    # se ejecuta; si es texto real se emite como text_delta.
    if stream_tail.strip():
        recovered_calls = embedded_tool_calls(stream_tail, real_names=real_names)
        if recovered_calls:
            has_received_data = True
            stop_reason = "tool_use"
            for call in recovered_calls:
                fn = call.get("function") or {}
                name = alias_map.get(fn.get("name") or call.get("name") or "", fn.get("name") or call.get("name") or "")
                raw_args = fn.get("arguments", call.get("input", {}))
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    parsed_args = {}
                tool_index = index
                index += 1
                yield sse("content_block_start", {"type": "content_block_start", "index": tool_index, "content_block": {
                    "type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}", "name": name, "input": {},
                }})
                yield sse("content_block_delta", {"type": "content_block_delta", "index": tool_index, "delta": {
                    "type": "input_json_delta", "partial_json": json.dumps(parsed_args, ensure_ascii=False),
                }})
                yield sse("content_block_stop", {"type": "content_block_stop", "index": tool_index})
            stream_tail = ""
        elif len(stream_tail) > 0:
            has_received_data = True
            if "text" not in open_blocks:
                open_blocks["text"] = index
                yield sse("content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}})
                index += 1
            yield sse("content_block_delta", {"type": "content_block_delta", "index": open_blocks["text"], "delta": {"type": "text_delta", "text": stream_tail}})
            stream_tail = ""

    # If direct stream produced no data, try robust collect_qwen_events with retries
    if not has_received_data:
        try:
            qwen_events = await collect_qwen_events(body)
            for event in qwen_events:
                kind, data = event.get("type"), event.get("data")
                recovered_calls = embedded_tool_calls(data, real_names=real_names) if kind == "content" else None
                if recovered_calls:
                    kind, data = "tool_calls", recovered_calls

                if kind in ("reasoning", "content"):
                    block_kind = "thinking" if kind == "reasoning" else "text"
                    if block_kind not in open_blocks:
                        open_blocks[block_kind] = index
                        initial = {"type": "thinking", "thinking": "", "signature": "qwen-reverse"} if block_kind == "thinking" else {"type": "text", "text": ""}
                        yield sse("content_block_start", {"type": "content_block_start", "index": index, "content_block": initial})
                        index += 1
                    delta = {"type": "thinking_delta", "thinking": data} if block_kind == "thinking" else {"type": "text_delta", "text": data}
                    yield sse("content_block_delta", {"type": "content_block_delta", "index": open_blocks[block_kind], "delta": delta})
                elif kind == "tool_calls":
                    stop_reason = "tool_use"
                    for call in data or []:
                        fn = call.get("function") or {}
                        name = alias_map.get(fn.get("name") or call.get("name") or "", fn.get("name") or call.get("name") or "")
                        raw_args = fn.get("arguments", call.get("input", {}))
                        try:
                            parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                        except json.JSONDecodeError:
                            parsed_args = {}
                        tool_index = index
                        index += 1
                        yield sse("content_block_start", {"type": "content_block_start", "index": tool_index, "content_block": {
                            "type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}", "name": name, "input": {},
                        }})
                        yield sse("content_block_delta", {"type": "content_block_delta", "index": tool_index, "delta": {
                            "type": "input_json_delta", "partial_json": json.dumps(parsed_args, ensure_ascii=False),
                        }})
                        yield sse("content_block_stop", {"type": "content_block_stop", "index": tool_index})
                elif kind == "usage" and isinstance(data, dict):
                    usage = {"input_tokens": data.get("input_tokens", 0), "output_tokens": data.get("output_tokens", 0)}
                elif kind == "done":
                    break
        except Exception as exc:
            import sys
            import traceback
            print(f"[qwen-bridge fallback exception] {exc}", file=sys.stderr, flush=True)
            if os.getenv("QWEN_BRIDGE_DEBUG"):
                print("[qwen-bridge fallback traceback]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
            hint = (
                ". Probablemente el request superó el límite de contexto del backend "
                "(los archivos leídos se reenvían enteros en cada turno) o el rate limit "
                "se enfrió. Reintentá el mismo mensaje; si vuelve a fallar, usá /clear y "
                "dividí la tarea en partes más chicas."
            )
            yield sse("error", {"type": "error", "error": {"type": "api_error", "message": f"Qwen Engine Error: {exc}{hint if 'vacía' in str(exc) else ''}"}})
            return

    for block_index in open_blocks.values():
        yield sse("content_block_stop", {"type": "content_block_stop", "index": block_index})
    yield sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": usage})
    yield sse("message_stop", {"type": "message_stop"})


async def zen_anthropic_response(body: dict[str, Any]) -> dict[str, Any]:
    """Una llamada no-stream a OpenCode Zen, traducida a respuesta Anthropic."""
    import aiohttp
    key = zen_api_key()
    if not key:
        return {"type": "error", "error": {
            "type": "authentication_error",
            "message": "Falta la API key de OpenCode Zen. Configurá ZEN_API_KEY (o tené la key "
                       "de opencode en ~/.local/share/opencode/auth.json).",
        }}
    _, zen_model = provider_for(body)
    payload = zen_chat_arguments(body)
    payload["stream"] = False
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{ZEN_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            if resp.status not in (200, 201):
                error_text = (await resp.text())[:500]
                if resp.status == 401:
                    raise QwenAuthError(f"OpenCode Zen auth: {error_text or 'sin detalle'}")
                if resp.status == 429:
                    raise QwenRateLimitError(f"OpenCode Zen rate limit: {error_text or 'sin detalle'}")
                raise QwenError(f"OpenCode Zen {resp.status}: {error_text or 'sin detalle'}")
            data = await resp.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    blocks: list[dict[str, Any]] = []
    reasoning = message.get("reasoning_content")
    if reasoning:
        blocks.append({"type": "thinking", "thinking": str(reasoning), "signature": "opencode-zen"})
    text = message.get("content")
    if text:
        blocks.append({"type": "text", "text": text})
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append({"type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}", "name": fn.get("name", ""), "input": args})
    usage_data = data.get("usage") or {}
    usage = {
        "input_tokens": usage_data.get("prompt_tokens", 0),
        "output_tokens": usage_data.get("completion_tokens", 0),
    }
    return {
        "id": f"msg_{uuid.uuid4().hex}", "type": "message", "role": "assistant",
        "model": str(body.get("model") or zen_model), "content": blocks,
        "stop_reason": "tool_use" if (message.get("tool_calls")) else "end_turn",
        "stop_sequence": None, "usage": usage,
    }


def error_response(error: Exception) -> JSONResponse:
    status = 401 if isinstance(error, QwenAuthError) else 429 if isinstance(error, QwenRateLimitError) else 502
    kind = "authentication_error" if status == 401 else "rate_limit_error" if status == 429 else "api_error"
    return JSONResponse(status_code=status, content={"type": "error", "error": {"type": kind, "message": str(error)}})


@app.post("/v1/messages")
async def messages(request: Request):
    body = await request.json()
    if os.getenv("QWEN_BRIDGE_DEBUG"):
        print(f"[qwen-bridge] model={body.get('model')} messages={len(body.get('messages') or [])}", flush=True)
        for i, msg in enumerate(body.get("messages") or []):
            content = msg.get("content")
            if isinstance(content, list):
                summary = [b.get("type") if isinstance(b, dict) else type(b).__name__ for b in content]
            else:
                summary = f"{type(content).__name__} len={len(content or '')}"
            extra = {k: v for k, v in msg.items() if k not in ("content", "role")}
            print(f"[qwen-bridge msg {i}] role={msg.get('role')} blocks={summary} extra={extra}", flush=True)
        tools = body.get("tools") or []
        print(f"[qwen-bridge tools] count={len(tools)} first_types={[type(t).__name__ for t in tools[:3]]}", flush=True)

    provider, _ = provider_for(body)
    if provider == "zen":
        if body.get("stream"):
            return StreamingResponse(live_zen_anthropic_stream(body), media_type="text/event-stream")
        try:
            return await zen_anthropic_response(body)
        except Exception as error:
            return error_response(error)

    if body.get("stream"):
        return StreamingResponse(live_anthropic_stream(body), media_type="text/event-stream")

    try:
        qwen_events = await collect_qwen_events(body)
        blocks: list[dict[str, Any]] = []
        reasoning = ""
        text = ""
        tools = []
        usage = {"input_tokens": 0, "output_tokens": 0}
        for event in qwen_events:
            kind, data = event.get("type"), event.get("data")
            recovered_calls = embedded_tool_calls(data, real_names=tool_real_names(translate_tools(body))) if kind == "content" else None
            if recovered_calls:
                kind, data = "tool_calls", recovered_calls
            if kind == "reasoning": reasoning += str(data)
            elif kind == "content": text += str(data)
            elif kind == "tool_calls": tools.extend(data or [])
            elif kind == "usage" and isinstance(data, dict): usage = data
            elif kind == "done": break
        if reasoning: blocks.append({"type": "thinking", "thinking": reasoning, "signature": "qwen-reverse"})
        if text: blocks.append({"type": "text", "text": text})
        for call in tools:
            fn = call.get("function") or {}
            raw = fn.get("arguments", call.get("input", {}))
            try: args = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError: args = {}
            blocks.append({"type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}", "name": fn.get("name") or call.get("name", ""), "input": args or {}})
        return {"id": f"msg_{uuid.uuid4().hex}", "type": "message", "role": "assistant", "model": body.get("model"), "content": blocks, "stop_reason": "tool_use" if tools else "end_turn", "stop_sequence": None, "usage": usage}
    except Exception as error:
        return error_response(error)


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
    chars = len(text_of(body.get("system"))) + sum(len(text_of(m.get("content"))) for m in body.get("messages") or [])
    return {"input_tokens": max(1, chars // 4)}


KNOWN_QWEN_MODELS = [
    "qwen3.8-max", "qwen3.8-max-preview", "qwen3.7-max", "qwen3.7-plus",
    "qwen3.6-plus", "qwen3-coder-plus", "qwen3.5-flash", "qwen3.5-plus", "qwen3-vl-plus",
]

KNOWN_ZEN_MODELS = [
    "claude-fable-5", "claude-opus-5", "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-opus-4-6", "claude-haiku-4-5", "gpt-5.6-sol", "gpt-5.5-pro", "gpt-5.4",
    "gpt-5.3-codex", "gpt-5.2-codex", "gpt-5.1-codex", "deepseek-v4-pro", "deepseek-v4-flash",
    "gemini-3.6-flash", "gemini-3.1-pro", "glm-5.2", "kimi-k3", "minimax-m3", "grok-4.5",
    "qwen3.6-plus", "deepseek-v4-flash-free",
]


async def zen_model_list() -> list[str]:
    import aiohttp
    key = zen_api_key()
    if not key:
        return KNOWN_ZEN_MODELS
    try:
        headers = {"Authorization": f"Bearer {key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ZEN_BASE_URL}/models", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ids = [item.get("id") for item in (data.get("data") or []) if isinstance(item, dict) and item.get("id")]
                    if ids:
                        return ids
    except Exception:
        pass
    return KNOWN_ZEN_MODELS


@app.get("/v1/models")
async def models():
    model_list = []
    try:
        found = await fetch_models(os.getenv("QWEN_TOKEN") or None)
        model_list.extend(found if found else KNOWN_QWEN_MODELS)
    except Exception:
        model_list.extend(KNOWN_QWEN_MODELS)
    zen_models = await zen_model_list()
    seen = set(model_list)
    for item in zen_models:
        if item not in seen:
            model_list.append(item)
            seen.add(item)
    return {
        "object": "list",
        "data": [
            {"id": item, "object": "model", "created": int(time.time()), "owned_by": "qwen-reverse"}
            for item in model_list
        ],
    }


@app.get("/health")
async def health():
    provider = "zen" if zen_api_key() else "qwen-reverse"
    return {
        "status": "ok",
        "backend": "qwen-reverse" if provider == "qwen-reverse" else "opencode-zen",
        "providers": ["qwen-reverse", "opencode-zen"] if provider == "zen" else ["qwen-reverse"],
        "model": os.getenv("QWEN_MODEL", "qwen3.8-max"),
    }

