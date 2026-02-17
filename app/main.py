"""
Summit Voice AI - FastAPI Application
Complete backend API for the $20M agency operating system
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Import database
from app.database import init_db, get_db
from app.config import settings
from app.services.agent_scheduler import AgentScheduler
from app.core.security import get_current_user
from app.api import websocket

# Import ALL route modules
from app.api.routes import (
    health,
    auth,
    agents,
    prospects,
    clients,
    content,
    analytics,
    meetings,
    outreach,
    builder,
)
from app.api.v1 import workflows, executions, leads, metrics, users, subscriptions, dashboard as dashboard_v1, ai_builder, content_approval, costs

logger = logging.getLogger(__name__)
scheduler = AgentScheduler(poll_seconds=30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Starting Summit Voice AI API...")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")

    logger.info("All 26 agents loaded and ready")
    logger.info(f"API running on {settings.app_env} environment")
    scheduler.start()
    app.state.agent_scheduler = scheduler
    logger.info("Agent scheduler started")
    logger.info("=" * 50)
    yield
    # Shutdown
    await scheduler.stop()
    logger.info("Shutting down Summit Voice AI API...")


app = FastAPI(
    title=settings.app_name,
    description="Backend API for Summit Voice AI",
    version="1.0.0",
    lifespan=lifespan,
)

# Respect Railway/Proxy forwarded proto/host so redirects don't downgrade to http.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Include ALL routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(
    agents.router, prefix="/api/v1/agents", tags=["Agents"]
)
app.include_router(
    prospects.router, prefix="/api/v1/prospects", tags=["Prospects"]
)
app.include_router(
    clients.router, prefix="/api/v1/clients", tags=["Clients"]
)
app.include_router(
    content.router, prefix="/api/v1/content", tags=["Content"]
)
app.include_router(
    analytics.router, prefix="/api/v1/analytics", tags=["Analytics"]
)
app.include_router(
    meetings.router, prefix="/api/v1/meetings", tags=["Meetings"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    outreach.router, prefix="/api/v1/outreach", tags=["Outreach"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    builder.router, prefix="/api/v1/builder", tags=["Builder"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    workflows.router, prefix="/api/v1/workflows", tags=["Workflows"]
)
app.include_router(
    executions.router, prefix="/api/v1/executions", tags=["Executions"]
)
app.include_router(
    leads.router, prefix="/api/v1/leads", tags=["Leads"]
)
app.include_router(
    metrics.router, prefix="/api/v1/metrics", tags=["Metrics"]
)
app.include_router(
    users.router, prefix="/api/v1/users", tags=["Users"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    subscriptions.router,
    prefix="/api/v1/subscriptions",
    tags=["Subscriptions"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    dashboard_v1.router,
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)
app.include_router(
    ai_builder.router,
    prefix="/api/v1/ai-builder",
    tags=["AI Builder"],
)
app.include_router(
    costs.router,
    prefix="/api/v1/costs",
    tags=["Costs"],
)
app.include_router(
    content_approval.router,
    prefix="/api/v1/content-approval",
    tags=["Content Approval"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(websocket.router, tags=["WebSocket"])
