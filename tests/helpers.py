"""Builds a full agent wired to fake apps + the mock AI (no Docker, no API key)."""
from agent.executor import Executor, Faults
from agent.llm import MockLLM
from agent.policy import Policy
from agent.runtime import Runtime
from agent.state import Store
from tests.fakes import FakeGitea, FakeMM
from tools.registry import build_tools
from verify.verifier import Verifier

PASSWORD = "Test-Pass-1!"


def make(faults=None, ask_answer="", approve_answer=True, drop_channel_adds=False):
    policy = Policy()
    mm = FakeMM(policy.inv_channels, drop_channel_adds=drop_channel_adds)
    gitea = FakeGitea(policy.inv_repos)
    store = Store(":memory:")
    tools = build_tools(mm, gitea, password=PASSWORD)
    executor = Executor(store, policy, tools, Faults(faults), backoff=0)
    verifier = Verifier(mm, gitea, PASSWORD)
    log = {"asked": [], "approvals": []}

    def ask(q):
        log["asked"].append(q)
        return ask_answer

    def approve(d):
        log["approvals"].append(d)
        return approve_answer

    rt = Runtime(MockLLM(), store, policy, tools, executor, verifier, ask, approve)
    return rt, mm, gitea, log, tools, executor, store, policy
