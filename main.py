import os
import random
import time
from dotenv import load_dotenv

from game import Game # Player is used internally by Game
# Placeholder imports - not needed if main only calls game.play_turn
# from llama_api import get_clue_from_llama, get_guess_from_llama

# Configuration (can also be moved to config.py and imported)
DEFAULT_HAND_SIZE = 6
DEFAULT_MAX_SCORE = 30 # Set lower (e.g., 10) for faster testing
DEFAULT_CARDS_DIR = "cards"
DEFAULT_NUM_PLAYERS = 4 # Including AI (e.g., 1 Human, 3 AI)
DEFAULT_HUMAN_PLAYERS = 1

def initialize_players(num_total=DEFAULT_NUM_PLAYERS, num_human=DEFAULT_HUMAN_PLAYERS):
    """Creates a list of player names, distinguishing human and AI."""
    if num_human > num_total:
        print("Warning: Number of human players exceeds total players. Adjusting.")
        num_human = num_total
        
    players = []
    for i in range(num_human):
        players.append(f"Human {i+1}")
    for i in range(num_total - num_human):
        players.append(f"AI {i+1}")
    return players

def create_dummy_cards(cards_dir, num_players, hand_size):
    """Creates dummy card files if the directory is missing or empty."""
    print(f"Checking for card directory: {cards_dir}")
    if not os.path.isdir(cards_dir) or not os.listdir(cards_dir):
        print(f"Card directory '{cards_dir}' is missing or empty.")
        print(f"Creating dummy card directory and files for testing.")
        os.makedirs(cards_dir, exist_ok=True)
        # Ensure enough cards for initial deal + a few turns
        num_dummy_cards = num_players * hand_size + (num_players * 5) # Heuristic for buffer
        print(f"Creating {num_dummy_cards} dummy card files...")
        for i in range(1, num_dummy_cards + 1):
            try:
                with open(os.path.join(cards_dir, f"{i:03d}.png"), 'w') as f:
                    f.write("dummy image data") # Create empty files
            except IOError as e:
                 print(f"Error creating dummy file {i:03d}.png: {e}")
                 # Decide if we should stop or continue
                 return False # Indicate failure
        print(f"Dummy files created successfully.")
        return True
    else:
        print("Card directory exists and is not empty.")
        return True # Indicate success (directory already exists)

def main():
    load_dotenv() # Load .env file for potential API keys

    # --- Configuration --- 
    # You can adjust these values for testing
    num_players = DEFAULT_NUM_PLAYERS
    num_human = DEFAULT_HUMAN_PLAYERS
    hand_size = DEFAULT_HAND_SIZE
    max_score = DEFAULT_MAX_SCORE
    cards_dir = DEFAULT_CARDS_DIR

    # --- Setup ---  
    if not create_dummy_cards(cards_dir, num_players, hand_size):
         print("Failed to create dummy cards. Exiting.")
         return

    try:
        player_names = initialize_players(num_players, num_human)
        game = Game(player_names, 
                      hand_size=hand_size, 
                      max_score=max_score, 
                      cards_directory=cards_dir)
    except ValueError as e:
         print(f"Error initializing game: {e}")
         return
    except Exception as e:
        print(f"An unexpected error occurred during setup: {e}")
        return

    print("\n--- Starting Dixit Game --- ")
    print(f"Players: {', '.join(player_names)}")
    print(f"Playing to {max_score} points.")
    game.print_scores()

    # --- Game Loop --- 
    turn = 1
    try:
        while not game.is_game_over():
            print(f"\n=================== Turn {turn} ===================")
            game.play_turn() # The Game class now handles the full turn logic
            turn += 1
            # Add a small delay or prompt to continue for readability
            if num_human > 0:
                 input("Press Enter to continue to the next turn...")
            else:
                 time.sleep(2) # Short pause if only AI players
                 
    except KeyboardInterrupt:
        print("\nGame interrupted by user. Exiting.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the game: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
    finally:
         # --- Game End --- 
         print("\n=================== GAME OVER ===================")
         game.print_scores()
         winners = game.get_winner()
         if winners:
             print(f"\nWinner(s): {', '.join(winners)}")
         else:
             # This might happen if game ends due to error or interruption before scoring
             print("\nGame ended without a clear winner.")

if __name__ == "__main__":
    # Added import here as it's only needed for main execution flow pause
    import time 
    main() 