"""
Agent 8: Content Idea Generator
Generates weekly content ideas using Claude AI
Target: 21 ideas per week (3 per day)
Runs weekly on Monday at 7 AM
"""
from typing import Dict, Any, List
import os
from datetime import datetime, timedelta
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import ContentCalendar

class ContentIdeaGeneratorAgent(BaseAgent):
    """Generates content ideas for social media"""
    
    def __init__(self, db):
        super().__init__(agent_id=8, agent_name="Content Idea Generator", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get target ideas from config
        ideas_per_week = self.config.get('ideas_per_week', 21)
        
        # Generate ideas for each platform
        linkedin_ideas = await self._generate_platform_ideas('linkedin', ideas_per_week // 3)
        facebook_ideas = await self._generate_platform_ideas('facebook', ideas_per_week // 3)
        instagram_ideas = await self._generate_platform_ideas('instagram', ideas_per_week // 3)
        
        all_ideas = linkedin_ideas + facebook_ideas + instagram_ideas
        
        # Save to content calendar
        saved_count = await self._save_ideas(all_ideas)
        
        return {
            "success": True,
            "data": {
                "ideas_generated": len(all_ideas),
                "ideas_saved": saved_count,
                "by_platform": {
                    "linkedin": len(linkedin_ideas),
                    "facebook": len(facebook_ideas),
                    "instagram": len(instagram_ideas)
                }
            }
        }
    
    async def _generate_platform_ideas(self, platform: str, count: int) -> List[Dict[str, Any]]:
        """Generate content ideas for specific platform"""
        
        # Build prompt based on platform
        platform_specs = {
            'linkedin': {
                'tone': 'professional, thought leadership',
                'length': '500-1000 words',
                'types': ['industry insights', 'case studies', 'tips & strategies', 'company updates']
            },
            'facebook': {
                'tone': 'conversational, community-focused',
                'length': '200-400 words',
                'types': ['before/after stories', 'customer testimonials', 'quick tips', 'behind-the-scenes']
            },
            'instagram': {
                'tone': 'visual, inspiring, brief',
                'length': '100-150 words',
                'types': ['quote graphics', 'project showcases', 'team spotlights', 'quick tips']
            }
        }
        
        spec = platform_specs.get(platform, platform_specs['linkedin'])
        
        prompt = f"""Generate {count} content ideas for {platform} targeting roofing, HVAC, plumbing, and home services contractors.

Platform: {platform}
Tone: {spec['tone']}
Post Length: {spec['length']}
Content Types: {', '.join(spec['types'])}

For each idea, provide:
1. Title (catchy, attention-grabbing)
2. Topic (specific angle/hook)
3. Key Points (3-5 bullet points to cover)
4. Content Type (blog/social_post/video/etc)
5. Target Audience (specific segment)
6. Keywords (5-7 relevant keywords)
7. Performance Goal (engagement/leads/awareness)

Focus on:
- Solving real pain points (missed calls, slow response times, inefficiency)
- ROI and business growth
- Technology adoption in traditional industries
- Success stories and transformations
- Practical actionable advice

Return ONLY valid JSON array:
[
  {{
    "title": "...",
    "topic": "...",
    "key_points": ["...", "...", "..."],
    "content_type": "social_post",
    "target_audience": "...",
    "keywords": ["...", "...", "..."],
    "performance_goal": "..."
  }},
  ...
]"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            ideas = json.loads(message.content[0].text)
            
            # Add platform to each idea
            for idea in ideas:
                idea['platform'] = platform
            
            return ideas
            
        except Exception as e:
            self._log("generate_ideas", "error", f"Failed for {platform}: {str(e)}")
            return []
    
    async def _save_ideas(self, ideas: List[Dict[str, Any]]) -> int:
        """Save content ideas to database"""
        saved_count = 0
        
        # Calculate scheduled dates (spread over next 7 days)
        start_date = datetime.utcnow().date() + timedelta(days=1)
        
        for i, idea in enumerate(ideas):
            try:
                # Calculate scheduled date (cycle through 7 days)
                days_offset = i % 7
                scheduled_date = start_date + timedelta(days=days_offset)
                
                # Create content calendar entry
                content = ContentCalendar(
                    title=idea.get('title', 'Untitled'),
                    content_type=idea.get('content_type', 'social_post'),
                    platform=idea.get('platform', 'linkedin'),
                    content_body=self._format_content_body(idea),
                    scheduled_date=scheduled_date,
                    status='draft',
                    target_audience=idea.get('target_audience', ''),
                    keywords=idea.get('keywords', []),
                    performance_goal=idea.get('performance_goal', 'engagement')
                )
                
                self.db.add(content)
                saved_count += 1
                
            except Exception as e:
                self._log("save_idea", "warning", f"Failed to save idea: {str(e)}")
                continue
        
        self.db.commit()
        return saved_count
    
    def _format_content_body(self, idea: Dict[str, Any]) -> str:
        """Format idea into content body structure"""
        
        body = f"# {idea.get('title', '')}\n\n"
        body += f"**Topic:** {idea.get('topic', '')}\n\n"
        body += "**Key Points:**\n"
        
        for point in idea.get('key_points', []):
            body += f"- {point}\n"
        
        body += f"\n**Target Audience:** {idea.get('target_audience', '')}\n"
        body += f"**Performance Goal:** {idea.get('performance_goal', '')}\n"
        
        return body
