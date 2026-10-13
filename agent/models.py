"""Data shapes used everywhere. Pydantic checks them for us."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Intent(BaseModel):
    """What the manager's sentence means, in structured form."""
    action: Literal["onboard", "offboard"]
    first_name: str = ""
    last_name: str = ""
    role: Optional[str] = None
    extra_access: list[str] = Field(default_factory=list)


class Expected(BaseModel):
    """The end state the company rules say is correct. Built by code, not by the AI."""
    action: str
    email: str
    username: str
    first_name: str
    last_name: str
    channels: list[str] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)
    inventory_channels: list[str] = Field(default_factory=list)
    inventory_repos: list[str] = Field(default_factory=list)
    offboard_approved: bool = False


class Check(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class Report(BaseModel):
    task_id: int
    status: str  # VERIFIED | FAILED_VERIFICATION | NEEDS_HUMAN | REJECTED_BY_HUMAN
    request: str
    intent: Optional[Intent] = None
    expected: Optional[Expected] = None
    checks: list[Check] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    actions: list[dict] = Field(default_factory=list)
    agent_summary: Optional[str] = None
    seconds: float = 0.0
