"""In-memory stand-ins for Mattermost and Gitea so tests run without Docker.
They offer the same methods as tools/apps.py."""
from agent.errors import ToolError


class FakeMM:
    def __init__(self, channels, drop_channel_adds=False):
        self.users = {}
        self.team = set()
        self.channels = {c: set() for c in channels}
        self.drop_channel_adds = drop_channel_adds  # simulates "says OK but did not save"
        self._n = 0

    def user_by_email(self, email):
        for u in self.users.values():
            if u["email"] == email:
                return dict(u)
        return None

    def user_by_username(self, username):
        for u in self.users.values():
            if u["username"] == username:
                return dict(u)
        return None

    def create_user(self, email, username, first_name, last_name, password):
        self._n += 1
        uid = f"mm{self._n}"
        self.users[uid] = {"id": uid, "email": email, "username": username,
                           "password": password, "delete_at": 0}
        return dict(self.users[uid])

    def is_team_member(self, user_id):
        return user_id in self.team

    def add_to_team(self, user_id):
        self.team.add(user_id)

    def _chan(self, name):
        if name not in self.channels:
            raise ToolError("channel_missing", f"channel '{name}' not found")
        return self.channels[name]

    def is_channel_member(self, channel, user_id):
        return user_id in self._chan(channel)

    def add_to_channel(self, channel, user_id):
        members = self._chan(channel)
        if not self.drop_channel_adds:
            members.add(user_id)

    def set_active(self, user_id, active):
        self.users[user_id]["delete_at"] = 0 if active else 1

    def can_login(self, email, password):
        u = self.user_by_email(email)
        return bool(u) and u["delete_at"] == 0 and u["password"] == password


class FakeGitea:
    def __init__(self, repos):
        self.users = {}
        self.repos = {r: set() for r in repos}

    def user_by_email(self, email):
        for u in self.users.values():
            if u["email"] == email:
                return dict(u)
        return None

    def user_by_username(self, username):
        u = self.users.get(username)
        return dict(u) if u else None

    def create_user(self, email, username, full_name, password):
        self.users[username] = {"login": username, "email": email, "password": password,
                                "active": True, "prohibit_login": False}
        return dict(self.users[username])

    def is_collaborator(self, repo, username):
        return username in self.repos[repo]

    def add_collaborator(self, repo, username):
        self.repos[repo].add(username)

    def remove_collaborator(self, repo, username):
        self.repos[repo].discard(username)

    def disable_user(self, username):
        self.users[username]["prohibit_login"] = True

    def can_login(self, username, password):
        u = self.users.get(username)
        return bool(u) and not u["prohibit_login"] and u["password"] == password
