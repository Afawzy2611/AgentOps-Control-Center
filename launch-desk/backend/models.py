from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class LaunchBrief(BaseModel):
    product_brief: str = Field(min_length=10)
    audience: str = Field(min_length=3)
    launch_date: str = Field(min_length=4)
    constraints: str = ""
    available_assets: str = ""


class LaunchTask(BaseModel):
    title: str
    priority: Literal["P0", "P1", "P2"]
    owner: str
    due: str
    rationale: str


class RiskItem(BaseModel):
    risk: str
    severity: Literal["High", "Medium", "Low"]
    mitigation: str
    owner: str


class LaunchPlan(BaseModel):
    executive_summary: str
    prioritized_plan: list[LaunchTask]
    risks: list[RiskItem]
    owner_checklist: list[str]
    launch_copy: dict[str, str]
    follow_up_questions: list[str]
    readiness_score: int = Field(ge=0, le=100)
