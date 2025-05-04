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
                if os.path.exists(card_path):
                     with cols[i % DEFAULT_HAND_SIZE]:
                         st.image(card_path, caption=f"{i}: {card_file}", use_container_width=True)
                         # Add buttons within the loop for actions related to specific cards
                         if st.session_state.turn_phase == "storyteller_clue" and storyteller == human_player:
                             # Need a form to get clue *then* choose card
                             pass # Defer complex actions to specific phase handling below
                         elif st.session_state.turn_phase == "player_submit" and storyteller != human_player:
                              # Button to submit this card
                              if st.button(f"Submit Card {i}", key=f"submit_{i}"):
                                   submitted_card = human_player.hand.pop(i)
                                   st.session_state.player_actions[human_player.name] = {'action': 'submit', 'card': submitted_card}
                                   st.session_state.message = f"{human_player.name} submitted {submitted_card}. Waiting for others..."
                                   # TODO: Trigger AI submissions if needed, then advance phase
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
        if storyteller == human_player:
            st.session_state.turn_phase = "storyteller_clue"
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
                 ai_chosen_card = storyteller.hand.pop(0)
                 st.session_state.current_clue = ai_clue
                 st.session_state.player_actions[storyteller.name] = {'action': 'clue', 'card': ai_chosen_card, 'clue': ai_clue}
                 st.session_state.message = f"{storyteller.name} (AI) gave clue: '{ai_clue}'. Waiting for players to submit cards."
                 st.session_state.turn_phase = "player_submit"
        st.rerun()

    # Human Storyteller Input Phase
    if st.session_state.turn_phase == "storyteller_clue" and storyteller == human_player:
        st.header("Provide Clue and Choose Card")
        with st.form(key='clue_form'):
            clue_input = st.text_input("Enter your clue:")
            card_index_input = st.number_input("Choose card index from your hand:", min_value=0, max_value=len(human_player.hand)-1 if human_player.hand else 0, step=1)
            submit_button = st.form_submit_button(label='Submit Clue and Card')

            if submit_button:
                if not clue_input:
                    st.warning("Clue cannot be empty.")
                elif not human_player.hand:
                    st.warning("Cannot submit, hand is empty.")
                elif 0 <= card_index_input < len(human_player.hand):
                    chosen_card = human_player.hand.pop(card_index_input)
                    st.session_state.current_clue = clue_input
                    st.session_state.player_actions[storyteller.name] = {'action': 'clue', 'card': chosen_card, 'clue': clue_input}
                    st.session_state.message = f"{storyteller.name} gave clue: '{clue_input}'. Waiting for players to submit cards."
                    st.session_state.turn_phase = "player_submit"
                    st.rerun()
                else:
                    st.warning("Invalid card index selected.")

    # Player Card Submission Phase (Human part handled by buttons above)
    if st.session_state.turn_phase == "player_submit":
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
                       # Mark AI as unable to submit if needed, or just decrement needed count?
                       # For now, assume they just don't submit if hand empty. Game logic might need adjustment.
                       num_submissions_needed -= 1 # Adjust needed count if AI has no cards

        if num_submitted >= num_submissions_needed:
            st.session_state.message = "All players submitted. Preparing board for guessing."
            # Collate cards for the board
            storyteller_action = st.session_state.player_actions.get(storyteller.name)
            if storyteller_action and storyteller_action['action'] == 'clue':
                 board = [{'player_name': storyteller.name, 'card': storyteller_action['card']}]
                 for p_name, action in st.session_state.player_actions.items():
                      if action['action'] == 'submit':
                           board.append({'player_name': p_name, 'card': action['card']})
                 
                 random.shuffle(board)
                 st.session_state.board_cards = board
                 st.session_state.turn_phase = "player_guess"
                 st.rerun()
            else:
                 st.error("Error: Storyteller action not found during submission phase.")
                 st.session_state.turn_phase = "error"


    # Player Guessing Phase
    if st.session_state.turn_phase == "player_guess":
        st.header(f"Guess the Card for Clue: '{st.session_state.current_clue}'")
        if not st.session_state.board_cards:
             st.warning("No cards on the board to guess.")
        else:
             cols = st.columns(len(st.session_state.board_cards))
             for i, submission in enumerate(st.session_state.board_cards):
                  card_path = os.path.join(DEFAULT_CARDS_DIR, submission['card'])
                  player_submitted_this = (human_player and submission['player_name'] == human_player.name)

                  with cols[i]:
                       if os.path.exists(card_path):
                            st.image(card_path, caption=f"Card {i}", use_container_width=True)
                       else:
                            st.warning(f"Image not found: {card_path}")
                       
                       is_human_turn_to_guess = (human_player and storyteller != human_player and human_player.name not in st.session_state.player_actions)
                       if is_human_turn_to_guess and not player_submitted_this:
                            if st.button(f"Guess Card {i}", key=f"guess_{i}"):
                                 st.session_state.player_actions[human_player.name] = {'action': 'guess', 'guess_index': i}
                                 st.session_state.message = f"{human_player.name} guessed Card {i}. Waiting for others..."
                                 st.rerun()
                       elif player_submitted_this:
                            st.caption("(Your Card)")

             # Check if all non-storytellers have guessed
             num_guesses_needed = len(game.players) - 1
             num_guessed = sum(1 for p_name, action in st.session_state.player_actions.items() if action['action'] == 'guess')

             # Trigger AI guesses
             for player in game.players:
                 if player != storyteller and player.is_ai and player.name not in st.session_state.player_actions:
                      st.write(f"{player.name} (AI) is guessing...")
                      time.sleep(0.5)
                      
                      ai_submitted_card_index = -1
                      for idx, sub in enumerate(st.session_state.board_cards):
                           if sub['player_name'] == player.name:
                                ai_submitted_card_index = idx
                                break
                                
                      possible_guesses = list(range(len(st.session_state.board_cards)))
                      if ai_submitted_card_index != -1:
                           try: # Avoid error if only 1 card somehow
                                possible_guesses.pop(ai_submitted_card_index)
                           except IndexError: pass
                      
                      if not possible_guesses: # Handle edge case
                           ai_guess_index = 0
                      else:
                           ai_guess_index = random.choice(possible_guesses) # Placeholder AI logic
                           
                      st.session_state.player_actions[player.name] = {'action': 'guess', 'guess_index': ai_guess_index}
                      st.write(f"{player.name} (AI) guessed Card {ai_guess_index}.")
                      num_guessed += 1

             # Check if ready to score
             if num_guessed >= num_guesses_needed:
                st.session_state.message = "All players guessed. Calculating scores..."
                st.session_state.turn_phase = "scoring"
                st.rerun()

    # Scoring and Turn End Phase
    if st.session_state.turn_phase == "scoring":
        st.header("Scoring Round")
        # Reconstruct necessary info for Game._update_scores
        # Note: This is awkward because the original _update_scores mutated state directly.
        # A better design would have _update_scores return score changes.
        # For now, we simulate the call by preparing args.

        storyteller_action = st.session_state.player_actions.get(storyteller.name)
        guesses_dict = {p_name: action['guess_index'] for p_name, action in st.session_state.player_actions.items() if action['action'] == 'guess'}

        if storyteller_action and storyteller_action['action'] == 'clue':
             storyteller_submission_sim = {'player': storyteller, 'card': storyteller_action['card']}
             
             # Temporarily reconstruct the board for the scoring function
             # This assumes board_cards still holds the shuffled list from the guessing phase
             board_for_scoring = []
             for submission_info in st.session_state.board_cards:
                  player_obj = next((p for p in game.players if p.name == submission_info['player_name']), None)
                  if player_obj:
                       board_for_scoring.append({'player': player_obj, 'card': submission_info['card']})
                  else:
                       st.error(f"Could not find player object for {submission_info['player_name']} during scoring prep.")
             
             game.board = board_for_scoring # Temporarily set game.board for scoring method
             
             # --- Call the actual scoring ---
             try:
                 # Use a container to capture print output from scoring if desired
                 # with st.spinner("Calculating scores..."):
                 #     with st_capture() as captured_prints: # Need a helper for this
                 #          game._update_scores(storyteller_submission_sim, guesses_dict)
                 # st.text("\n".join(captured_prints)) # Display scoring messages
                 
                 # Simpler: Just call it and show results after
                 game._update_scores(storyteller_submission_sim, guesses_dict)
                 st.success("Scores updated!")

             except Exception as e:
                  st.error(f"Error during scoring: {e}")
                  import traceback
                  st.code(traceback.format_exc())
             finally:
                 # Clean up state for next turn
                 game.discard_pile.extend([sub['card'] for sub in game.board])
                 game.board = [] # Clear board after scoring
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
                 time.sleep(2) 
                 st.rerun()

        else:
             st.error("Cannot score: Storyteller action missing.")
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