"""
AI Image Generation Service
Supports multiple models: Gemini, DALL-E, Stability AI
"""
from typing import Dict, Any, Optional
import os
import httpx
from anthropic import Anthropic
import base64


class ImageGenerator:
    """Generate images using various AI models"""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=api_key) if api_key else None
        self.gemini_key = os.getenv("GOOGLE_AI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.stability_key = os.getenv("STABILITY_API_KEY")

    async def generate_image(
        self,
        prompt: str,
        model: str = "auto",
        style: str = "photorealistic",
        aspect_ratio: str = "1:1"
    ) -> Dict[str, Any]:
        """
        Generate image from text prompt

        Args:
            prompt: Description of image to generate
            model: "gemini", "dalle3", "stability", or "auto" (AI chooses best)
            style: "photorealistic", "illustration", "minimalist", "artistic"
            aspect_ratio: "1:1", "16:9", "9:16", "4:3"

        Returns:
            {
                "url": "https://...",
                "model_used": "gemini",
                "prompt": "enhanced prompt used",
                "metadata": {}
            }
        """

        # Auto-select model based on content type
        if model == "auto":
            model = await self._select_best_model(prompt, style)

        # Enhance prompt for better results
        enhanced_prompt = await self._enhance_prompt(prompt, style)

        # Generate based on model
        if model == "gemini":
            result = await self._generate_gemini(enhanced_prompt, aspect_ratio)
        elif model == "dalle3":
            result = await self._generate_dalle(enhanced_prompt, aspect_ratio)
        elif model == "stability":
            result = await self._generate_stability(enhanced_prompt, style, aspect_ratio)
        else:
            raise ValueError(f"Unknown model: {model}")

        result["model_used"] = model
        result["original_prompt"] = prompt
        result["enhanced_prompt"] = enhanced_prompt

        return result

    async def _select_best_model(self, prompt: str, style: str) -> str:
        """Use AI to select best model for the content"""
        try:
            if self.anthropic is None:
                return "gemini"
            message = self.anthropic.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": f"""Select the best AI image model for this request.

Prompt: {prompt}
Style: {style}

Models:
- gemini: Best for photorealistic images, people, real-world scenes
- dalle3: Best for creative illustrations, abstract concepts
- stability: Best for artistic styles, custom aesthetics

Respond with ONLY the model name: gemini, dalle3, or stability"""
                }]
            )

            selected = message.content[0].text.strip().lower()
            if selected in ["gemini", "dalle3", "stability"]:
                return selected
        except Exception:
            pass

        # Default fallback
        return "gemini"

    async def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Enhance prompt for better image quality"""
        try:
            if self.anthropic is None:
                return prompt
            message = self.anthropic.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""Enhance this image generation prompt to be more detailed and specific.

Original: {prompt}
Style: {style}

Add details about:
- Lighting and atmosphere
- Composition and framing
- Color palette
- Quality keywords

Keep it under 200 words. Be specific and vivid.

Enhanced prompt:"""
                }]
            )
            return message.content[0].text.strip()
        except Exception:
            return prompt

    async def _generate_gemini(self, prompt: str, aspect_ratio: str) -> Dict[str, Any]:
        """Generate image using Google Gemini"""
        if not self.gemini_key:
            raise ValueError("GOOGLE_AI_API_KEY not configured")

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Using Imagen API endpoint
            url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict"
            payload = {
                "instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1, "aspectRatio": aspect_ratio.replace(":", "_")},
            }
            headers = {"Content-Type": "application/json"}
            response = await client.post(url, json=payload, headers=headers, params={"key": self.gemini_key})

            if response.status_code == 200:
                data = response.json()
                image_data = data["predictions"][0]["bytesBase64Encoded"]
                return {"url": f"data:image/png;base64,{image_data}", "format": "png"}
            raise Exception(f"Gemini API error: {response.text}")

    async def _generate_dalle(self, prompt: str, aspect_ratio: str) -> Dict[str, Any]:
        """Generate image using DALL-E 3"""
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY not configured")

        size_map = {
            "1:1": "1024x1024",
            "16:9": "1792x1024",
            "9:16": "1024x1792",
        }
        size = size_map.get(aspect_ratio, "1024x1024")

        async with httpx.AsyncClient(timeout=60.0) as client:
            url = "https://api.openai.com/v1/images/generations"
            payload = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": size, "quality": "hd"}
            headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return {
                    "url": data["data"][0]["url"],
                    "format": "png",
                    "revised_prompt": data["data"][0].get("revised_prompt"),
                }
            raise Exception(f"DALL-E API error: {response.text}")

    async def _generate_stability(self, prompt: str, style: str, aspect_ratio: str) -> Dict[str, Any]:
        """Generate image using Stability AI"""
        if not self.stability_key:
            raise ValueError("STABILITY_API_KEY not configured")

        aspect_map = {"1:1": "1:1", "16:9": "16:9", "9:16": "9:16", "4:3": "4:3"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            url = "https://api.stability.ai/v2beta/stable-image/generate/ultra"
            payload = {
                "prompt": prompt,
                "aspect_ratio": aspect_map.get(aspect_ratio, "1:1"),
                "output_format": "png",
            }
            headers = {"Authorization": f"Bearer {self.stability_key}", "Accept": "image/*"}
            response = await client.post(url, data=payload, headers=headers)

            if response.status_code == 200:
                image_bytes = response.content
                image_base64 = base64.b64encode(image_bytes).decode()
                return {"url": f"data:image/png;base64,{image_base64}", "format": "png"}
            raise Exception(f"Stability API error: {response.text}")

