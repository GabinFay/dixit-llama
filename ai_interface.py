import os
import base64
import requests
import time
import random # Added for fallback
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
# Make endpoint and model configurable or constants here
API_URL = os.getenv("LLAMA_API_URL", "https://api.llama.com/v1/chat/completions") # Use env var or default
MODEL = os.getenv("LLAMA_MODEL", "Llama-4-Maverick-17B-128E-Instruct-FP8") # Use env var or default
DEFAULT_MAX_TOKENS = 150 # Adjust as needed for different tasks

def encode_image(image_path):
    """Encodes the image file to base64."""
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at {image_path}")
        return None
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None

def _parse_ai_index_response(response_text, num_options):
    """Attempts to parse an integer index from the AI response."""
    if not response_text:
        return None
    try:
        # Try to extract the first integer found
        import re
        match = re.search(r'\d+', response_text)
        if match:
            index = int(match.group(0))
            if 0 <= index < num_options:
                return index
            else:
                print(f"Warning: AI returned index {index} out of bounds (0-{num_options-1}).")
                return None
        else:
            print(f"Warning: Could not find numeric index in AI response: '{response_text}'")
            return None
    except ValueError:
        print(f"Warning: Could not parse index from AI response: '{response_text}'")
        return None

def _call_llama_api(payload, max_retries=2, retry_delay=5):
    """Sends a prepared payload to the Llama API and returns the text content."""
    if not LLAMA_API_KEY:
        print("Error: LLAMA_API_KEY not found in environment variables.")
        return None

    headers = {
        "Authorization": f"Bearer {LLAMA_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(max_retries):
        print(f"Sending request to Llama API (Attempt {attempt + 1}/{max_retries})...")
        try:
            # Increased timeout for potentially larger payloads/longer processing
            response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            print("Received response from API.")
            data = response.json()

            # --- Flexible Content Extraction ---
            # Extract first text content found in common structures
            if data.get("choices") and len(data["choices"]) > 0:
                 message = data["choices"][0].get("message", {})
                 content = message.get("content")
                 if isinstance(content, str):
                      print(f"API Response Text: {content[:100]}...") # Log beginning of response
                      return content.strip()
                 elif isinstance(content, list):
                      text_parts = [item['text'] for item in content if item.get('type') == 'text']
                      full_text = " ".join(text_parts).strip()
                      print(f"API Response Text (from list): {full_text[:100]}...")
                      return full_text

            # Handle other possible structures if necessary (e.g., direct completion field)
            # Example based on user log:
            elif data.get('completion_message') and data['completion_message'].get('content') and isinstance(data['completion_message']['content'], dict):
                 text_content = data['completion_message']['content'].get('text')
                 if isinstance(text_content, str):
                      print(f"API Response Text (completion_message): {text_content[:100]}...")
                      return text_content.strip()

            print("Could not find standard text content in API response.")
            print("Full API Response Structure sample:", str(data)[:200]) # Log structure for debugging
            return None

        except requests.exceptions.Timeout:
            print(f"API request timed out.")
        except requests.exceptions.RequestException as e:
            print(f"Error calling Llama API: {e}")
            if e.response is not None:
                print(f"Response status code: {e.response.status_code}")
                try:
                     print(f"Response text: {e.response.text}")
                except Exception: pass
        except Exception as e:
            print(f"An unexpected error occurred during API call: {e}")

        if attempt < max_retries - 1:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            print("Max retries reached. API call failed.")
            return None

    return None

def generate_clue_for_image(image_path):
    """Generates a Dixit-style clue for a single image."""
    base64_image = encode_image(image_path)
    if not base64_image:
        return None

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Generate a short, evocative, one-sentence clue for this image, suitable for the card game Dixit. Avoid describing the image literally. Focus on themes, feelings, or abstract concepts."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"} # Assuming PNG
                    }
                ]
            }
        ],
        "max_tokens": DEFAULT_MAX_TOKENS // 2
    }
    return _call_llama_api(payload)

def choose_card_for_clue(hand_card_paths, clue):
    """Chooses the best card *index* from the hand that matches the clue using a single API call."""
    if not hand_card_paths:
        return None

    print(f"AI evaluating {len(hand_card_paths)} cards for clue: '{clue}'")

    content_list = [
        {"type": "text", "text": f"Given the Dixit clue '{clue}', which of the following images (indexed 0 to {len(hand_card_paths)-1}) is the best fit? Respond with only the index number."}
    ]

    valid_images_indices = []
    for i, card_path in enumerate(hand_card_paths):
        base64_image = encode_image(card_path)
        if base64_image:
            content_list.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            })
            valid_images_indices.append(i) # Keep track of images successfully added
        else:
            print(f"Warning: Could not encode image {card_path} for multi-image prompt.")

    if len(valid_images_indices) <= 1:
        print("Warning: Not enough valid images in hand to make a meaningful choice.")
        return random.choice(range(len(hand_card_paths))) if hand_card_paths else None # Fallback: random index if any cards exist

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": content_list}
        ],
        "max_tokens": 10 # Expecting just an index
    }

    response_text = _call_llama_api(payload)
    chosen_index = _parse_ai_index_response(response_text, len(hand_card_paths))

    if chosen_index is not None:
        print(f"AI chose index: {chosen_index}")
        return chosen_index
    else:
        # Fallback if AI fails or returns invalid index
        print(f"AI failed to provide a valid index. Choosing randomly from hand.")
        return random.choice(range(len(hand_card_paths))) # Return random valid index


def guess_storyteller_card(board_card_paths, clue, player_card_path):
    """Guesses the storyteller's card *index* from the board using a single API call,
       avoiding the player's own card."""
    if not board_card_paths or len(board_card_paths) <= 1:
        return 0 # Cannot guess if only one card

    print(f"AI guessing card for clue: '{clue}' (excluding own card: {os.path.basename(player_card_path)}) from {len(board_card_paths)} cards.")

    content_list = []
    index_map = {} # Maps API prompt index to original board index
    prompt_idx = 0
    image_content = []

    # Prepare image data first
    for i, card_path in enumerate(board_card_paths):
        if card_path == player_card_path:
             print(f" - Skipping own card at board index {i}")
             continue # Skip player's own card

        base64_image = encode_image(card_path)
        if base64_image:
            image_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            })
            index_map[prompt_idx] = i # Map the index in the prompt to the original board index
            prompt_idx += 1
        else:
            print(f"Warning: Could not encode image {card_path} for guessing prompt.")

    num_options_in_prompt = len(image_content)

    if num_options_in_prompt == 0:
        print("Error: No valid images (excluding own) to guess from.")
        # Fallback: guess randomly from original board excluding own card
        valid_indices = [idx for idx, path in enumerate(board_card_paths) if path != player_card_path]
        return random.choice(valid_indices) if valid_indices else 0
    elif num_options_in_prompt == 1:
         # Only one other card left, must be the storyteller's
         guessed_original_index = list(index_map.values())[0]
         print(f"Only one valid option (Board Index {guessed_original_index}). Guessing that.")
         return guessed_original_index

    # Construct the text part of the prompt
    content_list.append({
        "type": "text",
        "text": f"Given the Dixit clue '{clue}', which of the following images (indexed 0 to {num_options_in_prompt-1}) is most likely the storyteller's card? Respond with only the index number."
    })
    # Add the image content
    content_list.extend(image_content)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": content_list}
        ],
        "max_tokens": 10 # Expecting just an index
    }

    response_text = _call_llama_api(payload)
    # Parse the index relative to the prompt (0 to num_options_in_prompt-1)
    parsed_prompt_index = _parse_ai_index_response(response_text, num_options_in_prompt)

    if parsed_prompt_index is not None:
        # Map back to the original board index
        guessed_original_index = index_map.get(parsed_prompt_index)
        if guessed_original_index is not None:
            print(f"AI chose prompt index: {parsed_prompt_index}, which maps to board index: {guessed_original_index}")
            return guessed_original_index
        else:
             print(f"Error: AI returned valid prompt index {parsed_prompt_index}, but mapping failed.")
    else:
        print(f"AI failed to provide a valid index response.")

    # Fallback if AI fails or returns invalid index
    print("Choosing randomly (excluding own card)." )
    valid_indices = [idx for idx, path in enumerate(board_card_paths) if path != player_card_path]
    return random.choice(valid_indices) if valid_indices else 0 # Return random valid *original* board index


# Example usage (optional, for testing)
# if __name__ == '__main__':
#     test_image = 'cards/001.png' # Replace with an actual card image
#     cards_dir = 'cards' # Define cards directory for constructing paths
#     if os.path.exists(os.path.join(cards_dir, '001.png')):
#         # Test clue generation
#         print("\n--- Testing Clue Generation ---")
#         clue = generate_clue_for_image(os.path.join(cards_dir, '001.png'))
#         if clue:
#             print(f"Generated Clue: {clue}")
#         else:
#             print("Failed to generate clue.")
#
#         # Test card choosing (needs a dummy hand and clue)
#         print("\n--- Testing Card Choice ---")
#         dummy_hand_files = ['001.png', '002.png', '003.png'] # Just filenames
#         dummy_hand_paths = [os.path.join(cards_dir, f) for f in dummy_hand_files if os.path.exists(os.path.join(cards_dir, f))] # Full paths, filtered
#         test_clue = clue or "Ephemeral journey" # Use generated clue or a default
#         if dummy_hand_paths:
#              chosen_card_path = choose_card_for_clue(dummy_hand_paths, test_clue)
#              if chosen_card_path:
#                   print(f"Chosen card for clue '{test_clue}': {os.path.basename(chosen_card_path)}")
#              else:
#                   print("Failed to choose a card.")
#         else:
#              print("Skipping card choice test (no valid dummy hand paths).")
#
#
#         # Test guessing (needs a dummy board, clue, and own card)
#         print("\n--- Testing Card Guessing ---")
#         dummy_board_files = ['004.png', '001.png', '005.png'] # storyteller's card is 001
#         dummy_board_paths = [os.path.join(cards_dir, f) for f in dummy_board_files if os.path.exists(os.path.join(cards_dir, f))]
#         ai_own_card_file = '004.png' # Assume AI submitted 004
#         ai_own_card_path = os.path.join(cards_dir, ai_own_card_file)
#
#         if len(dummy_board_paths) > 1 and ai_own_card_path in dummy_board_paths:
#              guess = guess_storyteller_card(dummy_board_paths, test_clue, ai_own_card_path)
#              print(f"AI guessed index: {guess}")
#              try:
#                   print(f"  (Actual card at guessed index: {os.path.basename(dummy_board_paths[guess])})")
#                   correct_card_path = os.path.join(cards_dir, '001.png')
#                   correct_index = dummy_board_paths.index(correct_card_path)
#                   print(f"  (Correct index: {correct_index})")
#              except (IndexError, ValueError):
#                   print("  Error finding card at index or correct index.")
#         else:
#              print("Skipping guessing test (invalid dummy board setup).")
#
#     else:
#         print(f"Test image {os.path.join(cards_dir, '001.png')} not found. Cannot run tests.") 