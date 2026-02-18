from __future__ import annotations

import os


def integration_status() -> dict:
    keys = {
        'anthropic': bool(os.getenv('ANTHROPIC_API_KEY')),
        'apollo': bool(os.getenv('APOLLO_API_KEY')),
        'hunter': bool(os.getenv('HUNTER_API_KEY')),
        'clearbit': bool(os.getenv('CLEARBIT_API_KEY')),
        'twilio': bool(os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN')),
        'stripe': bool(os.getenv('STRIPE_SECRET_KEY')),
        'google_calendar': bool(
            os.getenv('GOOGLE_CALENDAR_CLIENT_ID')
            and os.getenv('GOOGLE_CALENDAR_CLIENT_SECRET')
        ),
        'gohighlevel': bool(os.getenv('GOHIGHLEVEL_API_KEY') and os.getenv('GOHIGHLEVEL_LOCATION_ID')),
        'late': bool(os.getenv('LATE_API_KEY')),
    }
    return {'integrations': keys}
