import os
import base64
import requests
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
API_URL = "https://api.llama.com/v1/chat/completions" # Replace with actual API endpoint if different
# Define paths for the two images
IMAGE_PATH_1 = "test.png" # Replace with your first image path
IMAGE_PATH_2 = "test2.png" # Replace with your second image path
MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8" # Replace with the model you intend to use if different
# Removed TARGET_DESCRIPTION, MAX_RETRIES, RETRY_DELAY as they are not needed for this version

def encode_image(image_path):
    """Encodes the image file to base64."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def get_images_description(base64_image_1, base64_image_2):
    """Sends two images to the Llama API and returns the description."""
    if not LLAMA_API_KEY:
        print("Error: LLAMA_API_KEY not found in environment variables.")
        return None
    if not base64_image_1 or not base64_image_2:
        print("Error: One or both base64 image strings are missing.")
        return None

    headers = {
        "Authorization": f"Bearer {LLAMA_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe these two images in detail."},
                    {
                        "type": "image_url",
                        "image_url": {
                            # Assuming PNG, adjust content type if needed (e.g., image/jpeg)
                            "url": f"data:image/png;base64,{base64_image_1}"
                        }
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            # Assuming PNG, adjust content type if needed
                            "url": f"data:image/png;base64,{base64_image_2}"
                        }
                    }
                ]
            }
        ],
        # Add other parameters like max_tokens if needed
        # "max_tokens": 500 # Increased max_tokens might be needed for two images
    }

    print("Sending request to Llama API...")
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        print("Received response from API.")
        data = response.json()

        # Extract the text content from the response structure
        # This might need adjustment based on the actual API response format
        # Based on previous log, content might be nested deeper
        if 'completion_message' in data and 'content' in data['completion_message'] and 'text' in data['completion_message']['content']:
             return data['completion_message']['content']['text']
        elif data.get("choices") and len(data["choices"]) > 0:
            message_content = data["choices"][0].get("message", {}).get("content")
            if message_content:
                # If content is a list (like in the older example format)
                if isinstance(message_content, list):
                     text_parts = [item['text'] for item in message_content if item.get('type') == 'text']
                     return " ".join(text_parts)
                # If content is just text
                elif isinstance(message_content, str):
                    return message_content

        print("Could not find description in API response format.")
        print("Full API Response:", data)
        return None

    except requests.exceptions.RequestException as e:
        print(f"Error calling Llama API: {e}")
        if e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def main():
    """Main function to get descriptions for two images."""
    print(f"Attempting to describe images: {IMAGE_PATH_1} and {IMAGE_PATH_2}")

    print(f"Encoding {IMAGE_PATH_1}...")
    base64_image_1 = encode_image(IMAGE_PATH_1)
    if not base64_image_1:
        return

    print(f"Encoding {IMAGE_PATH_2}...")
    base64_image_2 = encode_image(IMAGE_PATH_2)
    if not base64_image_2:
        return

    print("Requesting description for both images...")
    description = get_images_description(base64_image_1, base64_image_2)

    print("------ Combined Description ------")
    if description:
        print(description)
    else:
        print("Failed to get description for the images.")
    print("---------------------------------")

if __name__ == "__main__":
    main() 