import re
from pathlib import Path


def find_env_vars():
    """Find all environment variables referenced in code."""
    env_vars = set()
    for py_file in Path("app").rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        env_vars.update(re.findall(r'os\.getenv\(["\']([A-Z0-9_]+)["\']', content))
        env_vars.update(re.findall(r'os\.environ\[\s*["\']([A-Z0-9_]+)["\']\s*\]', content))
    return sorted(env_vars)


def verify_against_railway():
    railway_vars = [
        "ADMIN_EMAIL", "ADMIN_NAME", "ADMIN_PASSWORD_HASH",
        "ANTHROPIC_API_KEY", "API_V1_PREFIX", "APOLLO_API_KEY",
        "APP_DEBUG", "APP_ENV", "APP_NAME", "CORS_ORIGINS",
        "DATABASE_URL", "DID_API_KEY", "GOHIGHLEVEL_API_KEY",
        "GOHIGHLEVEL_LOCATION_ID", "GOOGLE_AI_API_KEY",
        "GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET",
        "GOOGLE_CALENDAR_REFRESH_TOKEN", "GOOGLE_MAPS_API_KEY",
        "HEYGEN_API_KEY", "HUNTER_API_KEY", "LATE_API_KEY",
        "OPENAI_API_KEY", "PORT", "POSTHOG_API_KEY",
        "ROCKETREACH_API_KEY", "SECRET_KEY", "SENDGRID_API_KEY",
        "SHOTSTACK_API_KEY", "STABILITY_AI_API_KEY", "STABILITY_API_KEY",
        "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY", "SUPABASE_URL",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
    ]

    code_vars = set(find_env_vars())
    railway_set = set(railway_vars)
    missing_in_railway = sorted(code_vars - railway_set)
    unused_in_code = sorted(railway_set - code_vars)

    print("=== ENV VAR VERIFICATION ===")
    print(f"Code references: {len(code_vars)} unique vars")
    print(f"Railway list has: {len(railway_vars)} vars")
    print("")
    if missing_in_railway:
        print(f"MISSING IN RAILWAY ({len(missing_in_railway)}):")
        for v in missing_in_railway:
            print(f"  - {v}")
    else:
        print("No missing vars against Railway list.")
    print("")
    if unused_in_code:
        print(f"UNUSED IN CODE ({len(unused_in_code)}):")
        for v in unused_in_code:
            print(f"  - {v}")
    else:
        print("No unused Railway vars.")


if __name__ == "__main__":
    verify_against_railway()

