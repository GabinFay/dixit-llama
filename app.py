import streamlit as st
import os
import time
import random
from dotenv import load_dotenv

# Assuming game.py and its classes (Game, Player) are in the same directory
from game import Game

# --- Configuration ---
# These could be moved to config.py or set via UI elements later
DEFAULT_HAND_SIZE = 6
DEFAULT_MAX_SCORE = 30
DEFAULT_CARDS_DIR = "cards"
DEFAULT_NUM_PLAYERS = 4
DEFAULT_HUMAN_PLAYERS = 1 # For now, assume 1 human player

# --- Helper Functions (adapted from main.py) ---

def initialize_players(num_total=DEFAULT_NUM_PLAYERS, num_human=DEFAULT_HUMAN_PLAYERS):
    """Creates a list of player names, distinguishing human and AI."""
    if num_human > num_total:
        st.warning("Number of human players exceeds total players. Adjusting.")
        num_human = num_total
    players = []
    for i in range(num_human):
        players.append(f"Human {i+1}") # Assuming the first player(s) are human
    for i in range(num_total - num_human):
        players.append(f"AI {i+1}")
    return players

def create_dummy_cards(cards_dir, num_players, hand_size):
    """Creates dummy card files if the directory is missing or empty."""
    if not os.path.isdir(cards_dir) or not os.listdir(cards_dir):
        st.warning(f"Card directory '{cards_dir}' is missing or empty. Creating dummy files.")
        os.makedirs(cards_dir, exist_ok=True)
        num_dummy_cards = num_players * hand_size + (num_players * 5)
        for i in range(1, num_dummy_cards + 1):
            try:
                with open(os.path.join(cards_dir, f"{i:03d}.png"), 'w') as f:
                    f.write("") # Create empty files
            except IOError as e:
                st.error(f"Error creating dummy file {i:03d}.png: {e}")
                return False
        st.success(f"Created {num_dummy_cards} dummy card files.")
        return True
    return True

# --- Streamlit App ---

st.set_page_config(layout="wide")
st.title("Dixit Game with Llama (Simple UI)")

# Load environment variables (optional, for API keys later)
load_dotenv()

# Initialize game state in session state if it doesn't exist
if 'game' not in st.session_state:
    st.session_state.game = None
    st.session_state.game_over = False
    st.session_state.human_player_name = f"Human {DEFAULT_HUMAN_PLAYERS}" # Assume first player is human
    st.session_state.turn_phase = "setup" # setup, storyteller_clue, player_submit, player_guess, scoring
    st.session_state.message = "Starting Game Setup..."
    st.session_state.board_cards = [] # Store cards currently displayed for guessing [{player_name, card_path}]
    st.session_state.current_clue = ""
    st.session_state.player_actions = {} # Track submissions/guesses this turn
    st.session_state.storyteller_selected_card_index = None # Track selected card for storyteller

# --- Game Setup ---
if st.session_state.game is None and st.session_state.turn_phase == "setup":
    st.header("Game Setup")
    if create_dummy_cards(DEFAULT_CARDS_DIR, DEFAULT_NUM_PLAYERS, DEFAULT_HAND_SIZE):
        try:
            player_names = initialize_players(DEFAULT_NUM_PLAYERS, DEFAULT_HUMAN_PLAYERS)
            game = Game(player_names,
                          hand_size=DEFAULT_HAND_SIZE,
                          max_score=DEFAULT_MAX_SCORE,
                          cards_directory=DEFAULT_CARDS_DIR)
            st.session_state.game = game
            st.session_state.turn_phase = "turn_start"
            st.session_state.message = "Game Initialized. Starting first turn."
            st.rerun() # Rerun to start the first turn
        except ValueError as e:
            st.error(f"Error initializing game: {e}")
            st.session_state.turn_phase = "error"
        except Exception as e:
            st.error(f"An unexpected error occurred during setup: {e}")
            st.session_state.turn_phase = "error"
    else:
        st.error("Failed to ensure card directory exists. Please check permissions or manually create '/cards'.")
        st.session_state.turn_phase = "error"

# --- Main Game Area ---
if st.session_state.game is not None and not st.session_state.game_over:
    game = st.session_state.game
    human_player = next((p for p in game.players if p.name == st.session_state.human_player_name), None)
    storyteller = game.players[game.storyteller_index]

    # --- Display General Game Info ---
    st.sidebar.header("Game State")
    st.sidebar.write(f"**Storyteller:** {storyteller.name}")
    st.sidebar.write(f"**Current Clue:** {st.session_state.current_clue}")
    st.sidebar.write(f"**Deck Size:** {len(game.deck)}")
    st.sidebar.write(f"**Discard Pile:** {len(game.discard_pile)}")

    st.sidebar.header("Scores")
    scores = {p.name: p.score for p in game.players}
    st.sidebar.dataframe(sorted(scores.items(), key=lambda item: item[1], reverse=True), column_config={"value": "Score"})

    # --- Display Message / Status ---
    st.info(st.session_state.message)

    # --- Display Human Player Hand ---
    if human_player:
        st.header(f"{human_player.name}'s Hand")
        if not human_player.hand:
            st.write("(Hand is empty)")
        else:
            cols = st.columns(DEFAULT_HAND_SIZE)
            for i, card_file in enumerate(human_player.hand):
                card_path = os.path.join(DEFAULT_CARDS_DIR, card_file)
                is_storyteller_phase = st.session_state.turn_phase == "storyteller_clue" and storyteller == human_player
                is_submit_phase = st.session_state.turn_phase == "player_submit" and storyteller != human_player
                
                if os.path.exists(card_path):
                     with cols[i % DEFAULT_HAND_SIZE]:
                         st.image(card_path, caption=f"Card {i}: {card_file}", use_container_width=True)
                         # Add buttons for relevant actions
                         
                         # Storyteller: Button to select this card
                         if is_storyteller_phase and st.session_state.storyteller_selected_card_index is None:
                             if st.button(f"Use Card {i} for Clue", key=f"select_clue_card_{i}"):
                                  st.session_state.storyteller_selected_card_index = i
                                  st.session_state.message = f"Selected card {i}. Now enter your clue below."
                                  st.rerun()
                         
                         # Non-Storyteller: Button to submit this card
                         elif is_submit_phase:
                              if st.button(f"Submit Card {i}", key=f"submit_{i}"):
                                   submitted_card = human_player.hand.pop(i)
                                   st.session_state.player_actions[human_player.name] = {'action': 'submit', 'card': submitted_card}
                                   st.session_state.message = f"{human_player.name} submitted {submitted_card}. Waiting for others..."
                                   # Need logic to check if all players submitted and advance phase
                                   st.rerun()
                else:
                    with cols[i % DEFAULT_HAND_SIZE]:
                        st.warning(f"Card image not found: {card_path}")

    # --- Handle Game Phases ---

    # Start of a new turn
    if st.session_state.turn_phase == "turn_start":
        st.session_state.message = f"Turn Start: {storyteller.name} is the storyteller."
        st.session_state.board_cards = []
        st.session_state.current_clue = ""
        st.session_state.player_actions = {}
        st.session_state.storyteller_selected_card_index = None # Reset selection
        
        if storyteller == human_player:
            st.session_state.turn_phase = "storyteller_clue"
            st.session_state.message = f"Your turn, {storyteller.name}. Select a card from your hand to start."
        else:
            # AI Storyteller Action
            st.session_state.message = f"{storyteller.name} (AI) is thinking of a clue..."
            # Simulate AI action (replace with actual AI call later)
            time.sleep(1)
            if not storyteller.hand:
                 st.warning(f"{storyteller.name} has no cards. Skipping turn.")
                 game._advance_storyteller()
                 game._replenish_hands()
                 st.session_state.turn_phase = "turn_start" # Start next turn immediately
            else:
                 ai_clue = f"AI Clue for {storyteller.hand[0].split('.')[0]}" # Placeholder
                 ai_chosen_card = storyteller.hand.pop(0) # AI chooses first card
                 st.session_state.current_clue = ai_clue
                 st.session_state.player_actions[storyteller.name] = {'action': 'clue', 'card': ai_chosen_card, 'clue': ai_clue}
                 st.session_state.message = f"{storyteller.name} (AI) gave clue: '{ai_clue}'. Waiting for players to submit cards."
                 st.session_state.turn_phase = "player_submit"
        st.rerun()

    # Human Storyteller Input Phase (After selecting card)
    if st.session_state.turn_phase == "storyteller_clue" and storyteller == human_player:
        # Check if a card has been selected
        if st.session_state.storyteller_selected_card_index is not None:
            selected_index = st.session_state.storyteller_selected_card_index
            
            # Ensure index is still valid (e.g., hand didn't change unexpectedly)
            if 0 <= selected_index < len(human_player.hand):
                selected_card_file = human_player.hand[selected_index]
                card_path = os.path.join(DEFAULT_CARDS_DIR, selected_card_file)
                
                st.header("Provide Clue for Selected Card")
                st.write(f"You selected Card {selected_index}:")
                if os.path.exists(card_path):
                    st.image(card_path, width=150) # Show smaller image of selected card
                else:
                    st.warning(f"Image not found: {card_path}")

                with st.form(key='clue_input_form'):
                    clue_input = st.text_input("Enter your clue:", key="clue_text")
                    submit_clue_button = st.form_submit_button(label='Submit Clue')

                    if submit_clue_button:
                        if not clue_input:
                            st.warning("Clue cannot be empty.")
                        else:
                            # Use the stored index to get the card and remove it
                            chosen_card = human_player.hand.pop(selected_index)
                            st.session_state.current_clue = clue_input
                            st.session_state.player_actions[storyteller.name] = {'action': 'clue', 'card': chosen_card, 'clue': clue_input}
                            st.session_state.message = f"{storyteller.name} gave clue: '{clue_input}'. Waiting for players to submit cards."
                            st.session_state.turn_phase = "player_submit"
                            st.session_state.storyteller_selected_card_index = None # Reset selection state
                            st.rerun()
            else:
                 st.warning("Selected card index is no longer valid. Please select again.")
                 st.session_state.storyteller_selected_card_index = None # Reset
                 st.rerun() # Rerun to show card selection buttons again
        else:
             # Message is already set during turn_start to prompt selection
             pass # Wait for user to click a card selection button

    # Player Card Submission Phase (Human part handled by buttons above)
    if st.session_state.turn_phase == "player_submit":
        # Check if storyteller has submitted their clue card info
        storyteller_action = st.session_state.player_actions.get(storyteller.name)
        if not storyteller_action or storyteller_action['action'] != 'clue':
             # This shouldn't happen if logic is correct, but acts as a failsafe
             st.warning("Waiting for storyteller to provide clue and card...")
             # Prevent AI from acting until storyteller is done
        else:
            # Check if all non-storytellers have submitted
            num_submissions_needed = len(game.players) - 1
            num_submitted = sum(1 for p_name, action in st.session_state.player_actions.items() if action['action'] == 'submit')

            # Trigger AI submissions if they haven't acted yet
            for player in game.players:
                 if player != storyteller and player.is_ai and player.name not in st.session_state.player_actions:
                      st.write(f"{player.name} (AI) is choosing a card...")
                      time.sleep(0.5) # Short delay for effect
                      if player.hand:
                           ai_submitted_card = player.hand.pop(0) # Placeholder AI logic
                           st.session_state.player_actions[player.name] = {'action': 'submit', 'card': ai_submitted_card}
                           st.write(f"{player.name} (AI) submitted a card.")
                           num_submitted += 1
                      else:
                           st.warning(f"{player.name} (AI) has no cards to submit.")
                           num_submissions_needed -= 1 # Adjust needed count if AI has no cards

            if num_submitted >= num_submissions_needed:
                st.session_state.message = "All players submitted. Preparing board for guessing."
                # Collate cards for the board (using the already stored storyteller card)
                board = [{'player_name': storyteller.name, 'card': storyteller_action['card']}]
                for p_name, action in st.session_state.player_actions.items():
                      if action['action'] == 'submit':
                           board.append({'player_name': p_name, 'card': action['card']})

                random.shuffle(board)
                st.session_state.board_cards = board
                st.session_state.turn_phase = "player_guess"
                # Reset player actions for the guessing phase (keep storyteller clue info)
                st.session_state.player_actions = {storyteller.name: storyteller_action} 
                st.rerun()
            else:
                # Message should already indicate waiting for submissions
                pass


    # Player Guessing Phase
    if st.session_state.turn_phase == "player_guess":
        st.header(f"Guess the Card for Clue: '{st.session_state.current_clue}'")
        if not st.session_state.board_cards:
             st.warning("No cards on the board to guess.")
        else:
             cols = st.columns(len(st.session_state.board_cards))
             human_has_guessed = human_player and human_player.name in st.session_state.player_actions and st.session_state.player_actions[human_player.name]['action'] == 'guess'
             
             for i, submission in enumerate(st.session_state.board_cards):
                  card_path = os.path.join(DEFAULT_CARDS_DIR, submission['card'])
                  player_submitted_this = (human_player and submission['player_name'] == human_player.name)

                  with cols[i]:
                       if os.path.exists(card_path):
                            st.image(card_path, caption=f"Card {i}", use_container_width=True)
                       else:
                            st.warning(f"Image not found: {card_path}")
                       
                       is_human_turn_to_guess = (human_player and storyteller != human_player and not human_has_guessed)
                       
                       if is_human_turn_to_guess and not player_submitted_this:
                            if st.button(f"Guess Card {i}", key=f"guess_{i}"):
                                 # Record the guess action
                                 st.session_state.player_actions[human_player.name] = {'action': 'guess', 'guess_index': i}
                                 st.session_state.message = f"{human_player.name} guessed Card {i}. Waiting for others..."
                                 st.rerun()
                       elif player_submitted_this:
                            st.caption("(Your Card)")
                       elif human_has_guessed and st.session_state.player_actions[human_player.name]['guess_index'] == i:
                            st.caption("(Your Guess)")


             # Check if all non-storytellers have guessed
             num_guesses_needed = len(game.players) - 1
             num_guessed = sum(1 for p_name, action in st.session_state.player_actions.items() if action.get('action') == 'guess') # Use .get()

             # Trigger AI guesses if they haven't guessed yet
             ai_action_taken_this_step = False
             for player in game.players:
                 # Check if player is AI, not the storyteller, and hasn't guessed yet
                 if player.is_ai and player != storyteller and player.name not in st.session_state.player_actions:
                      st.write(f"{player.name} (AI) is guessing...")
                      ai_action_taken_this_step = True
                      time.sleep(0.5)
                      
                      # Find the index of the card the AI submitted (if any on the board)
                      ai_submitted_card_index = -1
                      for idx, sub in enumerate(st.session_state.board_cards):
                           if sub['player_name'] == player.name:
                                ai_submitted_card_index = idx
                                break
                                
                      # AI cannot guess its own card
                      possible_guesses = list(range(len(st.session_state.board_cards)))
                      if ai_submitted_card_index != -1:
                           try: # Avoid error if only 1 card or index out of bounds
                                possible_guesses.pop(ai_submitted_card_index)
                           except IndexError: pass
                      
                      # Make a random guess from the remaining cards
                      if not possible_guesses: # Handle edge case where only AI's card is left (shouldn't happen in normal play)
                           ai_guess_index = 0 # Just guess the first card
                           st.warning(f"AI {player.name} had no valid guess options!")
                      else:
                           ai_guess_index = random.choice(possible_guesses) # Placeholder AI logic
                           
                      # Record the AI's guess action
                      st.session_state.player_actions[player.name] = {'action': 'guess', 'guess_index': ai_guess_index}
                      st.write(f"{player.name} (AI) guessed Card {ai_guess_index}.")
                      num_guessed += 1

             # Rerun if an AI took action to update the display before checking completion
             if ai_action_taken_this_step:
                  st.rerun()

             # Check if ready to score (only after confirming no more AI actions this step)
             elif num_guessed >= num_guesses_needed:
                st.session_state.message = "All players guessed. Calculating scores..."
                st.session_state.turn_phase = "scoring"
                st.rerun()

    # Scoring and Turn End Phase
    if st.session_state.turn_phase == "scoring":
        st.header("Scoring Round")
        # Reconstruct necessary info for Game._update_scores
        storyteller_action = st.session_state.player_actions.get(storyteller.name)
        # Extract guesses ensuring we only get 'guess' actions
        guesses_dict = {p_name: action['guess_index'] 
                        for p_name, action in st.session_state.player_actions.items() 
                        if action.get('action') == 'guess'} # Use .get()

        if storyteller_action and storyteller_action.get('action') == 'clue':
             # Storyteller info needed for scoring
             storyteller_submission_sim = {'player': storyteller, 'card': storyteller_action['card']}
             
             # Board info needed for scoring (cards and who submitted them)
             board_for_scoring = []
             player_map = {p.name: p for p in game.players} # Map names to player objects for efficiency
             for submission_info in st.session_state.board_cards:
                  player_obj = player_map.get(submission_info['player_name'])
                  if player_obj:
                       board_for_scoring.append({'player': player_obj, 'card': submission_info['card']})
                  else:
                       st.error(f"Could not find player object for {submission_info['player_name']} during scoring prep.")
                       st.session_state.turn_phase = "error" # Halt on critical error
                       st.rerun()
             
             # Temporarily set game.board for the scoring method
             # Ensure this doesn't cause issues if scoring fails midway
             original_board = game.board
             game.board = board_for_scoring 
             
             # --- Reveal Who Submitted Which Card ---
             st.subheader("Card Submissions Revealed:")
             reveal_cols = st.columns(len(game.board))
             for i, sub in enumerate(game.board):
                  card_p = os.path.join(DEFAULT_CARDS_DIR, sub['card'])
                  caption_text = f"Card {i}: {sub['player'].name}"
                  if sub['player'] == storyteller:
                       caption_text += " (Storyteller)"
                  with reveal_cols[i]:
                       if os.path.exists(card_p):
                            st.image(card_p, caption=caption_text, use_container_width=True)
                       else:
                            st.warning(f"Image missing: {card_p}")

             # --- Reveal Guesses ---
             st.subheader("Guesses:")
             for player_name, guess_idx in guesses_dict.items():
                  guessed_card_owner = game.board[guess_idx]['player'].name
                  st.write(f"- {player_name} guessed Card {guess_idx} (submitted by {guessed_card_owner})")


             # --- Call the actual scoring ---
             try:
                 st.write("Calculating score updates...")
                 game._update_scores(storyteller_submission_sim, guesses_dict)
                 st.success("Scores updated!")

             except Exception as e:
                  st.error(f"Error during scoring calculation: {e}")
                  import traceback
                  st.code(traceback.format_exc())
                  st.session_state.turn_phase = "error" # Halt on error
             finally:
                 # Clean up state for next turn IF scoring didn't set error phase
                 if st.session_state.turn_phase != "error":
                     # Add all cards from the temporary board to the discard pile
                     game.discard_pile.extend([sub['card'] for sub in game.board])
                     game.board = [] # Clear the temporary board representation
                     
                     game._replenish_hands()
                     game._advance_storyteller()
                     
                     if game.is_game_over():
                          st.session_state.game_over = True
                          st.session_state.turn_phase = "game_end"
                          st.session_state.message = "Game Over!"
                     else:
                          st.session_state.turn_phase = "turn_start" # Ready for next turn
                          st.session_state.message = "Scoring complete. Ready for next turn."
                     
                     # Short delay before rerunning for next turn or game end screen
                     time.sleep(3) # Slightly longer to see results
                     st.rerun()
                 else:
                      game.board = original_board # Restore original board state if error occurred


        else:
             st.error("Cannot score: Storyteller action missing or invalid.")
             st.session_state.turn_phase = "error"


# --- Game End ---
if st.session_state.game_over:
    st.balloons()
    st.header("GAME OVER!")
    st.subheader("Final Scores:")
    final_scores = {p.name: p.score for p in st.session_state.game.players}
    st.dataframe(sorted(final_scores.items(), key=lambda item: item[1], reverse=True), column_config={"value": "Score"})

    winners = st.session_state.game.get_winner()
    if winners:
        st.success(f"Winner(s): {', '.join(winners)}")
    else:
        st.info("It's a draw or game ended unexpectedly!")

    if st.button("Play Again?"):
        # Clear session state to restart
        for key in list(st.session_state.keys()):
             del st.session_state[key]
        st.rerun()

# --- Error State ---
if st.session_state.turn_phase == "error":
     st.error(f"An error occurred. Last message: {st.session_state.message}. Please check logs or restart.")
     if st.button("Restart Game"):
          # Clear session state to restart
          for key in list(st.session_state.keys()):
                del st.session_state[key]
          st.rerun()