"""Runs ONE tool call safely: gate -> (fault injection) -> run -> retry -> log."""
import time

from agent.errors import ToolError, TransientError


class Faults:
    """Break things on purpose to test recovery.

    spec example: {"mm_create_user": "fail_after_once"}
      fail_before_once : error BEFORE the app is called
      fail_after_once  : the app DID the work, but the caller sees a timeout
                         (the nasty case that can create duplicates)
    """

    def __init__(self, spec=None):
        self.spec = dict(spec or {})
        self.fired = set()

    def before(self, tool):
        if self.spec.get(tool) == "fail_before_once" and tool not in self.fired:
            self.fired.add(tool)
            raise TransientError("injected fault: connection reset before the request")

    def after(self, tool):
        if self.spec.get(tool) == "fail_after_once" and tool not in self.fired:
            self.fired.add(tool)
            raise TransientError("injected fault: timeout after the request was sent")


def parse_faults(text: str) -> dict:
    spec = {}
    for part in (text or "").split(","):
        if "=" in part:
            tool, mode = part.split("=", 1)
            spec[tool.strip()] = mode.strip()
    return spec


class Executor:
    def __init__(self, store, policy, tools, faults=None, max_retries=2, backoff=0.3):
        self.store = store
        self.policy = policy
        self.tools = tools
        self.faults = faults or Faults()
        self.max_retries = max_retries
        self.backoff = backoff

    def run(self, task_id, name, args, expected) -> dict:
        action_id = self.store.log_start(task_id, name, args)
        tool = self.tools.get(name)
        if tool is None:
            return self._end(action_id, "error", {"ok": False, "error": "unknown_tool",
                                                  "detail": f"there is no tool named '{name}'"}, 0)
        reason = self.policy.gate(name, args, expected)
        if reason:
            return self._end(action_id, "blocked", {"ok": False, "error": "blocked_by_policy",
                                                    "detail": reason}, 0)
        started = time.time()
        attempts = 0
        while True:
            attempts += 1
            try:
                self.faults.before(name)
                output = tool.func(**args)
                self.faults.after(name)
                result, status = {"ok": True, "result": output, "attempts": attempts}, "ok"
                break
            except TransientError as e:
                if attempts <= self.max_retries:
                    time.sleep(self.backoff * attempts)
                    continue
                result = {"ok": False, "error": "transient_failure",
                          "detail": f"{e} (gave up after {attempts} attempts)"}
                status = "error"
                break
            except ToolError as e:
                result, status = {"ok": False, "error": e.code, "detail": str(e)}, "error"
                break
            except TypeError as e:
                result, status = {"ok": False, "error": "bad_arguments", "detail": str(e)}, "error"
                break
        return self._end(action_id, status, result, int((time.time() - started) * 1000))

    def _end(self, action_id, status, result, ms):
        self.store.log_end(action_id, status, result, ms)
        return result
