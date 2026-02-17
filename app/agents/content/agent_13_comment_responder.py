"""
Agent 13: Comment Responder
Monitors comments on posts and generates intelligent responses
Uses Claude AI for natural, helpful replies
Runs every 20 minutes
"""
from typing import Dict, Any, List, Optional
import os
from datetime import datetime, timedelta
import httpx
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import ContentCalendar, Engagement

class CommentResponderAgent(BaseAgent):
    """Responds to comments on social media"""
    
    def __init__(self, db):
        super().__init__(agent_id=13, agent_name="Comment Responder", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get recent published content (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        recent_posts = self.db.query(ContentCalendar).filter(
            ContentCalendar.status == 'published',
            ContentCalendar.published_at >= week_ago
        ).all()
        
        responses_sent = 0
        
        for post in recent_posts:
            try:
                # Fetch new comments
                comments = await self._fetch_comments(post)
                
                # Respond to each comment
                for comment in comments:
                    if await self._should_respond(comment):
                        response = await self._generate_response(post, comment)
                        
                        if response:
                            sent = await self._send_response(post, comment, response)
                            
                            if sent:
                                responses_sent += 1
                                
            except Exception as e:
                self._log("respond_comments", "error", f"Failed for {post.title}: {str(e)}")
                continue
        
        return {
            "success": True,
            "data": {
                "posts_checked": len(recent_posts),
                "responses_sent": responses_sent
            }
        }
    
    async def _fetch_comments(self, content: ContentCalendar) -> List[Dict[str, Any]]:
        """Fetch comments from social platform"""
        
        platform = content.platform
        
        if platform == 'linkedin':
            return await self._fetch_linkedin_comments(content)
        elif platform == 'facebook':
            return await self._fetch_facebook_comments(content)
        elif platform == 'instagram':
            return await self._fetch_instagram_comments(content)
        else:
            return []
    
    async def _fetch_linkedin_comments(self, content: ContentCalendar) -> List[Dict[str, Any]]:
        """Fetch LinkedIn comments"""
        
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        
        if not access_token:
            return []
        
        comments = []
        
        try:
            post_id = content.meta.get('linkedin_post_id') if hasattr(content, 'meta') else None
            
            if not post_id:
                return []
            
            async with httpx.AsyncClient() as client:
                url = f"https://api.linkedin.com/v2/socialActions/{post_id}/comments"
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for comment in data.get('elements', []):
                        comments.append({
                            "id": comment.get('id'),
                            "author": comment.get('actor', ''),
                            "text": comment.get('message', {}).get('text', ''),
                            "created_at": comment.get('created', {}).get('time', 0),
                            "platform": "linkedin"
                        })
                        
        except Exception as e:
            self._log("fetch_linkedin_comments", "warning", f"Failed: {str(e)}")
        
        return comments
    
    async def _fetch_facebook_comments(self, content: ContentCalendar) -> List[Dict[str, Any]]:
        """Fetch Facebook comments"""
        
        access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        
        if not access_token:
            return []
        
        comments = []
        
        try:
            post_id = content.meta.get('facebook_post_id') if hasattr(content, 'meta') else None
            
            if not post_id:
                return []
            
            async with httpx.AsyncClient() as client:
                url = f"https://graph.facebook.com/v18.0/{post_id}/comments"
                
                params = {
                    "access_token": access_token,
                    "fields": "id,from,message,created_time"
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for comment in data.get('data', []):
                        comments.append({
                            "id": comment.get('id'),
                            "author": comment.get('from', {}).get('name', ''),
                            "text": comment.get('message', ''),
                            "created_at": comment.get('created_time'),
                            "platform": "facebook"
                        })
                        
        except Exception as e:
            self._log("fetch_facebook_comments", "warning", f"Failed: {str(e)}")
        
        return comments
    
    async def _fetch_instagram_comments(self, content: ContentCalendar) -> List[Dict[str, Any]]:
        """Fetch Instagram comments"""
        
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        
        if not access_token:
            return []
        
        comments = []
        
        try:
            media_id = content.meta.get('instagram_media_id') if hasattr(content, 'meta') else None
            
            if not media_id:
                return []
            
            async with httpx.AsyncClient() as client:
                url = f"https://graph.instagram.com/{media_id}/comments"
                
                params = {
                    "access_token": access_token,
                    "fields": "id,username,text,timestamp"
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for comment in data.get('data', []):
                        comments.append({
                            "id": comment.get('id'),
                            "author": comment.get('username', ''),
                            "text": comment.get('text', ''),
                            "created_at": comment.get('timestamp'),
                            "platform": "instagram"
                        })
                        
        except Exception as e:
            self._log("fetch_instagram_comments", "warning", f"Failed: {str(e)}")
        
        return comments
    
    async def _should_respond(self, comment: Dict[str, Any]) -> bool:
        """Determine if we should respond to this comment"""
        
        # Check if we've already responded
        existing = self.db.query(Engagement).filter(
            Engagement.user_info['comment_id'].astext == comment['id'],
            Engagement.engagement_type == 'comment_reply'
        ).first()
        
        if existing:
            return False
        
        # Don't respond to very old comments (>24 hours)
        comment_time = comment.get('created_at')
        if comment_time:
            # Parse timestamp based on platform
            # This is simplified - you'd need proper parsing
            try:
                if isinstance(comment_time, int):
                    comment_dt = datetime.fromtimestamp(comment_time / 1000)
                else:
                    comment_dt = datetime.fromisoformat(comment_time.replace('Z', '+00:00'))
                
                if (datetime.utcnow() - comment_dt).days > 1:
                    return False
            except:
                pass
        
        # Respond to questions, mentions, or meaningful comments
        text = comment.get('text', '').lower()
        
        if any(word in text for word in ['?', 'how', 'what', 'when', 'where', 'why', 'interested', 'more info']):
            return True
        
        # Respond to longer comments (shows engagement)
        if len(text.split()) > 10:
            return True
        
        return False
    
    async def _generate_response(self, post: ContentCalendar, comment: Dict[str, Any]) -> Optional[str]:
        """Generate intelligent response using Claude"""
        
        prompt = f"""You're Dan from Summit Voice AI. Someone commented on your {post.platform} post.

Original Post: {post.content_body[:500]}...

Comment from {comment['author']}: "{comment['text']}"

Write a natural, helpful reply that:
1. Thanks them for engaging
2. Directly answers their question (if there is one)
3. Provides value or additional insight
4. Invites further conversation
5. Sounds human (not robotic or salesy)
6. Is brief (2-3 sentences max)

If they seem interested in Voice AI, mention you'd be happy to share more details.

Return ONLY the reply text (no quotes, no formatting):"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text.strip()
            
        except Exception as e:
            self._log("generate_response", "error", f"Claude failed: {str(e)}")
            
            # Fallback to simple response
            return f"Thanks for the comment, {comment['author']}! Great question. Feel free to DM me if you'd like to discuss further!"
    
    async def _send_response(self, post: ContentCalendar, comment: Dict[str, Any], response: str) -> bool:
        """Send response to comment"""
        
        platform = comment['platform']
        
        try:
            if platform == 'linkedin':
                sent = await self._reply_linkedin(post, comment, response)
            elif platform == 'facebook':
                sent = await self._reply_facebook(post, comment, response)
            elif platform == 'instagram':
                sent = await self._reply_instagram(post, comment, response)
            else:
                return False
            
            if sent:
                # Record that we responded
                engagement = Engagement(
                    content_id=post.id,
                    platform=platform,
                    engagement_type='comment_reply',
                    user_info={
                        "comment_id": comment['id'],
                        "author": comment['author'],
                        "response": response
                    }
                )
                
                self.db.add(engagement)
                self.db.commit()
                
                self._log(
                    "send_response",
                    "success",
                    f"Replied to {comment['author']} on {platform}",
                    metadata={"comment_id": comment['id']}
                )
            
            return sent
            
        except Exception as e:
            self._log("send_response", "error", f"Failed: {str(e)}")
            return False
    
    async def _reply_linkedin(self, post: ContentCalendar, comment: Dict[str, Any], response: str) -> bool:
        """Reply to LinkedIn comment"""
        
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        
        if not access_token:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.linkedin.com/v2/socialActions/{postId}/comments"
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
                
                payload = {
                    "message": {
                        "text": response
                    }
                }
                
                http_response = await client.post(url, headers=headers, json=payload)
                
                return http_response.status_code == 201
                
        except Exception as e:
            self._log("reply_linkedin", "error", f"Failed: {str(e)}")
            return False
    
    async def _reply_facebook(self, post: ContentCalendar, comment: Dict[str, Any], response: str) -> bool:
        """Reply to Facebook comment"""
        # Facebook Graph API implementation
        self._log("reply_facebook", "info", "Facebook replies not yet implemented")
        return False
    
    async def _reply_instagram(self, post: ContentCalendar, comment: Dict[str, Any], response: str) -> bool:
        """Reply to Instagram comment"""
        # Instagram Graph API implementation
        self._log("reply_instagram", "info", "Instagram replies not yet implemented")
        return False
