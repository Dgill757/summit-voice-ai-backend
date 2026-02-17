"""
Agent 9: Post Drafter
Turns content ideas into fully-written posts
Target: 3 posts per day
Runs daily at 8 AM
"""
from typing import Dict, Any
import os
from datetime import datetime
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import ContentCalendar

class PostDrafterAgent(BaseAgent):
    """Drafts complete social media posts from ideas"""
    
    def __init__(self, db):
        super().__init__(agent_id=9, agent_name="Post Drafter", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get posts per day from config
        posts_per_day = self.config.get('posts_per_day', 3)
        
        # Get draft content ideas that need to be written
        drafts = self.db.query(ContentCalendar).filter(
            ContentCalendar.status == 'draft',
            ContentCalendar.scheduled_date <= datetime.utcnow().date()
        ).limit(posts_per_day).all()
        
        posts_drafted = 0
        
        for draft in drafts:
            try:
                # Generate full post content
                post_content = await self._draft_post(draft)
                
                if post_content:
                    # Update content with drafted post
                    draft.content_body = post_content['body']
                    draft.status = 'review'
                    
                    posts_drafted += 1
                    
            except Exception as e:
                self._log("draft_post", "error", f"Failed for {draft.title}: {str(e)}")
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "data": {
                "drafts_processed": len(drafts),
                "posts_drafted": posts_drafted
            }
        }
    
    async def _draft_post(self, content: ContentCalendar) -> Dict[str, str]:
        """Draft complete post from content idea"""
        
        # Platform-specific guidelines
        guidelines = {
            'linkedin': {
                'max_length': 1300,
                'style': 'Professional, thought leadership, storytelling',
                'structure': 'Hook ? Story/Context ? Value/Insight ? CTA',
                'hashtags': 3-5,
                'emojis': 'Minimal, professional only'
            },
            'facebook': {
                'max_length': 500,
                'style': 'Conversational, community-focused, relatable',
                'structure': 'Hook ? Value ? Story ? CTA',
                'hashtags': 1-3,
                'emojis': 'Moderate use'
            },
            'instagram': {
                'max_length': 2200,
                'style': 'Visual-first, inspirational, brief',
                'structure': 'Hook ? Value ? CTA (front-load value)',
                'hashtags': 10-15,
                'emojis': 'Generous use'
            }
        }
        
        platform = content.platform
        guide = guidelines.get(platform, guidelines['linkedin'])
        
        prompt = f"""Write a complete {platform} post based on this content idea:

Title: {content.title}
Content Body: {content.content_body}
Target Audience: {content.target_audience}
Keywords: {', '.join(content.keywords or [])}
Performance Goal: {content.performance_goal}

Platform Guidelines:
- Max Length: {guide['max_length']} characters
- Style: {guide['style']}
- Structure: {guide['structure']}
- Hashtags: {guide['hashtags']}
- Emojis: {guide['emojis']}

Requirements:
1. Start with a POWERFUL hook (first line must grab attention)
2. Include specific examples, numbers, or stories
3. Provide actionable value (what can they DO with this info?)
4. End with clear CTA (comment, share, DM, or click link)
5. Use line breaks for readability (no walls of text)
6. Sound human, authentic, not AI-generated
7. Focus on the pain points of roofing/HVAC/plumbing business owners

For {platform}, optimize for:
- LinkedIn: Expertise, credibility, professional insights
- Facebook: Community, conversation, relatability  
- Instagram: Visual appeal, inspiration, quick value

Return ONLY the post text (no JSON, no explanation):"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            post_text = message.content[0].text.strip()
            
            # Add hashtags if platform requires them
            if platform == 'instagram':
                hashtags = self._generate_hashtags(content, 12)
                post_text += f"\n\n{hashtags}"
            elif platform in ['linkedin', 'facebook']:
                hashtags = self._generate_hashtags(content, 3)
                post_text += f"\n\n{hashtags}"
            
            return {
                "body": post_text
            }
            
        except Exception as e:
            self._log("draft_post", "error", f"Claude API failed: {str(e)}")
            return None
    
    def _generate_hashtags(self, content: ContentCalendar, count: int) -> str:
        """Generate relevant hashtags"""
        
        # Base hashtags by industry
        base_hashtags = [
            '#VoiceAI',
            '#HomeServices',
            '#SmallBusiness',
            '#BusinessGrowth',
            '#Automation'
        ]
        
        # Add industry-specific
        industry_hashtags = {
            'roofing': ['#Roofing', '#RoofingContractor', '#RoofingBusiness'],
            'hvac': ['#HVAC', '#HVACContractor', '#HeatingCooling'],
            'plumbing': ['#Plumbing', '#PlumbingBusiness', '#PlumbingContractor']
        }
        
        # Combine with content keywords
        all_tags = base_hashtags.copy()
        
        if content.keywords:
            for keyword in content.keywords[:3]:
                tag = '#' + keyword.replace(' ', '').title()
                all_tags.append(tag)
        
        # Return requested count
        return ' '.join(all_tags[:count])
