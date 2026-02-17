"""User model placeholder until auth profile table is added to ORM."""
from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str
