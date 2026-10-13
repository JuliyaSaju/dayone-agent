"""The AI "brain" behind one simple interface: chat(system, messages, tools).

Messages use ONE neutral format (so the loop never cares about the provider):
  {"role": "user", "content": "text"}
  {"role": "assistant", "content": "text or None", "tool_calls": [{"id","name","args"}]}
  {"role": "tool", "tool_call_id": "...", "name": "...", "content": "json text"}
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from agent import config


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict
    extra: Optional[dict] = None


@dataclass
class LLMResponse:
    text: Optional[str] = None
    tool_calls: list = field(default_factory=list)


# ======================================================================
# MockLLM: no API key, fixed rules, same answer every time. For tests.
# ======================================================================
STOP_WORDS = {"Please", "Onboard", "Offboard", "Set", "Add", "New", "Remove", "Create",
              "Clarification", "Ignore", "Also", "Give", "Make", "Monday", "Tuesday",
              "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Today", "Tomorrow"}


class MockLLM:
    def chat(self, system, messages, tools):
        names = {t["name"] for t in tools}
        if "submit_intent" in names:
            return self._understand(messages)
        return self._execute(system, messages)

    def _understand(self, messages):
        text = messages[-1]["content"]
        action = "offboard" if re.search(r"\b(left|leaving|resigned|offboard|last day)\b", text, re.I) else "onboard"
        words = [w for w in re.findall(r"[A-Z][a-z]+", text) if w not in STOP_WORDS]
        first = words[0] if words else ""
        last = words[1] if len(words) > 1 else ""
        role = None
        m = re.search(r"\b(designer|developer|engineer|intern)\b", text, re.I)
        if m:
            role = m.group(1).lower()
            role = "developer" if role == "engineer" else role
        extra = []
        if re.search(r"\bfinance\b", text, re.I):
            extra.append("channel:finance")
        if re.search(r"\badmin\b", text, re.I):
            extra.append("admin")
        args = {"action": action, "first_name": first, "last_name": last, "extra_access": extra}
        if role:
            args["role"] = role
        return LLMResponse(tool_calls=[ToolCall("mock-intent", "submit_intent", args)])

    def _execute(self, system, messages):
        intent_line = re.search(r"^INTENT_JSON=(.*)$", system, re.M)
        exp = json.loads(re.search(r"^EXPECTED_JSON=(.*)$", system, re.M).group(1))
        calls, done, taken, last = {}, set(), {}, None
        for m in messages:
            if m["role"] == "assistant":
                for c in m.get("tool_calls", []):
                    calls[c["id"]] = (c["name"], c["args"])
            elif m["role"] == "tool":
                name, args = calls.get(m["tool_call_id"], (m.get("name"), {}))
                res = json.loads(m["content"])
                last = (name, res)
                if res.get("ok"):
                    done.add((name, json.dumps(args, sort_keys=True)))
                elif res.get("error") == "username_taken":
                    taken[name] = taken.get(name, 0) + 1
        nid = f"mock-{len(messages)}"
        if last and not last[1].get("ok") and last[1].get("error") != "username_taken":
            summary = f"Stopped: {last[0]} failed with {last[1].get('error')}: {last[1].get('detail', '')}"
            return LLMResponse(tool_calls=[ToolCall(nid, "finish", {"summary": summary})])

        e = exp["email"]
        if exp["action"] == "onboard":
            def uname(tool):
                n = taken.get(tool, 0)
                return exp["username"] if n == 0 else f"{exp['username']}{n + 1}"
            steps = [
                ("mm_create_user", {"email": e, "username": uname("mm_create_user"),
                                    "first_name": exp["first_name"], "last_name": exp["last_name"]}),
                ("gitea_create_user", {"email": e, "username": uname("gitea_create_user"),
                                       "full_name": f"{exp['first_name']} {exp['last_name']}"}),
            ]
            steps += [("mm_add_to_channel", {"email": e, "channel": c}) for c in exp["channels"]]
            steps += [("gitea_add_collaborator", {"email": e, "repo": r}) for r in exp["repos"]]
        else:
            steps = [("mm_deactivate_user", {"email": e}), ("gitea_disable_user", {"email": e})]
            steps += [("gitea_remove_collaborator", {"email": e, "repo": r}) for r in exp["inventory_repos"]]

        for name, args in steps:
            if (name, json.dumps(args, sort_keys=True)) not in done:
                return LLMResponse(tool_calls=[ToolCall(nid, name, args)])
        return LLMResponse(tool_calls=[ToolCall(nid, "finish", {"summary": "All planned steps ran."})])


# ======================================================================
# Anthropic (Claude)
# ======================================================================
def _to_anthropic(messages):
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for c in m.get("tool_calls", []):
                blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]})
            out.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            prev = out[-1] if out else None
            if prev and prev["role"] == "user" and isinstance(prev["content"], list):
                prev["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out


class AnthropicLLM:
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def chat(self, system, messages, tools):
        resp = self.client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=system,
            tools=[{"name": t["name"], "description": t["description"], "input_schema": t["schema"]}
                   for t in tools],
            messages=_to_anthropic(messages),
        )
        text = " ".join(b.text for b in resp.content if b.type == "text") or None
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        return LLMResponse(text, calls)


# ======================================================================
# OpenAI-compatible (OpenAI, Gemini compat endpoint, Ollama, ...)
# ======================================================================
def _to_openai(system, messages):
    out = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            msg = {"role": "assistant", "content": m.get("content")}
            if m.get("tool_calls"):
                msg["tool_calls"] = []
                for c in m["tool_calls"]:
                    tc_dict = {
                        "id": c["id"], "type": "function",
                        "function": {"name": c["name"], "arguments": json.dumps(c["args"])}
                    }
                    if c.get("extra"):
                        tc_dict["extra_content"] = c["extra"]
                    msg["tool_calls"].append(tc_dict)
            out.append(msg)
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
    return out


class OpenAILLM:
    def __init__(self):
        from openai import OpenAI
        kwargs = {"api_key": config.OPENAI_API_KEY}
        if config.OPENAI_BASE_URL:
            kwargs["base_url"] = config.OPENAI_BASE_URL
        self.client = OpenAI(**kwargs)

    def chat(self, system, messages, tools):
        resp = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=_to_openai(system, messages),
            tools=[{"type": "function",
                    "function": {"name": t["name"], "description": t["description"], "parameters": t["schema"]}}
                   for t in tools],
        )
        msg = resp.choices[0].message
        calls = [ToolCall(c.id, c.function.name, json.loads(c.function.arguments or "{}"),
                          extra=getattr(c, "extra_content", None))
                 for c in (msg.tool_calls or [])]
        return LLMResponse(msg.content, calls)


def make_llm():
    provider = config.LLM_PROVIDER.lower()
    if provider == "anthropic":
        return AnthropicLLM()
    if provider == "openai":
        return OpenAILLM()
    return MockLLM()
