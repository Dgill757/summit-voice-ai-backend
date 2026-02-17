"""
Lightweight in-process scheduler for autonomous agent execution.
Uses agent_settings.schedule_cron and updates last_run_at/next_run_at.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Set

from croniter import croniter

from app.agents.registry import get_agent_class
from app.database import SessionLocal
from app.models import AgentLog, AgentSetting

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Polls DB for due agents and executes them."""

    def __init__(self, poll_seconds: int = 30):
        self.poll_seconds = poll_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._running_agent_ids: Set[int] = set()

    def start(self) -> None:
        """Start scheduler loop as background task."""
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("AgentScheduler started")

    async def stop(self) -> None:
        """Stop scheduler loop and wait for completion."""
        self._stop_event.set()
        if self._task:
            await self._task
        logger.info("AgentScheduler stopped")

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception as exc:
                logger.exception("AgentScheduler tick failed: %s", exc)
            await asyncio.sleep(self.poll_seconds)

    async def _tick(self) -> None:
        now = datetime.utcnow()
        db = SessionLocal()
        try:
            due_agents = (
                db.query(AgentSetting)
                .filter(
                    AgentSetting.is_enabled.is_(True),
                    AgentSetting.schedule_cron.isnot(None),
                )
                .all()
            )

            for setting in due_agents:
                agent_id = setting.agent_id
                if agent_id in self._running_agent_ids:
                    continue

                should_run = setting.next_run_at is None or setting.next_run_at <= now
                if not should_run:
                    continue

                # Ensure next_run_at exists even if execution fails.
                setting.next_run_at = self._compute_next_run(setting.schedule_cron, now)
                db.commit()

                self._running_agent_ids.add(agent_id)
                asyncio.create_task(self._execute_agent(agent_id))
        finally:
            db.close()

    async def _execute_agent(self, agent_id: int) -> None:
        db = SessionLocal()
        try:
            setting = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
            if not setting or not setting.is_enabled:
                return

            agent_class = get_agent_class(agent_id)
            if agent_class is None:
                self._log_scheduler_error(
                    db=db,
                    agent_id=agent_id,
                    agent_name=setting.agent_name,
                    message=f"Agent class not registered for ID {agent_id}",
                )
                return

            agent = agent_class(db=db)
            result = await agent.run()

            setting.last_run_at = datetime.utcnow()
            setting.next_run_at = self._compute_next_run(setting.schedule_cron, setting.last_run_at)
            db.commit()

            logger.info(
                "Scheduled run complete for agent %s (%s): success=%s",
                agent_id,
                setting.agent_name,
                result.get("success"),
            )
        except Exception as exc:
            db.rollback()
            try:
                setting = db.query(AgentSetting).filter(AgentSetting.agent_id == agent_id).first()
                if setting:
                    self._log_scheduler_error(
                        db=db,
                        agent_id=agent_id,
                        agent_name=setting.agent_name,
                        message=f"Scheduled execution failed: {exc}",
                    )
            except Exception:
                pass
            logger.exception("Scheduled execution failed for agent %s: %s", agent_id, exc)
        finally:
            self._running_agent_ids.discard(agent_id)
            db.close()

    @staticmethod
    def _compute_next_run(schedule_cron: str | None, from_dt: datetime) -> datetime | None:
        if not schedule_cron:
            return None
        try:
            return croniter(schedule_cron, from_dt).get_next(datetime)
        except Exception:
            return None

    @staticmethod
    def _log_scheduler_error(db, agent_id: int, agent_name: str, message: str) -> None:
        log = AgentLog(
            agent_id=agent_id,
            agent_name=agent_name,
            action="scheduler_execute",
            status="error",
            message=message,
        )
        db.add(log)
        db.commit()

