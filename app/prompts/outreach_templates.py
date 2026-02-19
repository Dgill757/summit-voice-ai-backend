import logging
import random

logger = logging.getLogger(__name__)

TEMPLATE_DIRECT = """
{name}, the roofing businesses we work with said they were missing 3-8 calls a day.

We built them AI voice systems that add 50-100K a month in revenue for {company}.

Worth a look?
"""

TEMPLATE_SOFT = """
{name}, I'm not sure if you're adopting AI yet or not but I built {company} a system tailored to your business that's adding 50-100K a month in new revenue.

Worth a look? If not no worries I can scrap it but figured I would reach out.
"""

TEMPLATE_PROBLEM_AGITATE = """
{name}, most {city} roofers lose 40-60% of leads to missed calls.

We built {company} an AI that answers 24/7 and books appointments automatically - clients add 50-100K/month.

Reply YES for a 5-min demo.
"""

TEMPLATE_SOCIAL_PROOF = """
{name}, we helped 6 roofing companies in {state} go from missing half their calls to capturing every lead 24/7.

Average result: 50-100K/month increase in {city}.

Want to see how it works for {company}?
"""


async def generate_outreach_email(prospect: dict) -> dict:
    """Generate outreach email using fixed brand-safe templates (no LLM)."""
    name_raw = prospect.get("name") or prospect.get("contact_name") or ""
    name = name_raw.split()[0] if name_raw else "there"
    company = prospect.get("company") or prospect.get("company_name") or "your business"
    city = prospect.get("city") or "your area"
    state = prospect.get("state") or "your state"

    templates = [
        ("Direct", TEMPLATE_DIRECT),
        ("Soft", TEMPLATE_SOFT),
        ("Problem-Agitate", TEMPLATE_PROBLEM_AGITATE),
        ("Social Proof", TEMPLATE_SOCIAL_PROOF),
    ]
    template_name, template = random.choice(templates)
    body = template.format(name=name, company=company, city=city, state=state).strip()

    subjects = [
        f"{name}, 50K/month in missed revenue?",
        f"{name} - missing calls at {company}?",
        f"Quick question for {company}",
        f"{name}, built you something",
    ]
    subject = random.choice(subjects)

    logger.info("Generated %s outreach email for %s at %s", template_name, name, company)
    return {"subject": subject, "body": body, "template_used": template_name}
