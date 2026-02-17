"""
Agent 11: Post Scheduler
Schedules approved content to publish at optimal times
Integrates with social media APIs
Runs daily at 6 AM
"""
from typing import Dict, Any
import os
from datetime import datetime, time
import httpx
from app.agents.base import BaseAgent
from app.models import ContentCalendar

class PostSchedulerAgent(BaseAgent):
    """Schedules content publication"""
    
    def __init__(self, db):
        super().__init__(agent_id=11, agent_name="Post Scheduler", db=db)
        
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
        """Publish content to social media platform"""
        
        platform = content.platform
        
        # Platform-specific publishing
        if platform == 'linkedin':
            return await self._publish_to_linkedin(content)
        elif platform == 'facebook':
            return await self._publish_to_facebook(content)
        elif platform == 'instagram':
            return await self._publish_to_instagram(content)
        elif platform == 'twitter':
            return await self._publish_to_twitter(content)
        else:
            self._log("publish", "warning", f"Platform {platform} not yet implemented")
            return False
    
    async def _publish_to_linkedin(self, content: ContentCalendar) -> bool:
        """Publish to LinkedIn"""
        
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        person_urn = os.getenv("LINKEDIN_PERSON_URN")
        
        if not access_token or not person_urn:
            self._log("publish_linkedin", "warning", "LinkedIn credentials not configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.linkedin.com/v2/ugcPosts"
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
                
                payload = {
                    "author": person_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {
                                "text": content.content_body
                            },
                            "shareMediaCategory": "NONE"
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    }
                }
                
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 201:
                    self._log("publish_linkedin", "success", f"Published: {content.title}")
                    return True
                else:
                    self._log("publish_linkedin", "error", f"Failed: {response.text}")
                    return False
                    
        except Exception as e:
            self._log("publish_linkedin", "error", f"Exception: {str(e)}")
            return False
    
    async def _publish_to_facebook(self, content: ContentCalendar) -> bool:
        """Publish to Facebook"""
        # Similar implementation for Facebook Graph API
        self._log("publish_facebook", "info", "Facebook publishing not yet implemented")
        return False
    
    async def _publish_to_instagram(self, content: ContentCalendar) -> bool:
        """Publish to Instagram"""
        # Similar implementation for Instagram Graph API
        self._log("publish_instagram", "info", "Instagram publishing not yet implemented")
        return False
    
    async def _publish_to_twitter(self, content: ContentCalendar) -> bool:
        """Publish to Twitter"""
        # Similar implementation for Twitter API v2
        self._log("publish_twitter", "info", "Twitter publishing not yet implemented")
        return False
