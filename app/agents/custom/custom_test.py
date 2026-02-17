from app.agents.base import BaseAgent
class CustomTestAgent(BaseAgent):
    def __init__(self, db):
        super().__init__(agent_id=999, agent_name="Custom Test", db=db)
    async def execute(self):
        return {"success":True, "data":{}}
