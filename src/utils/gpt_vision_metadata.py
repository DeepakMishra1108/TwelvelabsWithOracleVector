"""
GPT-4o-mini Vision API for Rich Metadata Extraction
Extracts structured metadata from images for natural language search
"""

import os
import json
import base64
import logging
from typing import Dict, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class GPTVisionMetadataExtractor:
    """Extract rich metadata from images using GPT-4o-mini vision model"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize GPT-4o-mini client"""
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"
        logger.info("✅ GPT-4o-mini vision client initialized")
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64 string"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_metadata(self, image_path: str) -> Dict:
        """
        Extract rich metadata from image using GPT-4o-mini
        
        Returns structured JSON with:
        - setting: indoor/outdoor/beach/mountain/city/etc
        - objects: list of main objects/items in photo
        - people_count: number of people detected
        - activities: what people are doing
        - colors: dominant colors
        - mood: overall mood/feeling
        - time_of_day: morning/afternoon/evening/night
        - weather: sunny/cloudy/rainy (if outdoor)
        - tags: searchable keywords
        """
        try:
            logger.info(f"🔍 Extracting metadata from: {image_path}")
            
            # Encode image
            base64_image = self.encode_image(image_path)
            
            # Detailed prompt for structured metadata
            prompt = """Analyze this image and provide detailed metadata in JSON format.

Return ONLY valid JSON (no markdown, no explanations) with this exact structure:
{
  "setting": "indoor/outdoor/beach/mountain/city/home/restaurant/office/etc",
  "location_type": "specific location description",
  "objects": ["list", "of", "main", "objects", "items", "in", "photo"],
  "people_count": 0,
  "activities": ["what", "people", "are", "doing"],
  "clothing": ["description", "of", "clothing", "colors", "styles"],
  "colors": ["dominant", "colors"],
  "mood": "happy/serious/casual/formal/celebratory/etc",
  "time_of_day": "morning/afternoon/evening/night/unknown",
  "weather": "sunny/cloudy/rainy/snowy/unknown",
  "scene_type": "portrait/group/landscape/food/event/sports/etc",
  "tags": ["searchable", "keywords", "for", "natural", "language", "search"]
}

Be specific and detailed. Include colors of clothing, types of objects, specific activities.
Example tags: "red dress", "beach sunset", "birthday party", "family gathering", "outdoor barbecue"
"""
            
            # Call GPT-4o-mini vision API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low"  # Use low detail for faster/cheaper processing
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.3  # Lower temperature for more consistent JSON output
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            metadata = json.loads(content)
            
            # Add generation metadata
            metadata['generated_by'] = 'gpt-4o-mini'
            metadata['model_version'] = self.model
            
            logger.info(f"✅ Extracted metadata: {metadata.get('scene_type')} with {metadata.get('people_count', 0)} people")
            logger.info(f"   Tags: {', '.join(metadata.get('tags', [])[:5])}")
            
            return metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response: {e}")
            logger.error(f"   Raw response: {content}")
            return self._get_fallback_metadata()
        except Exception as e:
            logger.error(f"❌ Metadata extraction failed: {e}")
            return self._get_fallback_metadata()
    
    def _get_fallback_metadata(self) -> Dict:
        """Return minimal fallback metadata if extraction fails"""
        return {
            "setting": "unknown",
            "location_type": "unknown",
            "objects": [],
            "people_count": 0,
            "activities": [],
            "clothing": [],
            "colors": [],
            "mood": "unknown",
            "time_of_day": "unknown",
            "weather": "unknown",
            "scene_type": "unknown",
            "tags": [],
            "generated_by": "gpt-4o-mini",
            "status": "failed"
        }


def extract_metadata_from_file(image_path: str) -> Dict:
    """Convenience function to extract metadata from a single image"""
    extractor = GPTVisionMetadataExtractor()
    return extractor.extract_metadata(image_path)


if __name__ == "__main__":
    # Test the extractor
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python gpt_vision_metadata.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    print(f"\n🔍 Analyzing image: {image_path}\n")
    
    metadata = extract_metadata_from_file(image_path)
    
    print("\n📊 Extracted Metadata:")
    print(json.dumps(metadata, indent=2))
