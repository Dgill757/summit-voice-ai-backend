from app.services.ai_builder import AIBuilderService


def test_validate_code_accepts_base_agent_pattern():
    service = AIBuilderService()
    code = '''
from typing import Dict, Any
from app.agents.base import BaseAgent

class XAgent(BaseAgent):
    def __init__(self, db):
        super().__init__(agent_id=999, agent_name="X", db=db)

    async def execute(self) -> Dict[str, Any]:
        return {"success": True, "data": {}}
'''
    errors = service._validate_code(code)
    assert errors == []


def test_validate_code_rejects_missing_execute():
    service = AIBuilderService()
    code = 'class Bad: pass'
    errors = service._validate_code(code)
    assert errors
