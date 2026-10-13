"""Thin clients for the two real apps (Mattermost and Gitea).

Only this file knows the apps' API details. If an API call needs fixing,
this is the place. Each method returns plain data or raises
TransientError (retry) / ToolError (permanent problem).
"""
import httpx

from agent import config
from agent.errors import ToolError, TransientError

TIMEOUT = 10.0


def _call(method, url, **kw):
    try:
        r = httpx.request(method, url, timeout=TIMEOUT, **kw)
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        raise TransientError(f"network problem calling {url}: {e}") from e
    if r.status_code >= 500:
        raise TransientError(f"server error {r.status_code} from {url}: {r.text[:200]}")
    return r


def _fail(code, r):
    raise ToolError(code, f"{r.request.method} {r.request.url} -> {r.status_code}: {r.text[:300]}")


class Mattermost:
    def __init__(self):
        self.base = config.MM_URL.rstrip("/") + "/api/v4"
        self._token = None
        self._team_id = None

    # ---- plumbing ----
    def _headers(self):
        if not self._token:
            r = _call("POST", f"{self.base}/users/login",
                      json={"login_id": config.MM_ADMIN_EMAIL, "password": config.MM_ADMIN_PASSWORD})
            if r.status_code != 200:
                _fail("mm_admin_login_failed", r)
            self._token = r.headers["Token"]
        return {"Authorization": f"Bearer {self._token}"}

    def req(self, method, path, **kw):
        return _call(method, self.base + path, headers=self._headers(), **kw)

    def team_id(self):
        if not self._team_id:
            r = self.req("GET", f"/teams/name/{config.MM_TEAM}")
            if r.status_code != 200:
                _fail("mm_team_missing", r)
            self._team_id = r.json()["id"]
        return self._team_id

    def _channel_id(self, name):
        r = self.req("GET", f"/teams/{self.team_id()}/channels/name/{name}")
        if r.status_code != 200:
            raise ToolError("channel_missing", f"channel '{name}' was not found in team '{config.MM_TEAM}'")
        return r.json()["id"]

    # ---- reads ----
    def user_by_email(self, email):
        r = self.req("GET", f"/users/email/{email}")
        return r.json() if r.status_code == 200 else None

    def user_by_username(self, username):
        r = self.req("GET", f"/users/username/{username}")
        return r.json() if r.status_code == 200 else None

    def is_team_member(self, user_id):
        return self.req("GET", f"/teams/{self.team_id()}/members/{user_id}").status_code == 200

    def is_channel_member(self, channel, user_id):
        cid = self._channel_id(channel)
        return self.req("GET", f"/channels/{cid}/members/{user_id}").status_code == 200

    def can_login(self, email, password):
        r = _call("POST", f"{self.base}/users/login", json={"login_id": email, "password": password})
        return r.status_code == 200

    # ---- writes ----
    def create_user(self, email, username, first_name, last_name, password):
        r = self.req("POST", "/users", json={"email": email, "username": username,
                                             "first_name": first_name, "last_name": last_name,
                                             "password": password})
        if r.status_code != 201:
            _fail("mm_create_user_failed", r)
        return r.json()

    def add_to_team(self, user_id):
        r = self.req("POST", f"/teams/{self.team_id()}/members",
                     json={"team_id": self.team_id(), "user_id": user_id})
        if r.status_code not in (200, 201):
            _fail("mm_add_to_team_failed", r)

    def add_to_channel(self, channel, user_id):
        cid = self._channel_id(channel)
        r = self.req("POST", f"/channels/{cid}/members", json={"user_id": user_id})
        if r.status_code not in (200, 201):
            _fail("mm_add_to_channel_failed", r)

    def set_active(self, user_id, active):
        r = self.req("PUT", f"/users/{user_id}/active", json={"active": active})
        if r.status_code != 200:
            _fail("mm_set_active_failed", r)


class Gitea:
    def __init__(self):
        self.base = config.GITEA_URL.rstrip("/") + "/api/v1"
        self.owner = config.GITEA_OWNER

    def req(self, method, path, **kw):
        headers = {"Authorization": f"token {config.GITEA_TOKEN}"}
        return _call(method, self.base + path, headers=headers, **kw)

    # ---- reads ----
    def all_users(self):
        users, page = [], 1
        while True:
            r = self.req("GET", "/admin/users", params={"page": page, "limit": 50})
            if r.status_code != 200:
                _fail("gitea_list_users_failed", r)
            batch = r.json()
            users.extend(batch)
            if len(batch) < 50:
                return users
            page += 1

    def user_by_email(self, email):
        for u in self.all_users():
            if (u.get("email") or "").lower() == email.lower():
                return u
        return None

    def user_by_username(self, username):
        for u in self.all_users():
            if (u.get("login") or "").lower() == username.lower():
                return u
        return None

    def is_collaborator(self, repo, username):
        r = self.req("GET", f"/repos/{self.owner}/{repo}/collaborators/{username}")
        return r.status_code == 204

    def can_login(self, username, password):
        r = _call("GET", f"{self.base}/user", auth=(username, password))
        return r.status_code == 200

    # ---- writes ----
    def create_user(self, email, username, full_name, password):
        r = self.req("POST", "/admin/users", json={
            "email": email, "username": username, "full_name": full_name,
            "password": password, "must_change_password": False, "send_notify": False})
        if r.status_code != 201:
            _fail("gitea_create_user_failed", r)
        return r.json()

    def add_collaborator(self, repo, username):
        r = self.req("PUT", f"/repos/{self.owner}/{repo}/collaborators/{username}",
                     json={"permission": "write"})
        if r.status_code != 204:
            _fail("gitea_add_collaborator_failed", r)

    def remove_collaborator(self, repo, username):
        r = self.req("DELETE", f"/repos/{self.owner}/{repo}/collaborators/{username}")
        if r.status_code != 204:
            _fail("gitea_remove_collaborator_failed", r)

    def disable_user(self, username):
        r = self.req("PATCH", f"/admin/users/{username}",
                     json={"login_name": username, "source_id": 0, "prohibit_login": True})
        if r.status_code != 200:
            _fail("gitea_disable_user_failed", r)
