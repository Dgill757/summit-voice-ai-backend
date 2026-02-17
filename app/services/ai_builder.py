from __future__ import annotations

import ast
import importlib.util
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.anthropic_client import get_anthropic_client
from app.core.exceptions import BuilderDeploymentError

AGENT_GENERATION_PROMPT = """
You are an AI agent code generator for the Summit Voice AI platform.

User wants: {user_description}

Generate production-ready Python code following this pattern:
- Inherit from app.agents.base.BaseAgent
- Constructor signature: __init__(self, db)
- Implement async execute(self) -> dict
- Use self._log for operational logs
- Return a structured dict with success and data keys

REQUIREMENTS:
1. Inherit from BaseAgent
2. Implement async execute() method
3. Use type hints everywhere
4. Add comprehensive error handling
5. Add concise docstrings
6. Return Dict[str, Any] from execute

OUTPUT FORMAT:
Return ONLY valid Python code, no markdown.
"""

FALLBACK_TEMPLATE = """\
from typing import Dict, Any
from app.agents.base import BaseAgent


class GeneratedAgent(BaseAgent):
    \"\"\"Auto-generated placeholder agent.\"\"\"

    def __init__(self, db):
        super().__init__(agent_id=999, agent_name=\"Generated Agent\", db=db)

    async def execute(self) -> Dict[str, Any]:
        self._log(\"execute\", \"info\", \"Generated agent executed\")
        return {\"success\": True, \"data\": {\"message\": \"Generated agent executed\"}}
"""


class AIBuilderService:
    def __init__(self) -> None:
        self.client = get_anthropic_client()
        self.base_dir = Path(__file__).resolve().parents[1] / 'agents' / 'custom'
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def generate_agent_code(self, description: str) -> dict[str, Any]:
        prompt = AGENT_GENERATION_PROMPT.format(user_description=description)
        try:
            message = await self.client.messages.create(
                model='claude-3-5-sonnet-latest',
                max_tokens=3000,
                messages=[{'role': 'user', 'content': prompt}],
            )
            generated = message.content[0].text.strip()
            code = self._sanitize_code(generated)
        except Exception:
            code = FALLBACK_TEMPLATE

        filename = self._build_filename(description)
        return {
            'code': code,
            'filename': filename,
            'suggested_config': self._suggest_config(description),
        }

    def deploy_agent_code(self, filename: str, code: str, config: dict | None = None) -> dict[str, Any]:
        validation_errors = self._validate_code(code)
        if validation_errors:
            return {
                'success': False,
                'filepath': '',
                'module': '',
                'validation_errors': validation_errors,
            }

        filepath = self.base_dir / filename
        filepath.write_text(code, encoding='utf-8')

        module_name = f'app.agents.custom.{filepath.stem}'
        self._validate_import(filepath, module_name)

        # Persisting config per generated agent can be added to a dedicated table.
        _ = config or {}

        return {
            'success': True,
            'filepath': str(filepath),
            'module': module_name,
            'validation_errors': [],
        }

    def _build_filename(self, description: str) -> str:
        slug = re.sub(r'[^a-z0-9]+', '_', description.lower()).strip('_')
        slug = slug[:40] if slug else 'generated_agent'
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f'{slug}_{ts}.py'

    def _suggest_config(self, description: str) -> dict[str, Any]:
        lower = description.lower()
        cron = '0 9 * * *'
        if 'every hour' in lower or 'hourly' in lower:
            cron = '0 * * * *'
        elif 'every 15' in lower:
            cron = '*/15 * * * *'
        elif 'weekly' in lower:
            cron = '0 9 * * 1'
        return {
            'schedule_cron': cron,
            'max_retries': 3,
            'timeout_seconds': 60,
        }

    def _sanitize_code(self, generated: str) -> str:
        # Strip markdown fences if model emits them.
        cleaned = generated.replace('```python', '').replace('```', '').strip()
        return cleaned or FALLBACK_TEMPLATE

    def _validate_code(self, code: str) -> list[str]:
        errors: list[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return [f'SyntaxError: {exc}']

        class_defs = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        if not class_defs:
            errors.append('Code must define at least one class.')
        has_async_execute = False
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == 'execute':
                has_async_execute = True
                break
        if not has_async_execute:
            errors.append('Code must include async execute method.')
        if 'BaseAgent' not in code:
            errors.append('Code must reference BaseAgent.')
        return errors

    def _validate_import(self, filepath: Path, module_name: str) -> None:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            raise BuilderDeploymentError('Unable to load generated module spec.')
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise BuilderDeploymentError(f'Generated module import failed: {exc}') from exc
