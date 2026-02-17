"""Subscription model placeholder for Stripe-backed plans."""
from dataclasses import dataclass


@dataclass
class Subscription:
    id: str
    plan: str
    status: str
