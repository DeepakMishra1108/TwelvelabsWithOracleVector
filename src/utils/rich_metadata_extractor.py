"""
Rich Metadata Extraction for Natural Language Search
Extracts structured metadata from photos using GPT-4 Vision
"""

import logging
import json
from typing import Dict, List, Optional
import base64

logger = logging.getLogger(__name__)

# Structured metadata schema
METADATA_CATEGORIES = {
    "background": ["beach", "indoor", "outdoor", "mountains", "forest", "city", "park", "garden", "room", "street", "water", "sky"],
    "objects": ["car", "dog", "cat", "pet", "flowers", "food", "cake", "phone", "camera", "book", "furniture", "building", "tree"],
    "activities": ["swimming", "eating", "drinking", "playing", "running", "walking", "sitting", "standing", "dancing", "cooking", "reading", "working"],
    "clothing": ["dress", "suit", "casual", "formal", "red", "blue", "white", "black", "colorful", "traditional", "modern"],
    "themes": ["birthday", "party", "wedding", "vacation", "holiday", "celebration", "festival", "meeting", "graduation", "anniversary", "picnic", "trip"],
    "people": ["group", "couple", "family", "children", "adults", "friends", "alone", "crowd"],
    "mood": ["happy", "joyful", "serious", "casual", "formal", "relaxed", "energetic", "peaceful"],
    "time": ["morning", "afternoon", "evening", "night", "sunset", "sunrise", "daylight", "dark"]
}

def extract_rich_metadata(image_path: str, api_key: Optional[str] = None) -> Dict:
    """
    Extract rich structured metadata from image using GPT-4 Vision
    
    Args:
        image_path: Path to the image file
        api_key: OpenAI API key (optional, uses env var if not provided)
        
    Returns:
        Dict containing structured metadata
    """
    try:
        import openai
        import os
        
        if not api_key:
            api_key = os.environ.get('OPENAI_API_KEY')
        
        if not api_key:
            logger.warning("⚠️  OpenAI API key not found, cannot extract rich metadata")
            return {"error": "OpenAI API key not configured"}
        
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        client = openai.OpenAI(api_key=api_key)
        
        # Create detailed prompt for metadata extraction
        prompt = f"""Analyze this image and extract structured metadata in JSON format.

Identify and return ONLY the categories that are clearly visible or evident in the image:

**Background/Setting**: Where was this photo taken? (e.g., beach, indoor, outdoor, mountains, forest, city, park, garden, room, street, water)

**Objects**: What objects are visible? (e.g., car, dog, cat, flowers, food, cake, phone, camera, furniture, building, tree)

**Activities**: What are people doing? (e.g., swimming, eating, drinking, playing, running, walking, sitting, dancing, cooking)

**Clothing/Appearance**: What are people wearing? Describe style and colors (e.g., red dress, suit, casual, formal, traditional)

**Theme/Event**: What type of event or occasion? (e.g., birthday, party, wedding, vacation, holiday, celebration, festival, graduation)

**People**: How many people? (e.g., group, couple, family, children, adults, friends, alone, crowd)

**Mood/Atmosphere**: What's the emotional tone? (e.g., happy, joyful, serious, casual, formal, relaxed, energetic)

**Time of Day**: When was this taken? (e.g., morning, afternoon, evening, night, sunset, sunrise)

Return a JSON object with these fields (omit fields if not applicable):
{{
    "background": ["value1", "value2"],
    "objects": ["value1", "value2"],
    "activities": ["value1", "value2"],
    "clothing": ["value1", "value2"],
    "themes": ["value1", "value2"],
    "people": ["value1", "value2"],
    "mood": ["value1", "value2"],
    "time": ["value1", "value2"],
    "description": "A brief 1-2 sentence natural description of the scene"
}}

Be specific and descriptive. Include colors, styles, and details."""

        logger.info("🔍 Calling GPT-4 Vision for rich metadata extraction...")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.3  # Lower temperature for more consistent categorization
        )
        
        content = response.choices[0].message.content
        logger.info(f"✅ GPT-4 Vision response: {content[:200]}...")
        
        # Parse JSON response
        # Remove markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        metadata = json.loads(content)
        
        # Validate and clean metadata
        validated_metadata = {
            "background": metadata.get("background", []),
            "objects": metadata.get("objects", []),
            "activities": metadata.get("activities", []),
            "clothing": metadata.get("clothing", []),
            "themes": metadata.get("themes", []),
            "people": metadata.get("people", []),
            "mood": metadata.get("mood", []),
            "time": metadata.get("time", []),
            "description": metadata.get("description", ""),
            "extraction_model": "gpt-4o",
            "extraction_success": True
        }
        
        # Create searchable text from all metadata
        searchable_text = " ".join([
            " ".join(validated_metadata.get("background", [])),
            " ".join(validated_metadata.get("objects", [])),
            " ".join(validated_metadata.get("activities", [])),
            " ".join(validated_metadata.get("clothing", [])),
            " ".join(validated_metadata.get("themes", [])),
            " ".join(validated_metadata.get("people", [])),
            " ".join(validated_metadata.get("mood", [])),
            " ".join(validated_metadata.get("time", [])),
            validated_metadata.get("description", "")
        ]).lower()
        
        validated_metadata["searchable_text"] = searchable_text
        
        logger.info(f"✅ Extracted rich metadata: {len(searchable_text.split())} keywords")
        logger.info(f"   Background: {validated_metadata['background']}")
        logger.info(f"   Objects: {validated_metadata['objects']}")
        logger.info(f"   Activities: {validated_metadata['activities']}")
        logger.info(f"   Themes: {validated_metadata['themes']}")
        
        return validated_metadata
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse GPT-4 response as JSON: {e}")
        logger.error(f"   Response content: {content}")
        return {
            "error": "Failed to parse metadata",
            "extraction_success": False
        }
    except Exception as e:
        logger.error(f"❌ Rich metadata extraction failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": str(e),
            "extraction_success": False
        }


def search_by_metadata(
    query: str,
    connection,
    user_id: Optional[int] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Search photos by natural language query using rich metadata
    
    Args:
        query: Natural language search query (e.g., "photos at the beach")
        connection: Database connection
        user_id: Optional user ID to filter results
        limit: Maximum results
        
    Returns:
        List of matching photos with metadata
    """
    try:
        cursor = connection.cursor()
        
        # Build SQL query with text search on rich_metadata CLOB
        query_params = {'query': f'%{query.lower()}%', 'limit': limit}
        
        user_filter = ""
        if user_id:
            user_filter = "AND am.uploaded_by = :user_id"
            query_params['user_id'] = user_id
        
        cursor.execute(f"""
            SELECT 
                am.id,
                am.file_name,
                am.thumbnail_url,
                am.stream_url,
                am.created_at,
                am.file_type,
                am.rich_metadata
            FROM album_media am
            WHERE am.rich_metadata IS NOT NULL
            AND (
                LOWER(am.rich_metadata) LIKE :query
                OR DBMS_LOB.INSTR(LOWER(am.rich_metadata), :query) > 0
            )
            {user_filter}
            ORDER BY am.created_at DESC
            FETCH FIRST :limit ROWS ONLY
        """, query_params)
        
        results = []
        for row in cursor.fetchall():
            media_id, file_name, thumbnail_url, stream_url, created_at, file_type, metadata_clob = row
            
            # Parse metadata
            try:
                if metadata_clob:
                    metadata = json.loads(metadata_clob.read())
                else:
                    metadata = {}
            except:
                metadata = {}
            
            results.append({
                'media_id': media_id,
                'file_name': file_name,
                'thumbnail_url': thumbnail_url,
                'stream_url': stream_url,
                'created_at': created_at.isoformat() if created_at else None,
                'file_type': file_type,
                'metadata': metadata
            })
        
        logger.info(f"✅ Metadata search for '{query}': found {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"❌ Metadata search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


if __name__ == "__main__":
    print("Rich Metadata Extractor")
    print("=" * 60)
    print("Extracts structured metadata for natural language search")
    print("\nSupported categories:")
    for category, values in METADATA_CATEGORIES.items():
        print(f"  {category}: {', '.join(values[:5])}...")
