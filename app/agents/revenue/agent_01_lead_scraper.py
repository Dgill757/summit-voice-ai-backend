"""
Agent 1: Lead Scraper
Finds and scrapes qualified leads from Apollo.io and Google Maps
Target: 50+ new prospects daily
"""
from typing import Dict, Any, List
import httpx
import os
import random
from datetime import datetime
from app.agents.base import BaseAgent
from app.models import Prospect
from app.config import REVENUE_SPRINT_MODE
from app.integrations.apollo import ApolloClient

class LeadScraperAgent(BaseAgent):
    """Scrapes leads from Apollo and Google Maps"""
    
    def __init__(self, db):
        super().__init__(agent_id=1, agent_name="Lead Scraper", db=db)
        self.apollo_api_key = os.getenv("APOLLO_API_KEY")
        self.google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        daily_target = self.config.get('daily_target', 50)
        if REVENUE_SPRINT_MODE.get("enabled"):
            daily_target = min(REVENUE_SPRINT_MODE.get("daily_lead_target", 100), REVENUE_SPRINT_MODE.get("apollo_daily_limit", 160))
        
        prospects_scraped = []
        apollo_error = None
        gmaps_error = None
        demo_mode = os.getenv("DEMO_MODE", "").lower() == "true"
        allow_auto_demo = os.getenv("AUTO_DEMO_ON_EMPTY", "false").lower() == "true"

        if demo_mode:
            prospects_scraped = self._generate_demo_prospects(count=max(50, daily_target))
        else:
            # Scrape from Apollo
            apollo_prospects, apollo_error = await self._scrape_apollo(limit=daily_target // 2)
            prospects_scraped.extend(apollo_prospects)

            # Scrape from Google Maps
            gmaps_prospects, gmaps_error = await self._scrape_google_maps(limit=daily_target // 2)
            prospects_scraped.extend(gmaps_prospects)

            if not prospects_scraped and allow_auto_demo:
                self._log(
                    "scrape_fallback",
                    "warning",
                    "No live prospects returned from APIs; using demo fallback leads",
                )
                prospects_scraped = self._generate_demo_prospects(count=max(25, daily_target // 2))
        
        # Save to database
        saved_count = await self._save_prospects(prospects_scraped)
        
        demo_count = len([p for p in prospects_scraped if p.get("custom_fields", {}).get("demo_lead") is True])
        live_count = len(prospects_scraped) - demo_count

        return {
            "success": True,
            "data": {
                "prospects_found": len(prospects_scraped),
                "prospects_saved": saved_count,
                "sources": {
                    "apollo": len([p for p in prospects_scraped if p.get("source") == "apollo"]),
                    "google_maps": len([p for p in prospects_scraped if p.get("source") == "google_maps"]),
                    "demo": demo_count,
                },
                "auto_demo_fallback": allow_auto_demo and demo_count > 0 and not demo_mode,
                "apollo_error": apollo_error,
                "google_maps_error": gmaps_error,
                # Only bill live lead generation, never demo fallback rows.
                "cost_usd": 0 if (demo_mode or live_count <= 0) else round(live_count * 0.01, 4),
            }
        }

    def _generate_demo_prospects(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate realistic demo leads for full pipeline testing."""
        demo: List[Dict[str, Any]] = []
        states = ["TX", "FL", "CA", "NC", "GA", "AZ", "TN"]
        cities = ["Austin", "Dallas", "Miami", "Orlando", "Phoenix", "Charlotte", "Nashville", "San Diego", "Tampa"]
        titles = ["Owner", "CEO", "President", "General Manager"]
        for i in range(count):
            state = random.choice(states)
            city = random.choice(cities)
            company = f"Elite Roofing {state} {i + 1}"
            demo.append(
                {
                    "company_name": company,
                    "contact_name": f"John Smith {i + 1}",
                    "title": random.choice(titles),
                    "email": f"owner{i + 1}@roofingcompany{i + 1}.com",
                    "phone": f"+1-555-010{i:02d}",
                    "website": f"https://{company.lower().replace(' ', '')}.com",
                    "city": city,
                    "state": state,
                    "industry": "roofing",
                    "source": "demo",
                    "custom_fields": {"demo_lead": True},
                }
            )
        return demo
    
    async def _scrape_apollo(self, limit: int) -> tuple[List[Dict[str, Any]], str | None]:
        """Scrape leads from Apollo.io"""
        if not self.apollo_api_key:
            return [], "APOLLO_API_KEY not configured"
        
        prospects = []
        
        try:
            client = ApolloClient(api_key=self.apollo_api_key)
            try:
                # Primary query: explicit roofing focus + owner-level titles in core states.
                prospects = await client.search_people(
                    titles=["Owner", "CEO", "President", "General Manager"],
                    industries=["Construction", "Roofing"],
                    locations=["Texas", "Florida", "California", "North Carolina", "Georgia", "Arizona", "Tennessee"],
                    company_sizes=["11,50", "51,200"],
                    limit=limit,
                )

                # Broader fallback if primary returns too few rows.
                if len(prospects) < max(5, limit // 3):
                    fallback = await client.search_people(
                        titles=["Owner", "CEO", "President", "Founder"],
                        industries=["Construction"],
                        locations=["United States"],
                        company_sizes=["1,10", "11,50", "51,200"],
                        limit=limit,
                    )
                    prospects.extend(fallback)
            finally:
                await client.close()
                
        except Exception as e:
            error_message = f"Apollo scraping failed: {str(e)}"
            self._log("scrape_apollo", "error", error_message)
            return [], error_message
        
        # Normalize source label to match existing dashboard filters.
        for p in prospects:
            p["source"] = "apollo"
        return prospects[:limit], None
    
    async def _scrape_google_maps(self, limit: int) -> tuple[List[Dict[str, Any]], str | None]:
        """Scrape leads from Google Maps API"""
        if not self.google_maps_api_key:
            return [], "GOOGLE_MAPS_API_KEY not configured"
        
        prospects = []
        
        try:
            async with httpx.AsyncClient() as client:
                # Search terms for different industries
                search_queries = [
                    "roofing company",
                    "hvac company",
                    "plumbing company",
                    "restoration company"
                ]
                
                for query in search_queries:
                    # Google Places API Text Search
                    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                    
                    params = {
                        "query": query,
                        "key": self.google_maps_api_key,
                        "type": "point_of_interest"
                    }
                    
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for place in data.get('results', [])[:limit//len(search_queries)]:
                            # Get place details
                            details = await self._get_place_details(client, place.get('place_id'))
                            
                            if details:
                                prospect = {
                                    "company_name": place.get('name', ''),
                                    "address": place.get('formatted_address', ''),
                                    "phone": details.get('formatted_phone_number', ''),
                                    "website": details.get('website', ''),
                                    "industry": self._detect_industry([query]),
                                    "source": "google_maps",
                                    "custom_fields": {
                                        "google_place_id": place.get('place_id'),
                                        "google_rating": place.get('rating'),
                                        "google_reviews": place.get('user_ratings_total')
                                    }
                                }
                                
                                prospects.append(prospect)
                
        except Exception as e:
            error_message = f"Google Maps scraping failed: {str(e)}"
            self._log("scrape_google_maps", "error", error_message)
            return [], error_message
        
        return prospects, None
    
    async def _get_place_details(self, client: httpx.AsyncClient, place_id: str) -> Dict[str, Any]:
        """Get detailed information for a place"""
        try:
            url = "https://maps.googleapis.com/maps/api/place/details/json"
            
            params = {
                "place_id": place_id,
                "fields": "name,formatted_phone_number,website,formatted_address",
                "key": self.google_maps_api_key
            }
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                return response.json().get('result', {})
                
        except Exception:
            pass
        
        return {}
    
    async def _save_prospects(self, prospects: List[Dict[str, Any]]) -> int:
        """Save prospects to database, avoiding duplicates"""
        saved_count = 0
        
        for prospect_data in prospects:
            try:
                # Check if prospect already exists (by company name and email)
                existing = self.db.query(Prospect).filter(
                    Prospect.company_name == prospect_data.get('company_name'),
                    Prospect.email == prospect_data.get('email')
                ).first()
                
                if not existing:
                    # Create new prospect
                    prospect = Prospect(
                        **prospect_data,
                        scraped_at=datetime.utcnow(),
                        lead_score=self._calculate_initial_score(prospect_data)
                    )
                    
                    self.db.add(prospect)
                    saved_count += 1
                    
            except Exception as e:
                self._log("save_prospect", "warning", f"Failed to save prospect: {str(e)}")
                continue
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            saved_count = 0
            self._log("save_prospects", "error", f"Database commit failed: {str(e)}")
        
        return saved_count
    
    def _detect_industry(self, keywords: List[str]) -> str:
        """Detect industry from keywords"""
        keywords_str = ' '.join(keywords).lower()
        
        if 'roofing' in keywords_str or 'roof' in keywords_str:
            return 'roofing'
        elif 'hvac' in keywords_str or 'heating' in keywords_str or 'cooling' in keywords_str:
            return 'hvac'
        elif 'plumb' in keywords_str:
            return 'plumbing'
        elif 'solar' in keywords_str:
            return 'solar'
        elif 'restoration' in keywords_str or 'restore' in keywords_str:
            return 'restoration'
        else:
            return 'other'
    
    def _calculate_initial_score(self, prospect_data: Dict[str, Any]) -> int:
        """Calculate initial lead score based on available data"""
        score = 50  # Base score
        
        # Has email = +20
        if prospect_data.get('email'):
            score += 20
        
        # Has phone = +10
        if prospect_data.get('phone'):
            score += 10
        
        # Has website = +10
        if prospect_data.get('website'):
            score += 10
        
        # Employee count in sweet spot (10-50) = +10
        emp_count = prospect_data.get('employee_count', 0)
        if 10 <= emp_count <= 50:
            score += 10
        
        return min(score, 100)
