from sqlalchemy import text

from app.database import SessionLocal


def main():
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                UPDATE agent_settings
                SET is_enabled = true
                WHERE agent_name IN ('Lead Scraper', 'Lead Enricher', 'Outreach Sender', 'Meeting Scheduler', 'Cost Monitor')
                """
            )
        )
        db.execute(
            text(
                """
                UPDATE agent_settings
                SET is_enabled = false
                WHERE agent_name NOT IN ('Lead Scraper', 'Lead Enricher', 'Outreach Sender', 'Meeting Scheduler', 'Cost Monitor')
                """
            )
        )
        db.commit()
        print("Revenue sprint activation complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

