"""Tests each connection ONE BY ONE and tells you exactly which call fails.
    python -m scripts.check_setup
"""
from agent import config
from agent.policy import Policy
from tools.apps import Gitea, Mattermost


def step(name, fn):
    try:
        result = fn()
        print(f"[ OK ] {name}" + (f" -> {result}" if result not in (None, True) else ""))
        return True
    except Exception as e:
        print(f"[FAIL] {name}\n        {type(e).__name__}: {e}")
        return False


def main():
    policy = Policy()
    mm, gitea = Mattermost(), Gitea()
    print(f"Mattermost: {config.MM_URL}   Gitea: {config.GITEA_URL}\n")
    step("Mattermost: admin login", lambda: mm._headers() and True)
    step("Mattermost: team exists", lambda: mm.team_id())
    for ch in policy.inv_channels:
        step(f"Mattermost: channel '{ch}' exists", lambda ch=ch: mm._channel_id(ch) and True)
    step("Gitea: token works (list users)", lambda: f"{len(gitea.all_users())} user(s)")
    for repo in policy.inv_repos:
        step(f"Gitea: repo '{repo}' exists",
             lambda repo=repo: gitea.req("GET", f"/repos/{gitea.owner}/{repo}").status_code == 200 or (_ for _ in ()).throw(RuntimeError("not found")))


if __name__ == "__main__":
    main()
