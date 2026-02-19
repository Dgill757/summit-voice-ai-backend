"""
Agent 1: Lead Scraper
Scrapes real roofing prospects from Apollo.io only.
"""
from typing import Any, Dict, List
import os

from app.agents.base import BaseAgent
from app.models import Prospect
from app.config import REVENUE_SPRINT_MODE
from app.integrations.apollo import ApolloClient


class LeadScraperAgent(BaseAgent):
    """Scrape REAL leads from Apollo (no demo fallback)."""

    def __init__(self, db):
        super().__init__(agent_id=1, agent_name="Lead Scraper", db=db)
        self.apollo_api_key = os.getenv("APOLLO_API_KEY")

    async def execute(self) -> Dict[str, Any]:
        """Main execution logic."""
        if not self.apollo_api_key:
            self._log("scrape_apollo", "error", "APOLLO_API_KEY not configured")
            return {
                "success": False,
                "data": {
                    "prospects_found": 0,
                    "prospects_saved": 0,
                    "states_searched": 0,
                    "error": "APOLLO_API_KEY missing",
                    "cost_usd": 0,
                },
            }

        per_state_limit = int(self.config.get("batch_size", 25))
        if REVENUE_SPRINT_MODE.get("enabled"):
            per_state_limit = min(per_state_limit, REVENUE_SPRINT_MODE.get("apollo_daily_limit", 160))

        target_states = ["TX", "FL", "CA", "AZ", "GA", "NC", "TN"]
        target_titles = ["Owner", "CEO", "President", "General Manager", "Founder"]

        all_leads: List[Dict[str, Any]] = []
        errors: List[str] = []
        try:
            client = ApolloClient(api_key=self.apollo_api_key)
            try:
                for state in target_states:
                    try:
                        state_leads = await client.search_people(
                            titles=target_titles,
                            industries=["Roofing", "Roofing Contractor", "Roof Repair"],
                            locations=[state],
                            company_sizes=["11,50", "51,200", "201,500"],
                            limit=per_state_limit,
                        )
                        if not state_leads:
                            self._log("scrape_apollo", "warning", f"Apollo returned 0 results for {state}")
                            continue
                        all_leads.extend(state_leads)
                        self._log("scrape_apollo", "success", f"Scraped {len(state_leads)} leads for {state}")
                    except Exception as exc:
                        msg = f"{state}: {exc}"
                        errors.append(msg)
                        self._log("scrape_apollo", "error", msg)
            finally:
                await client.close()
        except Exception as exc:
            msg = f"Apollo client init failed: {exc}"
            self._log("scrape_apollo", "error", msg)
            return {
                "success": False,
                "data": {
                    "prospects_found": 0,
                    "prospects_saved": 0,
                    "states_searched": len(target_states),
                    "error": msg,
                    "cost_usd": 0,
                },
            }

        saved_count = await self._save_prospects(all_leads)
        return {
            "success": True,
            "data": {
                "prospects_found": len(all_leads),
                "prospects_saved": saved_count,
                "states_searched": len(target_states),
                "error_count": len(errors),
                "errors": errors[:10],
                "cost_usd": round(len(all_leads) * 0.01, 4),
            },
        }

    async def _save_prospects(self, prospects: List[Dict[str, Any]]) -> int:
        """Save prospects to database and skip duplicates by email."""
        saved_count = 0
        for prospect_data in prospects:
            email = prospect_data.get("email")
            if not email:
                continue
            try:
                existing = self.db.query(Prospect).filter(Prospect.email == email).first()
                if existing:
                    continue
                prospect = Prospect(
                    company_name=prospect_data.get("company_name") or "Unknown Company",
                    contact_name=prospect_data.get("contact_name"),
                    title=prospect_data.get("title"),
                    email=email,
                    phone=prospect_data.get("phone"),
                    linkedin_url=prospect_data.get("linkedin_url"),
                    website=prospect_data.get("website"),
                    city=prospect_data.get("city"),
                    state=prospect_data.get("state"),
                    industry="Roofing",
                    source="Apollo",
                    lead_score=self._calculate_initial_score(prospect_data),
                    custom_fields=prospect_data.get("custom_fields") or {},
                )
                self.db.add(prospect)
                saved_count += 1
            except Exception as exc:
                self._log("save_prospect", "warning", f"Failed to save lead {email}: {exc}")
                continue
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self._log("save_prospects", "error", f"Database commit failed: {exc}")
            return 0
        return saved_count

    def _calculate_initial_score(self, prospect_data: Dict[str, Any]) -> int:
        score = 50
        if prospect_data.get("email"):
            score += 20
        if prospect_data.get("phone"):
            score += 10
        if prospect_data.get("website"):
            score += 10
        emp_count = prospect_data.get("employee_count", 0) or 0
        if 10 <= emp_count <= 200:
            score += 10
        return min(score, 100)
