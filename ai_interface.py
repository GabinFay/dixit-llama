import os
import base64
import requests
import time
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
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60) # Added timeout
            response.raise_for_status()
            print("Received response from API.")
            data = response.json()

            # --- Flexible Content Extraction ---
            # Attempt 1: Standard OpenAI/Compatible format
            if data.get("choices") and len(data["choices"]) > 0:
                 message = data["choices"][0].get("message", {})
                 content = message.get("content")
                 if isinstance(content, str):
                      return content.strip()
                 # Handle potential list content (like in older vision models)
                 elif isinstance(content, list):
                      text_parts = [item['text'] for item in content if item.get('type') == 'text']
                      return " ".join(text_parts).strip()

            # Attempt 2: Anthropic/Claude-like format (if response structure differs)
            # Example: data.get('completion') or data.get('content') being the direct text
            # This part might need adjustment based on the specific Llama provider's format
            # For now, we assume the 'choices' structure is common

            # Fallback: Print structure if unsure
            print("Could not find standard text content in API response.")
            print("Full API Response Structure:", data) # Log structure for debugging
            return None

        except requests.exceptions.Timeout:
            print(f"API request timed out after 60 seconds.")
        except requests.exceptions.RequestException as e:
            print(f"Error calling Llama API: {e}")
            if e.response is not None:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
        except Exception as e:
            print(f"An unexpected error occurred during API call: {e}")

        if attempt < max_retries - 1:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            print("Max retries reached. API call failed.")
            return None

    return None # Should not be reached if retries are handled correctly

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
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"} # Assuming PNG, adjust if needed
                    }
                ]
            }
        ],
        "max_tokens": DEFAULT_MAX_TOKENS // 2 # Shorter response expected for clue
    }
    return _call_llama_api(payload)

def choose_card_for_clue(hand_card_paths, clue):
    """Chooses the best card from the hand that matches the clue."""
    if not hand_card_paths:
        return None

    best_card = None
    best_score = -1 # Using a simple score for now

    print(f"AI evaluating {len(hand_card_paths)} cards for clue: '{clue}'")

    # Simple approach: Ask for a match score for each card.
    # More complex: Ask the model to rank the cards.
    for card_path in hand_card_paths:
        base64_image = encode_image(card_path)
        if not base64_image:
            continue

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"On a scale of 1 (poor match) to 5 (excellent match), how well does this image fit the Dixit clue: '{clue}'? Respond with only the number (1, 2, 3, 4, or 5)."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            "max_tokens": 5 # Expecting just a single digit
        }

        response_text = _call_llama_api(payload)
        try:
            score = int(response_text) if response_text else 0
            print(f" - Card {os.path.basename(card_path)} scored: {score}")
            if score > best_score:
                best_score = score
                best_card = card_path
        except (ValueError, TypeError):
            print(f" - Could not parse score for card {os.path.basename(card_path)}. Response: '{response_text}'")
            # If scoring fails, maybe default to a low score or skip? For now, skip.

    # Fallback: If no card scored positively, pick randomly
    if best_card is None and hand_card_paths:
         print("AI couldn't determine best match via scoring, choosing randomly.")
         best_card = random.choice(hand_card_paths)

    return best_card


def guess_storyteller_card(board_card_paths, clue, player_card_path):
    """Guesses the storyteller's card from the board, avoiding the player's own card."""
    if not board_card_paths or len(board_card_paths) <= 1:
        return 0 # Cannot guess if only one card (must be storyteller's)

    possible_guesses = {} # index -> score

    print(f"AI guessing card for clue: '{clue}' (excluding own card: {os.path.basename(player_card_path)})")

    for i, card_path in enumerate(board_card_paths):
        # Skip the player's own card
        if card_path == player_card_path:
            print(f" - Skipping own card at index {i}: {os.path.basename(card_path)}")
            continue

        base64_image = encode_image(card_path)
        if not base64_image:
            continue

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                         {"type": "text", "text": f"On a scale of 1 (poor match) to 5 (excellent match), how well does this image fit the Dixit clue: '{clue}'? Respond with only the number (1, 2, 3, 4, or 5)."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                        }
                    ]
                }
            ],
             "max_tokens": 5
        }

        response_text = _call_llama_api(payload)
        try:
            score = int(response_text) if response_text else 0
            print(f" - Card at index {i} ({os.path.basename(card_path)}) scored: {score}")
            possible_guesses[i] = score
        except (ValueError, TypeError):
             print(f" - Could not parse score for card at index {i}. Response: '{response_text}'")
             possible_guesses[i] = 0 # Assign low score if parsing fails

    # Choose the index with the highest score
    if not possible_guesses:
        # Fallback: If all scores failed or only own card was present, guess randomly among others
        print("AI couldn't score any potential guesses, choosing randomly (excluding own card).")
        valid_indices = [idx for idx, path in enumerate(board_card_paths) if path != player_card_path]
        if not valid_indices: return 0 # Should not happen unless board has <= 1 card handled above
        return random.choice(valid_indices)
    else:
        # Find the index (key) with the maximum score (value)
        best_guess_index = max(possible_guesses, key=possible_guesses.get)
        print(f"AI highest score for index: {best_guess_index}")
        return best_guess_index

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