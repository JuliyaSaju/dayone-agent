"""The agent's tools. Each tool = a name, a description the AI reads, an input
schema, and a Python function. The AI can ONLY do what is listed here."""
from dataclasses import dataclass
from typing import Callable

from agent import config
from agent.errors import ToolError

STR = {"type": "string"}


def _obj(props: dict, required: list) -> dict:
    return {"type": "object", "properties": props, "required": required}


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    func: Callable
    writes: bool


def build_tools(mm, gitea, password=None) -> dict:
    pw = password or config.DEMO_USER_PASSWORD

    # ---------- Mattermost ----------
    def mm_find_user(email):
        u = mm.user_by_email(email)
        if not u:
            return {"found": False}
        return {"found": True, "username": u["username"], "active": u.get("delete_at", 0) == 0}

    def mm_create_user(email, username, first_name, last_name):
        existing = mm.user_by_email(email)
        if existing:  # makes retries safe: never a second account
            return {"status": "exists", "username": existing["username"]}
        if mm.user_by_username(username):
            raise ToolError("username_taken",
                            f"Mattermost username '{username}' belongs to someone else. Choose a different username.")
        u = mm.create_user(email, username, first_name, last_name, pw)
        return {"status": "created", "username": u["username"]}

    def mm_add_to_channel(email, channel):
        u = mm.user_by_email(email)
        if not u:
            raise ToolError("user_missing", f"no Mattermost account for {email}; create it first")
        if not mm.is_team_member(u["id"]):
            mm.add_to_team(u["id"])
        if mm.is_channel_member(channel, u["id"]):
            return {"status": "already_member"}
        mm.add_to_channel(channel, u["id"])
        return {"status": "added"}

    def mm_deactivate_user(email):
        u = mm.user_by_email(email)
        if not u:
            raise ToolError("user_missing", f"no Mattermost account for {email}")
        if u.get("delete_at", 0) > 0:
            return {"status": "already_deactivated"}
        mm.set_active(u["id"], False)
        return {"status": "deactivated"}

    # ---------- Gitea ----------
    def gitea_find_user(email):
        u = gitea.user_by_email(email)
        if not u:
            return {"found": False}
        return {"found": True, "username": u["login"],
                "active": u.get("active", True) and not u.get("prohibit_login", False)}

    def gitea_create_user(email, username, full_name):
        existing = gitea.user_by_email(email)
        if existing:
            return {"status": "exists", "username": existing["login"]}
        if gitea.user_by_username(username):
            raise ToolError("username_taken",
                            f"Gitea username '{username}' belongs to someone else. Choose a different username.")
        u = gitea.create_user(email, username, full_name, pw)
        return {"status": "created", "username": u["login"]}

    def gitea_add_collaborator(email, repo):
        u = gitea.user_by_email(email)
        if not u:
            raise ToolError("user_missing", f"no Gitea account for {email}; create it first")
        if gitea.is_collaborator(repo, u["login"]):
            return {"status": "already_collaborator"}
        gitea.add_collaborator(repo, u["login"])
        return {"status": "added"}

    def gitea_remove_collaborator(email, repo):
        u = gitea.user_by_email(email)
        if not u:
            raise ToolError("user_missing", f"no Gitea account for {email}")
        if not gitea.is_collaborator(repo, u["login"]):
            return {"status": "not_collaborator"}
        gitea.remove_collaborator(repo, u["login"])
        return {"status": "removed"}

    def gitea_disable_user(email):
        u = gitea.user_by_email(email)
        if not u:
            raise ToolError("user_missing", f"no Gitea account for {email}")
        if u.get("prohibit_login"):
            return {"status": "already_disabled"}
        gitea.disable_user(u["login"])
        return {"status": "disabled"}

    tools = [
        Tool("mm_find_user", "Look up a Mattermost account by email.",
             _obj({"email": STR}, ["email"]), mm_find_user, False),
        Tool("gitea_find_user", "Look up a Gitea account by email.",
             _obj({"email": STR}, ["email"]), gitea_find_user, False),
        Tool("mm_create_user",
             "Create a Mattermost account. If the username is taken by someone else you get error 'username_taken': pick another username and retry.",
             _obj({"email": STR, "username": STR, "first_name": STR, "last_name": STR},
                  ["email", "username", "first_name", "last_name"]), mm_create_user, True),
        Tool("gitea_create_user",
             "Create a Gitea account. If the username is taken you get 'username_taken': pick another and retry.",
             _obj({"email": STR, "username": STR, "full_name": STR},
                  ["email", "username", "full_name"]), gitea_create_user, True),
        Tool("mm_add_to_channel", "Add the person (by email) to a Mattermost channel. Also joins the team.",
             _obj({"email": STR, "channel": STR}, ["email", "channel"]), mm_add_to_channel, True),
        Tool("gitea_add_collaborator", "Give the person (by email) write access to a Gitea repo.",
             _obj({"email": STR, "repo": STR}, ["email", "repo"]), gitea_add_collaborator, True),
        Tool("mm_deactivate_user", "Deactivate a Mattermost account (offboarding).",
             _obj({"email": STR}, ["email"]), mm_deactivate_user, True),
        Tool("gitea_disable_user", "Block login for a Gitea account (offboarding).",
             _obj({"email": STR}, ["email"]), gitea_disable_user, True),
        Tool("gitea_remove_collaborator", "Remove the person's access to a Gitea repo (offboarding).",
             _obj({"email": STR, "repo": STR}, ["email", "repo"]), gitea_remove_collaborator, True),
    ]
    return {t.name: t for t in tools}
