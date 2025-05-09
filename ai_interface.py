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
                    {"type": "text", "text": "You are an AI playing the card game Dixit. Your goal as the storyteller is to provide a short, one-sentence clue for the image below. \\n\\nDixit Rules Reminder: \\n- You get 0 points if *everyone* guesses your card (clue was too obvious).\\n- You get 0 points if *no one* guesses your card (clue was too obscure).\\n- You get 3 points if *some*, but not all, players guess your card. \\n\\nStrategy: Give an evocative, metaphorical, or abstract clue. Avoid literal descriptions. Aim for ambiguity so the clue *could* potentially relate to other cards, but still strongly connects to yours. Keep it concise."},\
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"} # Assuming PNG
                    }
                ]
            }
        ],
        "max_tokens": DEFAULT_MAX_TOKENS // 2 # Allow slightly more tokens for better clues
    }
    return _call_llama_api(payload)

def choose_card_for_clue(hand_card_paths, clue):
    """Chooses the best card *index* from the hand that matches the clue using a single API call."""
    if not hand_card_paths:
        return None

    print(f"AI evaluating {len(hand_card_paths)} cards for clue: '{clue}'")

    content_list = [
        {"type": "text", "text": f"You are an AI player in the game Dixit. The storyteller gave the clue: '{clue}'. Which of the following images from your hand (indexed 0 to {len(hand_card_paths)-1}) is the best fit for this clue? Your goal is to trick other players into guessing your card instead of the storyteller's. Respond with only the index number of your chosen card."}
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

    # Add text prompt first, explaining the goal and rules
    # Removed exclusion of player's own card here, will filter *after* AI response
    text_prompt = (
        f"You are an AI player in the game Dixit. The storyteller gave the clue: '{clue}'. "
        f"Below are {len(board_card_paths)} cards submitted by players (indexed 0 to {len(board_card_paths) - 1}). "
        f"One of these is the storyteller's original card. Your goal is to identify the storyteller's card. "
        f"Remember the storyteller wants to be ambiguous (not too obvious, not too obscure). "
        f"Consider the theme and feeling of the clue, not just literal matches. "
        f"Also, you submitted the card located at path '{os.path.basename(player_card_path)}' if it's provided; do not guess your own card. "
        f"Which card index (0 to {len(board_card_paths) - 1}) is MOST LIKELY the storyteller's original card based on the clue? "
        f"Respond with only the index number."
    )
    content_list.append({"type": "text", "text": text_prompt})

    # Add images, keeping track of original indices
    for i, card_path in enumerate(board_card_paths):
        # We still need to encode all images for the AI to see them
        base64_image = encode_image(card_path)
        if base64_image:
            image_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
            })
            # Store mapping from the prompt's image order to the original board index
            index_map[prompt_idx] = i
            prompt_idx += 1
        else:
            print(f"Warning: Could not encode image {card_path} for guessing prompt.")

    # Combine text and images
    content_list.extend(image_content)

    # Ensure there are images to guess from
    if not image_content:
        print("Warning: No valid images on the board to guess from.")
        # Fallback: Guess randomly among possible indices (excluding own if known)
        possible_indices = [i for i, fname in enumerate(board_card_paths) if fname != player_card_path]
        return random.choice(possible_indices) if possible_indices else 0

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": content_list}
        ],
        "max_tokens": 10 # Expecting just an index
    }

    response_text = _call_llama_api(payload)

    # Parse the index from the response (relative to the images shown in the prompt)
    parsed_prompt_index = _parse_ai_index_response(response_text, prompt_idx) # Use prompt_idx as the upper bound

    # Fallback strategy
    if parsed_prompt_index is None:
        print(f"AI failed to provide a valid index. Choosing randomly (excluding own).")
        possible_indices = [i for i, path in enumerate(board_card_paths) if path != player_card_path]
        return random.choice(possible_indices) if possible_indices else 0 # Return random valid index

    # Convert the parsed index (from the AI prompt order) back to the original board index
    original_guess_index = index_map.get(parsed_prompt_index)

    if original_guess_index is None:
        print(f"Error: Could not map parsed index {parsed_prompt_index} back to original board index. Choosing randomly.")
        possible_indices = [i for i, path in enumerate(board_card_paths) if path != player_card_path]
        return random.choice(possible_indices) if possible_indices else 0

    # Final check: Ensure the AI didn't guess its own card (even though instructed not to)
    if board_card_paths[original_guess_index] == player_card_path:
        print(f"Warning: AI guess ({original_guess_index}) matched its own card ({os.path.basename(player_card_path)}). Re-choosing randomly.")
        possible_indices = [i for i, path in enumerate(board_card_paths) if path != player_card_path]
        return random.choice(possible_indices) if possible_indices else 0 # Return random valid index (excluding own)

    print(f"AI guessed original index: {original_guess_index}")
    return original_guess_index


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