# Basic configuration for the Dixit game

# --- Game Rules ---
NUM_PLAYERS = 4       # Total number of players (including AI)
HUMAN_PLAYERS = 1     # Number of human players (assuming they are players 0 to HUMAN_PLAYERS-1)
HAND_SIZE = 6         # Number of cards per player
MAX_SCORE = 30        # Score to reach to win the game

# --- File Paths ---
CARDS_DIRECTORY = "cards/"  # Path to the directory containing card images

# --- AI Configuration (Placeholders) ---
# LLAMA_MODEL = "llama-4-vision-preview" # Example model identifier
# Add other Llama API related configs if needed

# --- Environment Variables (Loaded via llama_api.py or main.py) ---
# Example: Ensure you have a .env file with LLAMA_API_KEY=your_key
# API keys and secrets should NOT be stored directly in this file. 