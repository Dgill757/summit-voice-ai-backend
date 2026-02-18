from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings


class ApolloClient:
    """Apollo.io API client for lead scraping/enrichment."""

    BASE_URL = "https://api.apollo.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("APOLLO_API_KEY") or getattr(settings, "apollo_api_key", None)
        if not key:
            raise ValueError("APOLLO_API_KEY is not configured")
        self.api_key = key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def search_people(
        self,
        titles: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        company_sizes: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        payload = {
            "q_organization_keyword_tags": industries or [],
            "person_titles": titles or [],
            "person_locations": locations or [],
            "organization_num_employees_ranges": company_sizes or [],
            "page": 1,
            "per_page": limit,
        }
        response = await self.client.post("/mixed_people/search", json=payload)
        response.raise_for_status()
        data = response.json()
        return self._normalize_leads(data.get("people", []))

    async def enrich_person(
        self, email: Optional[str] = None, linkedin_url: Optional[str] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if email:
            payload["email"] = email
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url
        response = await self.client.post("/people/match", json=payload)
        response.raise_for_status()
        person = response.json().get("person") or {}
        return self._normalize_person(person)

    def _normalize_leads(self, people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        leads: List[Dict[str, Any]] = []
        for person in people:
            org = person.get("organization") or {}
            phone_numbers = person.get("phone_numbers") or [{}]
            lead = {
                "contact_name": " ".join(
                    x for x in [person.get("first_name"), person.get("last_name")] if x
                ).strip()
                or person.get("name")
                or "",
                "email": person.get("email"),
                "phone": (phone_numbers[0] or {}).get("raw_number"),
                "company_name": org.get("name"),
                "title": person.get("title"),
                "linkedin_url": person.get("linkedin_url"),
                "city": person.get("city") or org.get("city"),
                "industry": org.get("industry"),
                "employee_count": org.get("estimated_num_employees"),
                "source": "apollo",
                "custom_fields": {"apollo_raw_data": person},
            }
            leads.append(lead)
        return leads

    def _normalize_person(self, person: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_leads([person])
        return normalized[0] if normalized else {}

    async def close(self):
        await self.client.aclose()
