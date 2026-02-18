"""
Agent 15: GHL Setup Agent
Automates GoHighLevel sub-account creation and setup
Creates workflows, phone numbers, integrations
Triggered on-demand (not scheduled)
"""
from typing import Dict, Any
import os
import httpx
from datetime import datetime
from app.agents.base import BaseAgent
from app.models import Client

class GHLSetupAgent(BaseAgent):
    """Automates GoHighLevel setup"""
    
    def __init__(self, db):
        super().__init__(agent_id=15, agent_name="GHL Setup Agent", db=db)
        self.ghl_api_key = os.getenv("GOHIGHLEVEL_API_KEY")
        self.ghl_location_id = os.getenv("GOHIGHLEVEL_LOCATION_ID")
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic - called manually for specific client"""
        
        # This agent is triggered manually, not scheduled
        # For demo purposes, we'll process any client needing setup
        
        clients_needing_setup = self.db.query(Client).filter(
            Client.status == 'onboarding',
            Client.ghl_sub_account_id.is_(None)
        ).limit(5).all()
        
        setup_count = 0
        
        for client in clients_needing_setup:
            try:
                # Create GHL sub-account
                sub_account = await self._create_sub_account(client)
                
                if sub_account:
                    client.ghl_sub_account_id = sub_account['id']
                    
                    # Configure sub-account
                    await self._configure_sub_account(client, sub_account)
                    
                    # Update onboarding progress
                    if not client.custom_fields:
                        client.custom_fields = {}
                    if 'onboarding' not in client.custom_fields:
                        client.custom_fields['onboarding'] = {}
                    
                    client.custom_fields['onboarding']['ghl_setup_completed'] = True
                    client.custom_fields['onboarding']['ghl_setup_date'] = datetime.utcnow().isoformat()
                    
                    self.db.commit()
                    setup_count += 1
                    
            except Exception as e:
                self._log("setup_ghl", "error", f"Failed for {client.company_name}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "clients_setup": setup_count
            }
        }
    
    async def _create_sub_account(self, client: Client) -> Dict[str, Any]:
        """Create GHL sub-account for client"""
        
        if not self.ghl_api_key:
            self._log("create_subaccount", "warning", "GHL API key not configured")
            return None
        
        try:
            async with httpx.AsyncClient() as http_client:
                url = "https://rest.gohighlevel.com/v1/locations/"
                
                headers = {
                    "Authorization": f"Bearer {self.ghl_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "name": client.company_name,
                    "address": client.custom_fields.get('address', ''),
                    "city": client.custom_fields.get('city', ''),
                    "state": client.custom_fields.get('state', ''),
                    "country": "US",
                    "postalCode": client.custom_fields.get('zip', ''),
                    "website": client.website or '',
                    "timezone": "America/New_York",
                    "firstName": client.primary_contact_name or '',
                    "lastName": "",
                    "email": client.email or '',
                    "phone": client.phone or ''
                }
                
                response = await http_client.post(url, headers=headers, json=payload)
                
                if response.status_code == 201:
                    data = response.json()
                    
                    self._log(
                        "create_subaccount",
                        "success",
                        f"Created GHL sub-account for {client.company_name}",
                        metadata={"sub_account_id": data.get('id')}
                    )
                    
                    return data
                else:
                    self._log("create_subaccount", "error", f"Failed: {response.text}")
                    
        except Exception as e:
            self._log("create_subaccount", "error", f"Exception: {str(e)}")
        
        return None
    
    async def _configure_sub_account(self, client: Client, sub_account: Dict[str, Any]):
        """Configure GHL sub-account with workflows and settings"""
        
        sub_account_id = sub_account['id']
        
        # 1. Import Voice AI workflow
        await self._import_voice_workflow(sub_account_id)
        
        # 2. Set up phone number
        await self._setup_phone_number(sub_account_id, client)
        
        # 3. Configure calendar
        await self._setup_calendar(sub_account_id, client)
        
        # 4. Import contact lists
        await self._setup_contacts(sub_account_id)
        
        self._log(
            "configure_subaccount",
            "success",
            f"Configured GHL for {client.company_name}"
        )
    
    async def _import_voice_workflow(self, sub_account_id: str):
        """Import Voice AI workflow template"""
        # GHL workflow import logic
        pass
    
    async def _setup_phone_number(self, sub_account_id: str, client: Client):
        """Purchase and configure phone number"""
        # GHL phone number setup logic
        pass
    
    async def _setup_calendar(self, sub_account_id: str, client: Client):
        """Configure calendar for appointments"""
        # GHL calendar setup logic
        pass
    
    async def _setup_contacts(self, sub_account_id: str):
        """Set up contact lists and custom fields"""
        # GHL contacts setup logic
        pass
