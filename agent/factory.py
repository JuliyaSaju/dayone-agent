"""Builds the whole system. The only file that wires real apps together."""
from agent import config
from agent.executor import Executor, Faults, parse_faults
from agent.llm import make_llm
from agent.policy import Policy
from agent.runtime import Runtime
from agent.state import Store


def _ask(question: str) -> str:
    return input(f"\n[agent asks] {question}\n> ")


def _approve(description: str) -> bool:
    return input(f"\n[approval needed] {description} (yes/no)\n> ").strip().lower() in ("y", "yes")


def build_runtime(llm=None, mm=None, gitea=None, ask=None, approve=None,
                  faults=None, db_path="dayone.db", policy=None, backoff=0.3):
    from tools.apps import Gitea, Mattermost  # imported here so tests need no httpx
    from tools.registry import build_tools
    from verify.verifier import Verifier

    mm = mm or Mattermost()
    gitea = gitea or Gitea()
    policy = policy or Policy()
    store = Store(db_path)
    tools = build_tools(mm, gitea)
    spec = faults if faults is not None else parse_faults(config.FAULTS)
    executor = Executor(store, policy, tools, Faults(spec), backoff=backoff)
    verifier = Verifier(mm, gitea, config.DEMO_USER_PASSWORD)
    return Runtime(llm or make_llm(), store, policy, tools, executor, verifier,
                   ask or _ask, approve or _approve)
