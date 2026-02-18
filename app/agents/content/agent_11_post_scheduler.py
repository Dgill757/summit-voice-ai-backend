"""
Agent 11: Post Scheduler
Schedules approved content to publish at optimal times
Integrates with social media APIs
Runs daily at 6 AM
"""
from typing import Dict, Any
from datetime import datetime, time
from app.agents.base import BaseAgent
from app.models import ContentCalendar
from app.integrations.late import LateClient

class PostSchedulerAgent(BaseAgent):
    """Schedules content publication"""
    
    def __init__(self, db):
        super().__init__(agent_id=11, agent_name="Post Scheduler", db=db)
        self.late_client = None
        try:
            self.late_client = LateClient()
        except Exception:
            self.late_client = None
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get approved content ready to schedule
        approved_content = self.db.query(ContentCalendar).filter(
            ContentCalendar.status == 'approved',
            ContentCalendar.scheduled_date == datetime.utcnow().date()
        ).all()
        
        scheduled_count = 0
        
        for content in approved_content:
            try:
                # Determine optimal posting time
                optimal_time = self._get_optimal_time(content.platform)
                
                # Update scheduled time
                content.scheduled_time = optimal_time
                content.status = 'scheduled'
                
                scheduled_count += 1
                
                self._log(
                    "schedule_post",
                    "success",
                    f"Scheduled {content.title} for {optimal_time}",
                    metadata={
                        "content_id": str(content.id),
                        "platform": content.platform
                    }
                )
                
            except Exception as e:
                self._log("schedule_post", "error", f"Failed for {content.title}: {str(e)}")
                continue
        
        self.db.commit()
        
        # Now publish scheduled posts whose time has come
        published_count = await self._publish_scheduled_posts()
        
        return {
            "success": True,
            "data": {
                "posts_scheduled": scheduled_count,
                "posts_published": published_count
            }
        }
    
    def _get_optimal_time(self, platform: str) -> time:
        """Get optimal posting time for platform"""
        
        # Best times based on engagement data
        optimal_times = {
            'linkedin': {
                'weekday': [time(9, 0), time(12, 0), time(17, 0)],  # 9am, noon, 5pm
                'weekend': [time(10, 0)]
            },
            'facebook': {
                'weekday': [time(13, 0), time(15, 0), time(19, 0)],  # 1pm, 3pm, 7pm
                'weekend': [time(12, 0), time(13, 0)]
            },
            'instagram': {
                'weekday': [time(11, 0), time(14, 0), time(19, 0)],  # 11am, 2pm, 7pm
                'weekend': [time(11, 0), time(16, 0)]
            },
            'twitter': {
                'weekday': [time(9, 0), time(12, 0), time(18, 0)],
                'weekend': [time(11, 0)]
            },
            'tiktok': {
                'weekday': [time(10, 0), time(14, 0), time(20, 0)],
                'weekend': [time(11, 0), time(17, 0)],
            }
        }
        
        # Determine if today is weekday or weekend
        today = datetime.utcnow()
        is_weekend = today.weekday() >= 5
        
        # Get times for platform
        platform_times = optimal_times.get(platform, optimal_times['linkedin'])
        times_list = platform_times['weekend'] if is_weekend else platform_times['weekday']
        
        # Return first available time
        current_time = datetime.utcnow().time()
        
        for optimal in times_list:
            if optimal > current_time:
                return optimal
        
        # If all times passed today, return first time for tomorrow
        return times_list[0]
    
    async def _publish_scheduled_posts(self) -> int:
        """Publish posts whose scheduled time has arrived"""
        published_count = 0
        
        # Get posts scheduled for now or earlier
        current_datetime = datetime.utcnow()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        
        scheduled_posts = self.db.query(ContentCalendar).filter(
            ContentCalendar.status == 'scheduled',
            ContentCalendar.scheduled_date <= current_date
        ).all()
        
        for post in scheduled_posts:
            try:
                # Check if time has come
                if post.scheduled_date < current_date or (
                    post.scheduled_date == current_date and 
                    post.scheduled_time and 
                    post.scheduled_time <= current_time
                ):
                    # Publish to platform
                    published = await self._publish_to_platform(post)
                    
                    if published:
                        post.status = 'published'
                        post.published_at = datetime.utcnow()
                        published_count += 1
                    else:
                        post.status = 'failed'
                        
            except Exception as e:
                self._log("publish_post", "error", f"Failed to publish {post.title}: {str(e)}")
                post.status = 'failed'
                continue
        
        self.db.commit()
        return published_count
    
    async def _publish_to_platform(self, content: ContentCalendar) -> bool:
        """Publish content through LATE unified API."""
        platform = (content.platform or "").lower()
        if platform not in {"linkedin", "twitter", "facebook", "instagram", "tiktok"}:
            self._log("publish", "warning", f"Platform {platform} not supported by scheduler")
            return False

        if self.late_client is None:
            self._log("publish_late", "warning", "LATE_API_KEY not configured")
            return False

        try:
            result = await self.late_client.publish(
                platform=platform,
                text=content.content_body or "",
                media_url=content.media_url,
                metadata={"content_id": str(content.id), "title": content.title},
            )
            meta = content.meta or {}
            meta["late_post_id"] = result.get("id")
            meta["late_platform"] = platform
            content.meta = meta
            self._log("publish_late", "success", f"Published {content.title} via LATE", metadata={"platform": platform, "late_post_id": result.get("id")})
            return True
        except Exception as e:
            self._log("publish_late", "error", f"Failed publishing via LATE: {str(e)}")
            return False
