from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from app.config import settings


class EnrichmentService:
    """Unified enrichment service (Clearbit + Hunter.io)."""

    def __init__(self):
        self.clearbit_key = os.getenv("CLEARBIT_API_KEY") or getattr(settings, "clearbit_api_key", None)
        self.hunter_key = os.getenv("HUNTER_API_KEY") or getattr(settings, "hunter_api_key", None)

    async def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        enriched: Dict[str, Any] = {}
        if not lead.get("email") and lead.get("contact_name") and lead.get("company_name"):
            first, last = self._split_name(lead.get("contact_name", ""))
            email = await self._find_email(first_name=first, last_name=last, company=lead["company_name"])
            if email:
                enriched["email"] = email

        if lead.get("company_name"):
            enriched.update(await self._enrich_company(lead["company_name"]))

        if lead.get("email") or enriched.get("email"):
            enriched.update(await self._enrich_person(lead.get("email") or enriched.get("email")))

        return enriched

    async def _find_email(self, first_name: str, last_name: str, company: str) -> Optional[str]:
        if not self.hunter_key:
            return None
        domain = self._extract_domain(company)
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://api.hunter.io/v2/email-finder",
                params={
                    "domain": domain,
                    "first_name": first_name,
                    "last_name": last_name,
                    "api_key": self.hunter_key,
                },
            )
            if response.status_code == 200:
                return (response.json().get("data") or {}).get("email")
        return None

    async def _enrich_company(self, company_name: str) -> Dict[str, Any]:
        if not self.clearbit_key:
            return {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://company.clearbit.com/v2/companies/find",
                params={"name": company_name},
                headers={"Authorization": f"Bearer {self.clearbit_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "website": data.get("domain"),
                    "industry": (data.get("category") or {}).get("industry"),
                    "employee_count": (data.get("metrics") or {}).get("employees"),
                    "custom_fields": {
                        "company_description": data.get("description"),
                        "company_revenue": (data.get("metrics") or {}).get("estimatedAnnualRevenue"),
                        "company_linkedin": (data.get("linkedin") or {}).get("handle"),
                    },
                }
        return {}

    async def _enrich_person(self, email: str) -> Dict[str, Any]:
        if not self.clearbit_key or not email:
            return {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://person.clearbit.com/v2/people/find",
                params={"email": email},
                headers={"Authorization": f"Bearer {self.clearbit_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "linkedin_url": self._absolute_handle((data.get("linkedin") or {}).get("handle"), "linkedin"),
                    "custom_fields": {
                        "twitter_url": self._absolute_handle((data.get("twitter") or {}).get("handle"), "twitter"),
                        "bio": data.get("bio"),
                        "location_detail": data.get("location"),
                    },
                }
        return {}

    def _extract_domain(self, company: str) -> str:
        return company.lower().replace(" ", "").replace(",", "") + ".com"

    def _split_name(self, name: str) -> tuple[str, str]:
        parts = [p for p in name.split(" ") if p]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[-1]

    def _absolute_handle(self, handle: Optional[str], provider: str) -> Optional[str]:
        if not handle:
            return None
        if handle.startswith("http"):
            return handle
        if provider == "linkedin":
            return f"https://www.linkedin.com/in/{handle}"
        return f"https://x.com/{handle}"

