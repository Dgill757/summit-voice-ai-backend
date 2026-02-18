from __future__ import annotations

import pytest

from app.services.n8n_parser import N8NWorkflowParser

SAMPLE_N8N_WORKFLOW = {
    "name": "Test Lead Scraper",
    "nodes": [
        {
            "name": "Apollo API",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "url": "https://api.apollo.io/v1/mixed_people/search",
                "method": "POST",
                "nodeCredentialType": "apolloApi",
            },
        },
        {
            "name": "Transform",
            "type": "n8n-nodes-base.code",
            "parameters": {"language": "javascript", "jsCode": "return items;"},
        },
    ],
    "connections": {
        "Apollo API": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]}
    },
}


@pytest.mark.asyncio
async def test_n8n_parse():
    parser = N8NWorkflowParser()
    parsed = await parser.parse_workflow(SAMPLE_N8N_WORKFLOW)
    assert parsed["workflow_name"] == "Test Lead Scraper"
    assert len(parsed["required_apis"]) > 0
    assert parsed["required_apis"][0]["env_var"] == "APOLLO_API_KEY"
    assert parsed["execution_order"] == ["Apollo API", "Transform"]


@pytest.mark.asyncio
async def test_n8n_convert_fallback(monkeypatch):
    parser = N8NWorkflowParser()
    monkeypatch.setattr(parser, "anthropic_key", None)
    parsed = await parser.parse_workflow(SAMPLE_N8N_WORKFLOW)
    python_code = await parser.convert_to_python_agent(parsed, {})
    assert "async def execute(config: dict):" in python_code
    assert "httpx" in python_code
    assert "apollo" in python_code.lower()

