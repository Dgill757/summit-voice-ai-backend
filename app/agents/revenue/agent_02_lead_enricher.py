"""
Agent 2: Lead Enricher
Enriches prospect data with emails, phone numbers, company info
Runs every 30 minutes, processes 10 prospects per batch
"""
from typing import Dict, Any, Optional
import httpx
import os
from datetime import datetime
import logging
from app.agents.base import BaseAgent
from app.models import Prospect

logger = logging.getLogger(__name__)

class LeadEnricherAgent(BaseAgent):
    """Enriches prospect data with additional information"""
    
    def __init__(self, db):
        super().__init__(agent_id=2, agent_name="Lead Enricher", db=db)
        self.hunter_api_key = os.getenv("HUNTER_API_KEY")
        self.clearbit_api_key = os.getenv("CLEARBIT_API_KEY")
        self.rocketreach_api_key = os.getenv("ROCKETREACH_API_KEY")
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get batch size from config
        batch_size = self.config.get('batch_size', 10)
        if os.getenv("DEMO_MODE", "").lower() == "true":
            batch_size = max(batch_size, 25)
        
        # Get prospects that need enrichment (new status, no email)
        prospects = self.db.query(Prospect).filter(
            Prospect.status == 'new',
            Prospect.enriched_at == None
        ).limit(batch_size).all()
        
        enriched_count = 0
        
        for prospect in prospects:
            try:
                if os.getenv("DEMO_MODE", "").lower() == "true":
                    if not prospect.phone:
                        prospect.phone = f"+1-555-20{prospect.id.int % 100000:05d}" if hasattr(prospect.id, "int") else "+1-555-2000000"
                    custom = prospect.custom_fields or {}
                    custom["enrichment_source"] = "Demo"
                    prospect.custom_fields = custom
                    prospect.enriched_at = datetime.utcnow()
                    prospect.status = "qualified"
                    enriched_count += 1
                    self.db.commit()
                    continue

                # Update status to enriching
                prospect.status = 'enriching'
                self.db.commit()
                
                # Enrich the prospect
                enriched = await self._enrich_prospect(prospect)
                
                if enriched:
                    prospect.enriched_at = datetime.utcnow()
                    prospect.status = 'qualified' if prospect.email else 'new'
                    enriched_count += 1
                
                self.db.commit()
                
            except Exception as e:
                self._log("enrich_prospect", "error", f"Failed to enrich {prospect.company_name}: {str(e)}")
                prospect.status = 'new'
                self.db.commit()
        
        return {"success": True, "data": {"prospects_processed": len(prospects), "prospects_enriched": enriched_count, "cost_usd": 0 if os.getenv('DEMO_MODE', '').lower() == 'true' else round(enriched_count * 0.02, 4)}}
    
    async def _enrich_prospect(self, prospect: Prospect) -> bool:
        """Enrich a single prospect with all available data"""
        enriched = False

        # Waterfall enrichment by email when available.
        if prospect.email:
            waterfall = await self.enrich_lead_waterfall(prospect.email, {"company_name": prospect.company_name})
            if waterfall and not waterfall.get("enrichment_failed"):
                if waterfall.get("email") and not prospect.email:
                    prospect.email = waterfall.get("email")
                if waterfall.get("phone") and not prospect.phone:
                    prospect.phone = waterfall.get("phone")
                custom = prospect.custom_fields or {}
                custom["enrichment_source"] = waterfall.get("source")
                prospect.custom_fields = custom
                enriched = True

        # Find email if missing
        if not prospect.email:
            email = await self._find_email(prospect)
            if email:
                prospect.email = email
                enriched = True
        
        # Find phone if missing
        if not prospect.phone:
            phone = await self._find_phone(prospect)
            if phone:
                prospect.phone = phone
                enriched = True
        
        # Enrich company data
        company_data = await self._enrich_company(prospect)
        if company_data:
            prospect.employee_count = company_data.get('employee_count', prospect.employee_count)
            prospect.revenue_estimate = company_data.get('revenue_estimate', prospect.revenue_estimate)
            prospect.tech_stack = company_data.get('tech_stack', prospect.tech_stack)
            enriched = True
        
        # Recalculate lead score
        prospect.lead_score = self._calculate_score(prospect)
        
        return enriched
    
    async def _find_email(self, prospect: Prospect) -> Optional[str]:
        """Find email using Hunter.io"""
        if not self.hunter_api_key or not prospect.website:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                # Hunter.io Domain Search API
                url = "https://api.hunter.io/v2/domain-search"
                
                params = {
                    "domain": prospect.website.replace('http://', '').replace('https://', '').split('/')[0],
                    "api_key": self.hunter_api_key,
                    "limit": 1
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    emails = data.get('data', {}).get('emails', [])
                    
                    if emails:
                        # Prioritize owner/ceo/president emails
                        for email in emails:
                            position = email.get('position', '').lower()
                            if any(title in position for title in ['owner', 'ceo', 'president', 'founder']):
                                return email.get('value')
                        
                        # Return first email if no match
                        return emails[0].get('value')
                
        except Exception as e:
            self._log("find_email", "warning", f"Hunter.io failed for {prospect.company_name}: {str(e)}")
        
        return None
    
    async def _find_phone(self, prospect: Prospect) -> Optional[str]:
        """Find phone using RocketReach"""
        if not self.rocketreach_api_key or not prospect.company_name:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.rocketreach.co/v1/api/company/search"
                
                headers = {
                    "Api-Key": self.rocketreach_api_key
                }
                
                params = {
                    "query": prospect.company_name,
                    "limit": 1
                }
                
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    companies = data.get('data', [])
                    
                    if companies:
                        return companies[0].get('phone')
                
        except Exception as e:
            self._log("find_phone", "warning", f"RocketReach failed for {prospect.company_name}: {str(e)}")
        
        return None
    
    async def _enrich_company(self, prospect: Prospect) -> Optional[Dict[str, Any]]:
        """Enrich company data using Clearbit"""
        if not self.clearbit_api_key or not prospect.website:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                # Clearbit Company API
                url = "https://company.clearbit.com/v2/companies/find"
                
                headers = {
                    "Authorization": f"Bearer {self.clearbit_api_key}"
                }
                
                params = {
                    "domain": prospect.website.replace('http://', '').replace('https://', '').split('/')[0]
                }
                
                response = await client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    return {
                        "employee_count": data.get('metrics', {}).get('employees'),
                        "revenue_estimate": data.get('metrics', {}).get('estimatedAnnualRevenue'),
                        "tech_stack": ', '.join(data.get('tech', []))
                    }
                
        except Exception as e:
            self._log("enrich_company", "warning", f"Clearbit failed for {prospect.company_name}: {str(e)}")
        
        return None
    
    def _calculate_score(self, prospect: Prospect) -> int:
        """Calculate enriched lead score"""
        score = 0
        
        # Has all contact info = 40 points
        if prospect.email:
            score += 20
        if prospect.phone:
            score += 20
        
        # Has website = 10 points
        if prospect.website:
            score += 10
        
        # Company size scoring
        if prospect.employee_count:
            if 10 <= prospect.employee_count <= 50:
                score += 20  # Sweet spot
            elif 5 <= prospect.employee_count < 10 or 50 < prospect.employee_count <= 100:
                score += 10  # Good
        
        # Revenue estimate = 10 points
        if prospect.revenue_estimate:
            score += 10
        
        # Has tech stack info = 10 points
        if prospect.tech_stack:
            score += 10
        
        return min(score, 100)

    async def enrich_lead_waterfall(self, lead_email: str, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Try enrichment providers in sequence until success."""
        if self.apollo_api_key:
            try:
                enriched = await self.enrich_with_apollo(lead_email)
                if enriched.get("email") and enriched.get("phone"):
                    enriched["source"] = "Apollo"
                    return enriched
            except Exception as exc:
                logger.warning("Apollo enrichment failed: %s", exc)

        if self.hunter_api_key:
            try:
                enriched = await self.enrich_with_hunter(lead_email)
                if enriched.get("email"):
                    enriched["source"] = "Hunter"
                    return enriched
            except Exception as exc:
                logger.warning("Hunter enrichment failed: %s", exc)

        if self.rocketreach_api_key:
            try:
                enriched = await self.enrich_with_rocketreach(lead_email)
                if enriched.get("email") or enriched.get("phone"):
                    enriched["source"] = "RocketReach"
                    return enriched
            except Exception as exc:
                logger.warning("RocketReach enrichment failed: %s", exc)

        return {"email": lead_email, "source": "None", "enrichment_failed": True, **lead_data}

    async def enrich_with_apollo(self, email: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.apollo.io/v1/people/match",
                headers={"X-Api-Key": self.apollo_api_key or ""},
                json={"email": email},
            )
            response.raise_for_status()
            return response.json().get("person", {}) or {}

    async def enrich_with_hunter(self, email: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://api.hunter.io/v2/email-verifier",
                params={"email": email, "api_key": self.hunter_api_key or ""},
            )
            response.raise_for_status()
            return response.json().get("data", {}) or {}

    async def enrich_with_rocketreach(self, email: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.rocketreach.co/v2/api/lookupProfile",
                headers={"Api-Key": self.rocketreach_api_key or ""},
                json={"email": email},
            )
            response.raise_for_status()
            return response.json() or {}
