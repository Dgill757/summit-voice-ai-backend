"""Workflow placeholder model for future orchestration persistence."""
from dataclasses import dataclass


@dataclass
class Workflow:
    id: str
    name: str
    is_active: bool = True
