"""Company rules in code: who gets what, what needs approval, what is blocked.

IMPORTANT: this file (not the AI model) decides what is allowed. Even if the
model is tricked by text in a request, the gate below blocks anything outside
the approved access list.
"""
import re
from pathlib import Path
from typing import Optional

import yaml

from agent.models import Expected, Intent

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "roles.yaml"
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'-]*$")
EXTRA_RE = re.compile(r"^(channel|repo):([a-z0-9._-]+)$")

ONBOARD_TOOLS = {
    "mm_find_user", "gitea_find_user",
    "mm_create_user", "gitea_create_user",
    "mm_add_to_channel", "gitea_add_collaborator",
}
OFFBOARD_TOOLS = {
    "mm_find_user", "gitea_find_user",
    "mm_deactivate_user", "gitea_disable_user", "gitea_remove_collaborator",
}


class Policy:
    def __init__(self, path=DEFAULT_PATH):
        self.cfg = yaml.safe_load(Path(path).read_text())
        self.roles = self.cfg["roles"]
        self.inv_channels = list(self.cfg["inventory"]["channels"])
        self.inv_repos = list(self.cfg["inventory"]["repos"])
        self.sensitive = self.cfg.get("sensitive", {})
        self.domain = self.cfg["email_domain"]

    # ---- names ----
    @staticmethod
    def _slug(text: str) -> str:
        return re.sub(r"[^a-z]", "", text.lower())

    def email_for(self, first: str, last: str) -> str:
        return f"{self._slug(first)}.{self._slug(last)}@{self.domain}"

    def username_for(self, first: str, last: str) -> str:
        return f"{self._slug(first)}.{self._slug(last)}"

    # ---- checking the request meaning ----
    def validate_intent(self, intent: Intent) -> list[str]:
        problems = []
        for label, value in (("first name", intent.first_name), ("last name", intent.last_name)):
            if not value or not NAME_RE.match(value):
                problems.append(f"the {label} is missing or looks invalid")
        if intent.action == "onboard":
            if not intent.role or intent.role not in self.roles:
                problems.append(f"the role is missing or unknown (known roles: {', '.join(self.roles)})")
        return problems

    def classify_extra(self, item: str) -> str:
        """'normal' | 'sensitive' | 'unsupported' for an extra-access request."""
        m = EXTRA_RE.match(item.strip().lower())
        if not m:
            return "unsupported"  # e.g. "admin": no tool exists for it
        kind, name = m.group(1), m.group(2)
        inventory = self.inv_channels if kind == "channel" else self.inv_repos
        if name not in inventory:
            return "unsupported"
        if name in self.sensitive.get(kind + "s", []):
            return "sensitive"
        return "normal"

    # ---- the correct end state ----
    def expected_state(self, intent: Intent, approved_extra: list[str], offboard_approved: bool) -> Expected:
        channels, repos = set(), set()
        if intent.action == "onboard":
            role = self.roles[intent.role]
            channels.update(role.get("channels", []))
            repos.update(role.get("repos", []))
            for item in approved_extra:
                kind, name = EXTRA_RE.match(item.strip().lower()).groups()
                (channels if kind == "channel" else repos).add(name)
        return Expected(
            action=intent.action,
            email=self.email_for(intent.first_name, intent.last_name),
            username=self.username_for(intent.first_name, intent.last_name),
            first_name=intent.first_name,
            last_name=intent.last_name,
            channels=sorted(channels),
            repos=sorted(repos),
            inventory_channels=self.inv_channels,
            inventory_repos=self.inv_repos,
            offboard_approved=offboard_approved,
        )

    # ---- the gate every tool call must pass ----
    def gate(self, tool: str, args: dict, exp: Expected) -> Optional[str]:
        """Return None if allowed, or a reason string if blocked."""
        allowed = ONBOARD_TOOLS if exp.action == "onboard" else OFFBOARD_TOOLS
        if tool not in allowed:
            return f"tool '{tool}' is not allowed for a {exp.action} task"
        if "email" in args and str(args["email"]).lower() != exp.email:
            return "the email does not match the person in this task"
        if tool == "mm_add_to_channel" and args.get("channel") not in exp.channels:
            return f"channel '{args.get('channel')}' is not in this person's approved access"
        if tool == "gitea_add_collaborator" and args.get("repo") not in exp.repos:
            return f"repo '{args.get('repo')}' is not in this person's approved access"
        if tool == "gitea_remove_collaborator" and args.get("repo") not in exp.inventory_repos:
            return f"repo '{args.get('repo')}' is not a managed repo"
        if tool in {"mm_deactivate_user", "gitea_disable_user"} and not exp.offboard_approved:
            return "offboarding has not been approved by a human"
        return None
