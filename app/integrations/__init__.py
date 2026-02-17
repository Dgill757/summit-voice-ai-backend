"""External integration adapters."""

from .apollo import ApolloClient
from .enrichment import EnrichmentService
from .email import EmailService
from .sms import SMSService
from .calendar import CalendarService
from .meta import MetaMessagingService

__all__ = [
    "ApolloClient",
    "EnrichmentService",
    "EmailService",
    "SMSService",
    "CalendarService",
    "MetaMessagingService",
]

