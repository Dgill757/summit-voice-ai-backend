from __future__ import annotations

from app.core.logger import get_logger

logger = get_logger(__name__)


def send_notification(channel: str, message: str, metadata: dict | None = None) -> dict:
    logger.info('Notification channel=%s message=%s metadata=%s', channel, message, metadata or {})
    return {'success': True, 'channel': channel}
