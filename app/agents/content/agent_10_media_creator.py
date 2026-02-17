"""
Agent 10: Media Creator
Identifies content needing media and provides recommendations
For now, provides Canva template suggestions and stock photo queries
Future: AI image generation integration
Runs daily at 9 AM
"""
from typing import Dict, Any, List
import os
from datetime import datetime
from anthropic import AsyncAnthropic
from app.agents.base import BaseAgent
from app.models import ContentCalendar

class MediaCreatorAgent(BaseAgent):
    """Manages media creation for content"""
    
    def __init__(self, db):
        super().__init__(agent_id=10, agent_name="Media Creator", db=db)
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
    async def execute(self) -> Dict[str, Any]:
        """Main execution logic"""
        
        # Get content in review status that needs media
        content_items = self.db.query(ContentCalendar).filter(
            ContentCalendar.status == 'review',
            ContentCalendar.media_url.is_(None)
        ).limit(10).all()
        
        media_created = 0
        
        for content in content_items:
            try:
                # Generate media recommendation
                media_rec = await self._generate_media_recommendation(content)
                
                if media_rec:
                    # Store media recommendation in metadata
                    content.media_url = media_rec.get('placeholder_url', '')
                    
                    # Add media instructions to content body
                    content.content_body += f"\n\n---\nMEDIA RECOMMENDATION:\n{media_rec.get('description', '')}\n"
                    
                    media_created += 1
                    
            except Exception as e:
                self._log("create_media", "error", f"Failed for {content.title}: {str(e)}")
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "data": {
                "content_processed": len(content_items),
                "media_recommendations": media_created
            }
        }
    
    async def _generate_media_recommendation(self, content: ContentCalendar) -> Dict[str, Any]:
        """Generate media recommendation for content"""
        
        prompt = f"""Recommend the best visual media for this {content.platform} post:

Title: {content.title}
Content Type: {content.content_type}
Platform: {content.platform}
Post Preview: {content.content_body[:500]}...

Provide:
1. Media Type (photo/graphic/video/carousel)
2. Visual Style (professional/casual/before-after/infographic/etc)
3. Key Elements (what should be shown)
4. Canva Template Suggestion (specific template name if possible)
5. Stock Photo Query (3-5 keywords for finding the right image)
6. Color Scheme (brand colors: blue/white/gray or other)

Return JSON:
{{
  "media_type": "...",
  "visual_style": "...",
  "key_elements": ["...", "..."],
  "canva_template": "...",
  "stock_query": "...",
  "color_scheme": "..."
}}"""

        try:
            message = await self.anthropic.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            recommendation = json.loads(message.content[0].text)
            
            # Generate description for manual creation
            description = self._format_media_description(recommendation)
            
            # Generate placeholder URL (for now, using a placeholder service)
            placeholder_url = f"https://placehold.co/1200x630/0066CC/FFFFFF/png?text={content.title.replace(' ', '+')}"
            
            return {
                "description": description,
                "placeholder_url": placeholder_url,
                "recommendation": recommendation
            }
            
        except Exception as e:
            self._log("generate_media_rec", "error", f"Failed: {str(e)}")
            return None
    
    def _format_media_description(self, rec: Dict[str, Any]) -> str:
        """Format media recommendation for manual creation"""
        
        desc = f"Create {rec.get('media_type', 'image')} with {rec.get('visual_style', 'professional')} style\n\n"
        desc += "Key Elements:\n"
        
        for element in rec.get('key_elements', []):
            desc += f"- {element}\n"
        
        desc += f"\nCanva Template: {rec.get('canva_template', 'Use professional template')}\n"
        desc += f"Stock Photo Query: {rec.get('stock_query', 'home services business')}\n"
        desc += f"Color Scheme: {rec.get('color_scheme', 'Blue/White/Gray')}\n"
        
        desc += "\nTo Create:\n"
        desc += "1. Open Canva or Photoshop\n"
        desc += f"2. Search for '{rec.get('canva_template', 'social media post')}' template\n"
        desc += "3. Include the key elements listed above\n"
        desc += f"4. Use color scheme: {rec.get('color_scheme', 'Blue/White')}\n"
        desc += "5. Export as PNG 1200x630 for optimal quality\n"
        
        return desc
