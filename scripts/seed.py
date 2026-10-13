"""Creates the demo world: Mattermost team + channels, Gitea repos, and one
existing employee (Rahul Verma, developer) so you can demo offboarding.

Run once after both apps are up and your .env is filled in:
    python -m scripts.seed
Safe to run again (it skips things that already exist).
Add --conflict to also create an unrelated 'priya.sharma' username, which makes
the later onboarding of Priya Sharma hit a real "username taken" problem.
"""
import sys

import httpx

from agent import config
from agent.policy import Policy
from tools.apps import Gitea, Mattermost
from tools.registry import build_tools


def ensure_mm_admin():
    base = config.MM_URL.rstrip("/") + "/api/v4"
    r = httpx.post(f"{base}/users/login", json={"login_id": config.MM_ADMIN_EMAIL,
                                                 "password": config.MM_ADMIN_PASSWORD}, timeout=15)
    if r.status_code == 200:
        return
    print("Admin login failed; trying to create the first Mattermost account...")
    r = httpx.post(f"{base}/users", json={"email": config.MM_ADMIN_EMAIL, "username": "dayoneadmin",
                                           "password": config.MM_ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 201:
        sys.exit(f"Could not create the admin ({r.status_code}: {r.text[:200]}).\n"
                 f"Open {config.MM_URL} in your browser, sign up with the email and password from .env, "
                 f"then run this script again.")


def main():
    policy = Policy()
    ensure_mm_admin()
    mm, gitea = Mattermost(), Gitea()

    # Mattermost team
    r = mm.req("GET", f"/teams/name/{config.MM_TEAM}")
    if r.status_code != 200:
        r = mm.req("POST", "/teams", json={"name": config.MM_TEAM, "display_name": config.MM_TEAM.title(), "type": "O"})
        assert r.status_code == 201, f"team create failed: {r.status_code} {r.text}"
        print("created team", config.MM_TEAM)
    team_id = mm.team_id()

    # Mattermost channels (private, so people only see what they are added to)
    for ch in policy.inv_channels:
        if mm.req("GET", f"/teams/{team_id}/channels/name/{ch}").status_code != 200:
            r = mm.req("POST", "/channels", json={"team_id": team_id, "name": ch,
                                                   "display_name": ch.title(), "type": "P"})
            assert r.status_code == 201, f"channel {ch} failed: {r.status_code} {r.text}"
            print("created channel", ch)

    # Gitea repos
    for repo in policy.inv_repos:
        if gitea.req("GET", f"/repos/{gitea.owner}/{repo}").status_code != 200:
            r = gitea.req("POST", "/user/repos", json={"name": repo, "private": True, "auto_init": True})
            assert r.status_code == 201, f"repo {repo} failed: {r.status_code} {r.text}"
            print("created repo", repo)

    # An existing employee, to demo offboarding
    tools = build_tools(mm, gitea)
    e = policy.email_for("Rahul", "Verma")
    tools["mm_create_user"].func(e, "rahul.verma", "Rahul", "Verma")
    tools["gitea_create_user"].func(e, "rahul.verma", "Rahul Verma")
    for ch in policy.roles["developer"]["channels"]:
        tools["mm_add_to_channel"].func(e, ch)
    for repo in policy.roles["developer"]["repos"]:
        tools["gitea_add_collaborator"].func(e, repo)
    print("existing employee ready: Rahul Verma (developer)")

    if "--conflict" in sys.argv:
        other = "priya.sharma.old@example.test"
        tools["mm_create_user"].func(other, "priya.sharma", "Priya", "S-Old")
        tools["gitea_create_user"].func(other, "priya.sharma", "Priya S-Old")
        print("created a different person with username priya.sharma (for the conflict demo)")
    print("Seed done.")


if __name__ == "__main__":
    main()
