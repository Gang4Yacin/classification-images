import json
import sys
import requests
from PIL import Image
import imagehash
from io import BytesIO

def download_image(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        return None

def calculate_similarity(img1, img2):
    if img1 is None or img2 is None:
        return 0.0
    
    # Using Perceptual Hashing (dhash is usually good for similarity)
    hash1 = imagehash.dhash(img1)
    hash2 = imagehash.dhash(img2)
    
    # Distance is number of differing bits. Max distance is hash_size * hash_size (default 8*8=64)
    # Similarity = 1 - (distance / max_distance)
    distance = hash1 - hash2
    max_distance = 64 # for 8x8 hash
    similarity = 1 - (distance / max_distance)
    return similarity * 100

def process_users(data):
    if isinstance(data, dict):
        # Handle single user object
        data = [data]
    
    results = []
    
    for user in data:
        user_id = user.get("user_id")
        ad_creative_images = user.get("ad_creative_images", [])
        metaad_previews = user.get("metaad_previews", [])
        
        user_matches = []
        
        # Pre-download metaad previews to avoid re-downloading for each creative
        preview_images = []
        for p in metaad_previews:
            img = download_image(p["url"])
            if img:
                preview_images.append({"id": p["id"], "url": p["url"], "image": img})
        
        for creative in ad_creative_images:
            creative_id = creative.get("id")
            creative_urls = creative.get("urls", {})
            
            # Support both old format ('url') and new format ('urls')
            if "url" in creative and not creative_urls:
                creative_urls = {"original": creative["url"]}
            
            best_overall_match = None
            max_sim = -1.0
            
            # Iterate through each version of the creative image (original, 1:1, 4:5, etc.)
            for url_key, url_value in creative_urls.items():
                creative_img = download_image(url_value)
                if not creative_img:
                    continue
                
                for preview in preview_images:
                    sim = calculate_similarity(creative_img, preview["image"])
                    if sim > max_sim:
                        max_sim = sim
                        best_overall_match = {
                            "ad_creative_image_id": creative_id,
                            "ad_creative_image_url": url_value,
                            "ad_creative_image_url_key": url_key,
                            "metaad_preview_id": preview["id"],
                            "metaad_preview_url": preview["url"],
                            "similarity_percentage": round(sim, 2)
                        }
            
            if best_overall_match:
                user_matches.append(best_overall_match)
        
        results.append({
            "user_id": user_id,
            "matches": user_matches
        })
    
    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compare_images.py '<json_data>'")
        sys.exit(1)
    
    try:
        input_data = json.loads(sys.argv[1])
        output = process_users(input_data)
        print(json.dumps(output, indent=2))
    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        sys.exit(1)
