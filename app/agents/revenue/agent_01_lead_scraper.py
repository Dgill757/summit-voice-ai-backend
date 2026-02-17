"""
Agent 1: Lead Scraper
Finds and scrapes qualified leads from Apollo.io and Google Maps
Target: 50+ new prospects daily
"""
from typing import Dict, Any, List
import httpx
import os
from datetime import datetime
from app.agents.base import BaseAgent
from app.models import Prospect

class LeadScraperAgent(BaseAgent):
    """Scrapes leads from Apollo and Google Maps"""
    
    def __init__(self, db):
        super().__init__(agent_id=1, agent_name="Lead Scraper", db=db)
        self.apollo_api_key = os.getenv("APOLLO_API_KEY")
        self.google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get daily target from config
        daily_target = self.config.get('daily_target', 50)
        
        prospects_scraped = []
        
        # Scrape from Apollo
        apollo_prospects = await self._scrape_apollo(limit=daily_target // 2)
        prospects_scraped.extend(apollo_prospects)
        
        # Scrape from Google Maps
        gmaps_prospects = await self._scrape_google_maps(limit=daily_target // 2)
        prospects_scraped.extend(gmaps_prospects)
        
        # Save to database
        if not prospects_scraped and os.getenv("DEMO_MODE", "").lower() == "true":
            prospects_scraped = self._generate_demo_prospects(count=max(5, daily_target // 2))

        saved_count = await self._save_prospects(prospects_scraped)
        
        return {
            "success": True,
            "data": {
                "prospects_found": len(prospects_scraped),
                "prospects_saved": saved_count,
                "sources": {
                    "apollo": len(apollo_prospects),
                    "google_maps": len(gmaps_prospects)
                }
            }
        }

    def _generate_demo_prospects(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate deterministic demo leads when external APIs are unavailable."""
        demo: List[Dict[str, Any]] = []
        for i in range(count):
            demo.append(
                {
                    "company_name": f"Summit Roofing Demo {i + 1}",
                    "contact_name": f"Owner {i + 1}",
                    "title": "Owner",
                    "email": f"demo.lead{i + 1}@example.com",
                    "phone": f"+1-555-010{i:02d}",
                    "website": f"https://summit-demo-{i + 1}.com",
                    "city": "Phoenix",
                    "state": "AZ",
                    "industry": "roofing",
                    "source": "demo",
                }
            )
        return demo
    
    async def _scrape_apollo(self, limit: int) -> List[Dict[str, Any]]:
        """Scrape leads from Apollo.io"""
        if not self.apollo_api_key:
            return []
        
        prospects = []
        
        try:
            async with httpx.AsyncClient() as client:
                # Apollo API endpoint for people/organizations search
                url = "https://api.apollo.io/v1/mixed_people/search"
                
                headers = {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "X-Api-Key": self.apollo_api_key
                }
                
                # Search criteria for roofing/HVAC/plumbing companies
                payload = {
                    "q_organization_domains": "",
                    "page": 1,
                    "per_page": limit,
                    "organization_locations": ["United States"],
                    "organization_num_employees_ranges": ["1,10", "11,50", "51,200"],
                    "person_titles": ["owner", "ceo", "president", "founder", "director"],
                    "q_organization_keyword_tags": ["roofing", "hvac", "plumbing", "restoration"]
                }
                
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for person in data.get('people', []):
                        org = person.get('organization', {})
                        
                        # Extract prospect data
                        prospect = {
                            "company_name": org.get('name', ''),
                            "contact_name": person.get('name', ''),
                            "title": person.get('title', ''),
                            "email": person.get('email', ''),
                            "phone": org.get('phone', ''),
                            "linkedin_url": person.get('linkedin_url', ''),
                            "website": org.get('website_url', ''),
                            "city": org.get('city', ''),
                            "state": org.get('state', ''),
                            "employee_count": org.get('estimated_num_employees', 0),
                            "industry": self._detect_industry(org.get('keywords', [])),
                            "source": "apollo"
                        }
                        
                        if prospect["company_name"]:
                            prospects.append(prospect)
                
        except Exception as e:
            self._log("scrape_apollo", "error", f"Apollo scraping failed: {str(e)}")
        
        return prospects
    
    async def _scrape_google_maps(self, limit: int) -> List[Dict[str, Any]]:
        """Scrape leads from Google Maps API"""
        if not self.google_maps_api_key:
            return []
        
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
            self._log("scrape_google_maps", "error", f"Google Maps scraping failed: {str(e)}")
        
        return prospects
    
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
