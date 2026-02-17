from __future__ import annotations

from app.agents.registry import get_agent_class
from app.database import SessionLocal


async def execute_agent(agent_id: int) -> dict:
    db = SessionLocal()
    try:
        cls = get_agent_class(agent_id)
        if cls is None:
            return {'success': False, 'error': f'Agent {agent_id} not registered'}
        agent = cls(db=db)
        return await agent.run()
    finally:
        db.close()
