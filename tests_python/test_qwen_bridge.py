import asyncio
import unittest
from unittest import mock
from qwen_bridge import TOOL_ERROR_RE, _close_json_tail, chat_arguments, collect_qwen_events, embedded_tool_calls, live_anthropic_stream, text_of, translate_messages, translate_tools

class BridgeStreamTests(unittest.TestCase):
    def test_live_stream_converts_fragmented_malformed_marker(self):
        # El marcador llega partido en N chunks y con prefijo malformado
        # (<qwen_local sin "_tool"). Debe terminar como tool_use real con el
        # nombre traducido, y el texto previo debe fluir como text_delta.
        chunks = [
            "Voy a preguntarte. ",
            "<qwen_local",
            '{"name":"local_tool_0"',
            ',"arguments":{"questions":[]}}',
            "_tool>",
        ]

        async def fake_create_chat(**kwargs):
            for c in chunks:
                yield {"type": "content", "data": c}
            yield {"type": "done", "data": None}

        original = None
        try:
            import qwen_bridge
            original = qwen_bridge.create_chat
            qwen_bridge.create_chat = fake_create_chat

            body = {
                "model": "qwen3.8-max",
                "messages": [{"role": "user", "content": "ideas"}],
                "tools": [{"name": "AskUserQuestion", "description": "d", "input_schema": {"type": "object"}}],
            }
            events = []

            async def collect():
                async for ev in live_anthropic_stream(body):
                    events.append(ev)

            asyncio.run(collect())
        finally:
            if original is not None:
                qwen_bridge.create_chat = original

        joined = "".join(events)
        self.assertIn("Voy a preguntarte.", joined)
        self.assertIn('"type": "tool_use"', joined)
        self.assertIn('"name": "AskUserQuestion"', joined)
        self.assertNotIn("qwen_local", joined)
        self.assertNotIn("local_tool_0", joined)


class BridgeTranslationTests(unittest.TestCase):
    def test_structured_system_and_text(self):
        body = {"system": [{"type": "text", "text": "sistema"}], "messages": [{"role": "user", "content": [{"type": "text", "text": "hola"}]}]}
        self.assertEqual(translate_messages(body), [{"role": "system", "content": "sistema"}, {"role": "user", "content": "hola"}])

    def test_tool_use_and_result(self):
        body = {"messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "a"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]},
        ]}
        messages = translate_messages(body)
        self.assertEqual(messages[0]["tool_calls"][0]["function"]["name"], "Read")
        self.assertIn("Resultado de herramienta t1", messages[1]["content"])

    def test_anthropic_tool_schema(self):
        tools = translate_tools({"tools": [{"name": "Read", "description": "lee", "input_schema": {"type": "object"}}]})
        self.assertEqual(tools[0]["function"]["name"], "Read")

    def test_recovers_json_tool_call_with_suffix(self):
        calls = embedded_tool_calls('Voy a hacerlo. {"tool_calls":[{"name":"Bash","arguments":{"command":"pwd"}}]} texto extra')
        self.assertEqual(calls[0]["function"]["name"], "Bash")

    def test_recovers_marked_tool_calls(self):
        calls = embedded_tool_calls('[Tool call: Edit]\n{"file_path":"a","old_string":"x","new_string":"y"}\n[Tool call: Bash]\n{"command":"true"}')
        self.assertEqual([call["function"]["name"] for call in calls], ["Edit", "Bash"])

    def test_recovers_local_tool_envelope(self):
        calls = embedded_tool_calls('<qwen_local_tool>{"name":"Edit","arguments":{"file_path":"a"}}</qwen_local_tool>')
        self.assertEqual(calls[0]["function"]["name"], "Edit")

    def test_recovers_bare_local_tool_json_behind_error_text(self):
        # Qwen no soporta function-calling nativo; emite el objeto llamada
        # suelto tras un marcador de error. El puente debe recuperarlo.
        raw = 'Tool local_tool_0 does not exists.Tool local_tool_0 does not exists.{"name":"local_tool_0","arguments":{"questions":[]}}'
        calls = embedded_tool_calls(raw)
        self.assertIsNotNone(calls)
        self.assertEqual(calls[0]["function"]["name"], "local_tool_0")
        self.assertIn('"questions"', calls[0]["function"]["arguments"])

    def test_recovers_flat_object_with_real_name(self):
        # Enfoque de protocolo plano (como qwen-reverse-agent): el modelo escribe
        # {"name":"AskUserQuestion","arguments":{...}} sin envoltura. Se captura
        # solo si el nombre pertenece a las tools conocidas.
        calls = embedded_tool_calls('{"name":"AskUserQuestion","arguments":{"questions":[]}}', real_names={"AskUserQuestion"})
        self.assertIsNotNone(calls)
        self.assertEqual(calls[0]["function"]["name"], "AskUserQuestion")

    def test_plain_object_with_unknown_name_is_ignored(self):
        calls = embedded_tool_calls('{"name":"HacerCosas","arguments":{"x":1}}', real_names={"Read"})
        self.assertIsNone(calls)

    def test_strips_generic_tool_error_text(self):
        stripped = TOOL_ERROR_RE.sub("", "Tool AskUserQuestion does not exists.¿Qué nivel de C tienes?")
        self.assertEqual(stripped, "¿Qué nivel de C tienes?")

    def test_recovers_truncated_json_tail(self):
        # Qwen corta el tool call por streaming sin cerrar la última llave.
        raw = '{"name":"AskUserQuestion","arguments":{"questions":[{"question":"n","options":["a"]}]'
        self.assertEqual(_close_json_tail(raw)[-1:], "}")
        calls = embedded_tool_calls(raw, real_names={"AskUserQuestion"})
        self.assertIsNotNone(calls)
        self.assertEqual(calls[0]["function"]["name"], "AskUserQuestion")

    def test_does_not_confuse_unrelated_objects(self):
        calls = embedded_tool_calls('{"name":"Juan","arguments":{"edad":30}}')
        self.assertIsNone(calls)

    def test_recovers_json_inside_malformed_marker(self):
        # Qwen a veces emite <qwen_local{"name":...}}_tool> (prefijo sin
        # "_tool" y cierre dividido). El JSON interior debe recuperarse.
        raw = '<qwen_local{"name":"local_tool_0","arguments":{"questions":[{"question":"Nivel?"}]}}_tool>'
        calls = embedded_tool_calls(raw)
        self.assertIsNotNone(calls)
        self.assertEqual(calls[0]["function"]["name"], "local_tool_0")
        self.assertIn("Nivel", calls[0]["function"]["arguments"])

    def test_recovers_all_calls_in_consecutive_objects(self):
        # Qwen a veces encadena dos llamadas en el mismo turno:
        # {...}{\"name\":\"Bashtool\"...} sin parar tras la primera.
        raw = 'Voy a revisar. {"name":"Read","arguments":{"file_path":"package.json"}}{"name":"Bash","arguments":{"command":"ls -la scripts/"}}'
        calls = embedded_tool_calls(raw, real_names={"Read", "Bash"})
        self.assertIsNotNone(calls)
        self.assertEqual([call["function"]["name"] for call in calls], ["Read", "Bash"])
        args0 = calls[0]["function"]["arguments"]
        args1 = calls[1]["function"]["arguments"]
        self.assertIn('"file_path"', args0)
        self.assertIn('"command"', args1)

    def test_recovers_fragmented_corrupt_prefix(self):
        # El `{` inicial se pierde por streaming: queda `":"Read",...` y
        # `name":"Bash",...` pegados al texto. Deben recuperarse ambas.
        raw = 'Voy a revisar: ":"Read","arguments":{"file_path":"C:\\\\package.json"}}name":"Bash","arguments":{"command":"ls -la scripts/"}}'
        calls = embedded_tool_calls(raw, real_names={"Read", "Bash"})
        self.assertIsNotNone(calls)
        self.assertEqual([call["function"]["name"] for call in calls], ["Read", "Bash"])

    def test_fragment_with_unknown_name_is_ignored(self):
        raw = 'el texto ":"HacerCosas","arguments":{"x":1}}" y el resto'
        calls = embedded_tool_calls(raw, real_names={"Read"})
        self.assertIsNone(calls)

    def test_live_stream_emits_all_tool_calls_from_one_turn(self):
        chunks = [
            'Voy a revisar. {"name":"Read","arguments":{"file_path":"package.json"}}',
            '{"name":"Bash","arguments":{"command":"ls -la"}}',
        ]

        async def fake_create_chat(**kwargs):
            for c in chunks:
                yield {"type": "content", "data": c}
            yield {"type": "done", "data": None}

        import qwen_bridge
        original = qwen_bridge.create_chat
        qwen_bridge.create_chat = fake_create_chat
        try:
            body = {
                "model": "qwen3.8-max",
                "messages": [{"role": "user", "content": "explora"}],
                "tools": [
                    {"name": "Read", "description": "lee", "input_schema": {"type": "object"}},
                    {"name": "Bash", "description": "bash", "input_schema": {"type": "object"}},
                ],
            }
            events = []

            async def collect():
                async for ev in live_anthropic_stream(body):
                    events.append(ev)

            asyncio.run(collect())
        finally:
            qwen_bridge.create_chat = original

        joined = "".join(events)
        self.assertEqual(joined.count('"name": "Read"'), 1)
        self.assertEqual(joined.count('"name": "Bash"'), 1)
        self.assertIn('"stop_reason": "tool_use"', joined)
        self.assertNotIn('"text_delta"', joined)

    def test_live_stream_flushes_tail_junk_as_text_not_json(self):
        # Un tail residual sin tool call (p.ej. texto entrecomillado retenido)
        # debe fluir como text_delta al cerrarse el stream, no perderse ni
        # quedarse retenido para siempre.
        chunks = ['El resultado es "exactamente" esto, nada más.']

        async def fake_create_chat(**kwargs):
            for c in chunks:
                yield {"type": "content", "data": c}
            yield {"type": "done", "data": None}

        import qwen_bridge
        original = qwen_bridge.create_chat
        qwen_bridge.create_chat = fake_create_chat
        try:
            body = {
                "model": "qwen3.8-max",
                "messages": [{"role": "user", "content": "texto"}],
                "tools": [],
            }
            events = []

            async def collect():
                async for ev in live_anthropic_stream(body):
                    events.append(ev)

            asyncio.run(collect())
        finally:
            qwen_bridge.create_chat = original

        joined = "".join(events)
        self.assertIn("El resultado es", joined)
        self.assertIn("exactamente", joined)

class EmptyResponseRetryTests(unittest.TestCase):
    def _body(self):
        return {
            "model": "qwen3.8-max",
            "messages": [{"role": "user", "content": "hola"}],
            "tools": [],
            "thinking": {"type": "enabled", "budget_tokens": 20000},
        }

    def test_empty_response_retries_with_none_effort_and_raises_informative(self):
        # El backend devuelve done sin contenido; los intentos impares deben
        # usar reasoning_effort=none para escapar del modo trabado.
        import qwen_bridge

        observed = []
        attempts = 3

        def fake_create_chat(**kwargs):
            observed.append(kwargs.get("reasoning_effort"))
            async def gen():
                for _ in range(attempts):
                    yield {"type": "done", "data": None}
            return gen()

        original = qwen_bridge.create_chat
        qwen_bridge.create_chat = fake_create_chat
        try:
            with self.assertRaises(qwen_bridge.QwenError) as ctx:
                asyncio.run(collect_qwen_events(self._body(), attempts=attempts, retry_delays=[0.01, 0.01, 0.01]))
        finally:
            qwen_bridge.create_chat = original

        self.assertEqual(len(observed), attempts)
        self.assertEqual(observed, ["low", "none", "low"])  # base effort low; intentos impares con none
        self.assertIn("vacía", str(ctx.exception))
        self.assertIn("tokens", str(ctx.exception))

    def test_success_recovers_content_after_empty_first_attempt(self):
        import qwen_bridge

        calls = 0

        def fake_create_chat(**kwargs):
            nonlocal calls
            calls += 1
            async def stream():
                if calls == 1:
                    yield {"type": "done", "data": None}
                else:
                    yield {"type": "content", "data": "texto recuperado"}
                    yield {"type": "done", "data": None}
            return stream()

        original = qwen_bridge.create_chat
        qwen_bridge.create_chat = fake_create_chat
        try:
            events = asyncio.run(collect_qwen_events(self._body(), attempts=3, retry_delays=[0.01, 0.01, 0.01]))
        finally:
            qwen_bridge.create_chat = original

        self.assertEqual(calls, 2)
        self.assertIn("texto recuperado", "".join(e.get("data") or "" for e in events if e.get("type") == "content"))

    def test_chat_arguments_effort_override(self):
        body = self._body()
        # Override explícito gana sobre el derivado del body
        self.assertEqual(chat_arguments(body, reasoning_effort="medium")["reasoning_effort"], "medium")
        self.assertEqual(chat_arguments(body)["reasoning_effort"], "low")


class ZenProviderTests(unittest.TestCase):
    def test_provider_routing_zen_prefix(self):
        import qwen_bridge as qb
        provider, model = qb.provider_for({"model": "opencode/deepseek-v4-flash-free", "messages": []})
        self.assertEqual(provider, "zen")
        self.assertEqual(model, "deepseek-v4-flash-free")

    def test_provider_routing_qwen_keeps_web(self):
        import qwen_bridge as qb
        provider, model = qb.provider_for({"model": "qwen3.8-max", "messages": []})
        self.assertEqual(provider, "qwen")
        self.assertEqual(model, "qwen3.8-max")

    def test_provider_routing_env_zen_model(self):
        import qwen_bridge as qb
        with mock.patch.dict("os.environ", {"QWEN_MODEL": "opencode/deepseek-v4-flash-free"}, clear=False):
            provider, model = qb.provider_for({"model": "opus", "messages": []})
        self.assertEqual(provider, "zen")
        self.assertEqual(model, "deepseek-v4-flash-free")

    def test_zen_messages_preserves_tool_ids(self):
        import qwen_bridge as qb
        body = {"messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_t1", "name": "Read", "input": {"file_path": "a"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_t1", "content": "contenido"}]},
            {"role": "user", "content": "sigue"},
        ]}
        msgs = qb.zen_messages(body)
        self.assertEqual(msgs[0]["tool_calls"][0]["id"], "toolu_t1")
        self.assertEqual(msgs[1]["role"], "tool")
        self.assertEqual(msgs[1]["tool_call_id"], "toolu_t1")
        self.assertEqual(msgs[1]["content"], "contenido")
        self.assertEqual(msgs[2]["role"], "user")
        self.assertEqual(msgs[2]["content"], "sigue")

    def test_provider_chat_arguments_includes_tools_and_model(self):
        import qwen_bridge as qb
        body = {
            "model": "opencode/deepseek-chat",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": [{"name": "Bash", "description": "d", "input_schema": {"type": "object"}}],
            "max_tokens": 200,
        }
        payload = qb.provider_chat_arguments(qb.get_provider("zen"), body)
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(payload["stream"], True)
        self.assertEqual(len(payload["tools"]), 1)
        self.assertEqual(payload["tools"][0]["function"]["name"], "Bash")
        self.assertEqual(payload["max_tokens"], 200)

    def test_stream_provider_payload_is_openai_compatible(self):
        import qwen_bridge as qb
        body = {"model": "opencode/gpt-5.5-pro", "messages": [{"role": "user", "content": "hi"}]}
        payload = qb.provider_chat_arguments(qb.get_provider("zen"), body)
        self.assertNotIn("tools", payload)  # sin tools en el body -> no forge tools vacíos
        self.assertEqual(payload["messages"][0]["role"], "user")

    def test_provider_registry_routes_by_prefix(self):
        import qwen_bridge as qb
        self.assertEqual(qb.provider_for({"model": "openrouter/anthropic/claude-sonnet-4.5"})[0], "openrouter")
        self.assertEqual(qb.provider_for({"model": "groq/llama-3.3-70b-versatile"})[0], "groq")
        self.assertEqual(qb.provider_for({"model": "deepseek/deepseek-chat"})[0], "deepseek")
        self.assertEqual(qb.provider_for({"model": "local/llama3"})[0], "local")
        self.assertEqual(qb.provider_for({"model": "qwen3.8-max"})[0], "qwen")

    def test_provider_registry_strips_prefix(self):
        import qwen_bridge as qb
        self.assertEqual(qb.provider_for({"model": "openrouter/anthropic/claude-sonnet-4.5"})[1], "anthropic/claude-sonnet-4.5")
        self.assertEqual(qb.provider_for({"model": "groq/llama-3.3-70b-versatile"})[1], "llama-3.3-70b-versatile")


if __name__ == '__main__': unittest.main()
