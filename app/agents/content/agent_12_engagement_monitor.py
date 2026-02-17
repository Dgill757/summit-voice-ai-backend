"""
Agent 12: Engagement Monitor
Monitors and tracks engagement on published content
Collects likes, comments, shares, clicks
Runs every 30 minutes
"""
from typing import Dict, Any, List
import os
from datetime import datetime, timedelta
import httpx
from app.agents.base import BaseAgent
from app.models import ContentCalendar, Engagement

class EngagementMonitorAgent(BaseAgent):
    """Monitors social media engagement"""
    
    def __init__(self, db):
        super().__init__(agent_id=12, agent_name="Engagement Monitor", db=db)
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get published content from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        published_content = self.db.query(ContentCalendar).filter(
            ContentCalendar.status == 'published',
            ContentCalendar.published_at >= thirty_days_ago
        ).all()
        
        total_engagements = 0
        
        for content in published_content:
            try:
                # Fetch engagement data from platform
                engagement_data = await self._fetch_engagement(content)
                
                if engagement_data:
                    # Save new engagements
                    new_engagements = await self._save_engagements(content, engagement_data)
                    total_engagements += new_engagements
                    
            except Exception as e:
                self._log("monitor_engagement", "error", f"Failed for {content.title}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "content_monitored": len(published_content),
                "new_engagements": total_engagements
            }
        }
    
    async def _fetch_engagement(self, content: ContentCalendar) -> Dict[str, Any]:
        """Fetch engagement data from social platform"""
        
        platform = content.platform
        
        if platform == 'linkedin':
            return await self._fetch_linkedin_engagement(content)
        elif platform == 'facebook':
            return await self._fetch_facebook_engagement(content)
        elif platform == 'instagram':
            return await self._fetch_instagram_engagement(content)
        else:
            return None
    
    async def _fetch_linkedin_engagement(self, content: ContentCalendar) -> Dict[str, Any]:
        """Fetch LinkedIn post engagement"""
        
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        
        if not access_token:
            return None
        
        try:
            # Extract post ID from metadata (stored during publishing)
            post_id = content.meta.get('linkedin_post_id') if hasattr(content, 'meta') else None
            
            if not post_id:
                return None
            
            async with httpx.AsyncClient() as client:
                # Get post statistics
                url = f"https://api.linkedin.com/v2/socialActions/{post_id}"
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    return {
                        "likes": data.get('likesSummary', {}).get('totalLikes', 0),
                        "comments": data.get('commentsSummary', {}).get('totalComments', 0),
                        "shares": data.get('sharesSummary', {}).get('totalShares', 0),
                        "views": data.get('impressionsSummary', {}).get('totalImpressions', 0)
                    }
                    
        except Exception as e:
            self._log("fetch_linkedin", "warning", f"Failed: {str(e)}")
        
        return None
    
    async def _fetch_facebook_engagement(self, content: ContentCalendar) -> Dict[str, Any]:
        """Fetch Facebook post engagement"""
        
        access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        
        if not access_token:
            return None
        
        try:
            post_id = content.meta.get('facebook_post_id') if hasattr(content, 'meta') else None
            
            if not post_id:
                return None
            
            async with httpx.AsyncClient() as client:
                url = f"https://graph.facebook.com/v18.0/{post_id}"
                
                params = {
                    "fields": "likes.summary(true),comments.summary(true),shares",
                    "access_token": access_token
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    return {
                        "likes": data.get('likes', {}).get('summary', {}).get('total_count', 0),
                        "comments": data.get('comments', {}).get('summary', {}).get('total_count', 0),
                        "shares": data.get('shares', {}).get('count', 0)
                    }
                    
        except Exception as e:
            self._log("fetch_facebook", "warning", f"Failed: {str(e)}")
        
        return None
    
    async def _fetch_instagram_engagement(self, content: ContentCalendar) -> Dict[str, Any]:
        """Fetch Instagram post engagement"""
        
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        
        if not access_token:
            return None
        
        try:
            media_id = content.meta.get('instagram_media_id') if hasattr(content, 'meta') else None
            
            if not media_id:
                return None
            
            async with httpx.AsyncClient() as client:
                url = f"https://graph.instagram.com/{media_id}"
                
                params = {
                    "fields": "like_count,comments_count,saved_count,impressions,reach",
                    "access_token": access_token
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    return {
                        "likes": data.get('like_count', 0),
                        "comments": data.get('comments_count', 0),
                        "saves": data.get('saved_count', 0),
                        "views": data.get('impressions', 0)
                    }
                    
        except Exception as e:
            self._log("fetch_instagram", "warning", f"Failed: {str(e)}")
        
        return None
    
    async def _save_engagements(self, content: ContentCalendar, engagement_data: Dict[str, Any]) -> int:
        """Save engagement records to database"""
        
        saved_count = 0
        
        # Save each type of engagement
        for engagement_type, count in engagement_data.items():
            try:
                # Check if we already have this engagement recorded
                existing = self.db.query(Engagement).filter(
                    Engagement.content_id == content.id,
                    Engagement.engagement_type == engagement_type
                ).first()
                
                if existing:
                    # Update count if changed
                    if count > 0:
                        existing.engagement_datetime = datetime.utcnow()
                        existing.user_info = {"count": count}
                else:
                    # Create new engagement record
                    if count > 0:
                        engagement = Engagement(
                            content_id=content.id,
                            platform=content.platform,
                            engagement_type=engagement_type,
                            engagement_datetime=datetime.utcnow(),
                            user_info={"count": count}
                        )
                        
                        self.db.add(engagement)
                        saved_count += 1
                        
            except Exception as e:
                self._log("save_engagement", "warning", f"Failed to save {engagement_type}: {str(e)}")
                continue
        
        self.db.commit()
        return saved_count
