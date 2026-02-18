from __future__ import annotations

import os

import httpx

OUTREACH_SYSTEM_PROMPT = """
You are a direct-response copywriter trained on Hormozi-style outreach.

Rules:
- Max 4 sentences.
- Sentence 1: sharp hook with specific business problem.
- Sentence 2: proof with numbers.
- Sentence 3: concrete offer.
- Sentence 4: direct CTA.
- No fluff, no corporate jargon, no AI-sounding language.
- Plain text only.

Prospect:
Name: {name}
Company: {company}
City: {city}
State: {state}
Title: {title}
"""


async def generate_hormozi_style_email(prospect: dict) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_email(prospect)

    prompt = OUTREACH_SYSTEM_PROMPT.format(
        name=((prospect.get("contact_name") or prospect.get("name") or "").split(" ")[0] or "there"),
        company=prospect.get("company_name") or prospect.get("company") or "your company",
        city=prospect.get("city") or "your market",
        state=prospect.get("state") or "",
        title=prospect.get("title") or "Owner",
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "X-API-Key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 260,
                    "temperature": 0.7,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            body = response.json()
            text = body["content"][0]["text"].strip()
            return text.strip('"').strip("'")
    except Exception:
        return _fallback_email(prospect)


def _fallback_email(prospect: dict) -> str:
    first = ((prospect.get("contact_name") or prospect.get("name") or "").split(" ")[0] or "there")
    company = prospect.get("company_name") or prospect.get("company") or "your team"
    city = prospect.get("city") or "your market"
    return (
        f"{first}, most roofing shops in {city} lose deals because calls get missed when crews are in the field.\n\n"
        "Our AI voice stack books qualified jobs 24/7, and clients are averaging 30+ appointments per month.\n\n"
        f"We can set this up for {company} with a 30-appointment guarantee.\n\n"
        "Reply with \"demo\" and I will send a 12-minute walkthrough."
    )

