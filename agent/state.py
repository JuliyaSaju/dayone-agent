"""SQLite memory: every task and every action is written down (the audit log)."""
import json
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str = "dayone.db"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request TEXT, status TEXT, intent TEXT, report TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS actions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER, tool TEXT, args TEXT, status TEXT,
                result TEXT, ms INTEGER, ts TEXT);
            """
        )

    def new_task(self, request: str) -> int:
        cur = self.db.execute(
            "INSERT INTO tasks(request,status,created_at) VALUES(?,?,?)",
            (request, "STARTED", _now()),
        )
        self.db.commit()
        return cur.lastrowid

    def update_task(self, task_id: int, **fields):
        allowed = {"status", "intent", "report"}
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"cannot update column {key}")
            if not isinstance(value, str):
                value = json.dumps(value)
            self.db.execute(f"UPDATE tasks SET {key}=? WHERE id=?", (value, task_id))
        self.db.commit()

    def log_start(self, task_id: int, tool: str, args: dict) -> int:
        """Written BEFORE the action runs, so a crash still leaves a trace."""
        cur = self.db.execute(
            "INSERT INTO actions(task_id,tool,args,status,ts) VALUES(?,?,?,?,?)",
            (task_id, tool, json.dumps(args, sort_keys=True), "intended", _now()),
        )
        self.db.commit()
        return cur.lastrowid

    def log_end(self, action_id: int, status: str, result: dict, ms: int):
        self.db.execute(
            "UPDATE actions SET status=?, result=?, ms=? WHERE id=?",
            (status, json.dumps(result), ms, action_id),
        )
        self.db.commit()

    def actions(self, task_id: int) -> list[dict]:
        rows = self.db.execute(
            "SELECT tool,args,status,result,ms,ts FROM actions WHERE task_id=? ORDER BY id",
            (task_id,),
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "tool": r["tool"],
                "args": json.loads(r["args"]),
                "status": r["status"],
                "result": json.loads(r["result"]) if r["result"] else None,
                "ms": r["ms"],
                "ts": r["ts"],
            })
        return out
