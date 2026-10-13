"""The independent checker. Plain code, no AI.

It does NOT trust the model's words or any tool's success message. It asks
the two apps directly: "what is the real state right now?" and compares that
with the correct state computed from the company rules.
"""
from agent.models import Check


class Verifier:
    def __init__(self, mm, gitea, password):
        self.mm = mm
        self.gitea = gitea
        self.password = password

    # ---- helpers ----
    @staticmethod
    def _try(name, fn):
        try:
            ok, detail = fn()
            return Check(name=name, passed=bool(ok), detail=detail)
        except Exception as e:  # reading failed => we cannot prove it => fail
            return Check(name=name, passed=False, detail=f"could not verify: {e}")

    # ---- entry point ----
    def verify(self, exp) -> list:
        try:
            mu = self.mm.user_by_email(exp.email)
            gu = self.gitea.user_by_email(exp.email)
        except Exception as e:
            return [Check(name="read accounts from both apps", passed=False,
                          detail=f"could not read the apps: {e}")]
        if exp.action == "onboard":
            return self._onboard(exp, mu, gu)
        return self._offboard(exp, mu, gu)

    # ---- onboarding: must HAVE the right access and NOTHING extra ----
    def _onboard(self, exp, mu, gu):
        checks = []
        mm_active = mu is not None and mu.get("delete_at", 0) == 0
        checks.append(Check(name="Mattermost account exists and is active", passed=mm_active,
                            detail="found" if mu else "no account found"))
        g_active = gu is not None and gu.get("active", True) and not gu.get("prohibit_login", False)
        checks.append(Check(name="Gitea account exists and is active", passed=g_active,
                            detail="found" if gu else "no account found"))
        if mu:
            checks.append(self._try("Mattermost: member of the team",
                                    lambda: (self.mm.is_team_member(mu["id"]), "")))
            for ch in exp.inventory_channels:
                should = ch in exp.channels

                def chan(ch=ch, should=should):
                    actual = self.mm.is_channel_member(ch, mu["id"])
                    return actual == should, f"should be member={should}, actually member={actual}"
                checks.append(self._try(f"Mattermost channel '{ch}'", chan))
            checks.append(self._try("Mattermost: can log in",
                                    lambda: (self.mm.can_login(exp.email, self.password), "")))
        if gu:
            for repo in exp.inventory_repos:
                should = repo in exp.repos

                def repo_check(repo=repo, should=should):
                    actual = self.gitea.is_collaborator(repo, gu["login"])
                    return actual == should, f"should have access={should}, actually has access={actual}"
                checks.append(self._try(f"Gitea repo '{repo}'", repo_check))
            checks.append(self._try("Gitea: can log in",
                                    lambda: (self.gitea.can_login(gu["login"], self.password), "")))
        return checks

    # ---- offboarding: nothing active, nothing reachable, login fails ----
    def _offboard(self, exp, mu, gu):
        if mu is None and gu is None:
            return [Check(name="an account exists to offboard", passed=False,
                          detail="no account found in either app: nothing was offboarded (is the name right?)")]
        checks = []
        if mu is None:
            checks.append(Check(name="Mattermost account", passed=True, detail="none found (nothing to deactivate)"))
        else:
            checks.append(Check(name="Mattermost account is deactivated",
                                passed=mu.get("delete_at", 0) > 0, detail=""))
            checks.append(self._try("Mattermost: login is refused",
                                    lambda: (not self.mm.can_login(exp.email, self.password), "")))
        if gu is None:
            checks.append(Check(name="Gitea account", passed=True, detail="none found (nothing to disable)"))
        else:
            disabled = bool(gu.get("prohibit_login")) or not gu.get("active", True)
            checks.append(Check(name="Gitea account is disabled", passed=disabled, detail=""))
            checks.append(self._try("Gitea: login is refused",
                                    lambda: (not self.gitea.can_login(gu["login"], self.password), "")))
            for repo in exp.inventory_repos:
                def repo_check(repo=repo):
                    actual = self.gitea.is_collaborator(repo, gu["login"])
                    return (not actual), f"has access={actual}"
                checks.append(self._try(f"Gitea repo '{repo}': no access", repo_check))
        return checks
