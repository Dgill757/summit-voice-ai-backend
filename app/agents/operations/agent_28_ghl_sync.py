from __future__ import annotations

from sqlalchemy import text

from app.agents.base import BaseAgent
from app.integrations.gohighlevel import ghl_sync


class GHLSyncAgent(BaseAgent):
    """Bidirectional GoHighLevel sync agent."""

    def __init__(self, db):
        super().__init__(agent_id=28, agent_name="GoHighLevel Sync", db=db)

    async def execute(self):
        import_result = await ghl_sync.sync_from_ghl(self.db)

        unsynced = self.db.execute(
            text(
                """
                SELECT id, company_name, contact_name, email, phone, source, industry, status
                FROM prospects
                WHERE (custom_fields->>'ghl_contact_id') IS NULL
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
        ).mappings().all()

        synced = 0
        for row in unsynced:
            result = await ghl_sync.sync_prospect_to_ghl(dict(row))
            if not result.get("success"):
                continue
            ghl_id = result.get("ghl_contact_id")
            self.db.execute(
                text(
                    """
                    UPDATE prospects
                    SET custom_fields = COALESCE(custom_fields, '{}'::jsonb) || jsonb_build_object('ghl_contact_id', :ghl_id),
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": str(row["id"]), "ghl_id": ghl_id},
            )
            synced += 1

        self.db.commit()
        return {
            "success": True,
            "data": {
                "imported_from_ghl": import_result.get("contacts_imported", 0),
                "synced_to_ghl": synced,
                "cost_usd": 0,
            },
        }

