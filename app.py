import streamlit as st
import os
import time
import random
import threading
import queue # Using queue for thread-safe result collection
from dotenv import load_dotenv

# Assuming game.py and its classes (Game, Player) are in the same directory
from game import Game, Player
# Import AI functions needed for direct calls if any (though most are in Player now)
from ai_interface import encode_image # Might need for displaying images if paths change

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

# Removed create_dummy_cards as it's handled in Game.__init__

# --- Streamlit App ---

st.set_page_config(layout="wide")
st.title("Dixit Game with Llama AI (Parallel)")

# Load environment variables (needed for ai_interface)
load_dotenv()

# Check for API key early
if not os.getenv("LLAMA_API_KEY"):
    st.error("Error: LLAMA_API_KEY not found in environment variables. Please create a .env file with your API key.")
    st.stop()

# Initialize game state in session state if it doesn't exist
if 'game' not in st.session_state:
    st.session_state.game = None
    st.session_state.game_over = False
    st.session_state.human_player_name = f"Human {DEFAULT_HUMAN_PLAYERS}" # Assume first player is human
    st.session_state.turn_phase = "setup" # setup, storyteller_clue, player_submit, player_guess, scoring
    st.session_state.message = "Starting Game Setup..."
    st.session_state.board_cards_info = [] # Store cards currently displayed for guessing [{player_name, card_filename}] # Renamed for clarity
    st.session_state.current_clue = ""
    st.session_state.player_actions = {} # Track submissions/guesses this turn {player_name: {action, card, clue?, guess_index?}}
    st.session_state.storyteller_selected_card_index = None # Track selected card index for human storyteller
    st.session_state.storyteller_submitted_card = None # Store the card filename submitted by storyteller
    st.session_state.human_submitted_card = None # Track card submitted by human this turn
    st.session_state.ai_log = [] # Log AI decisions
    st.session_state.turn_start_time = time.time() # Track turn time for logs
    st.session_state.ai_threads_running = False # Flag to prevent duplicate thread launches

def log_ai_action(message):
    """Adds a message to the AI log in session state."""
    turn_time = time.time() - st.session_state.get('turn_start_time', time.time())
    st.session_state.ai_log.append(f"[{turn_time:.1f}s] {message}")
    # Keep log size manageable
    st.session_state.ai_log = st.session_state.ai_log[-20:]

# --- Game Setup --- Moved card creation inside game init
if st.session_state.game is None and st.session_state.turn_phase == "setup":
    st.header("Game Setup")
    # Game __init__ now handles card check/creation
    try:
        player_names = initialize_players(DEFAULT_NUM_PLAYERS, DEFAULT_HUMAN_PLAYERS)
        # Pass the card directory to the Game constructor
        game = Game(player_names,
                        hand_size=DEFAULT_HAND_SIZE,
                        max_score=DEFAULT_MAX_SCORE,
                        cards_directory=DEFAULT_CARDS_DIR)
        st.session_state.game = game
        st.session_state.turn_phase = "turn_start"
        st.session_state.message = "Game Initialized. Starting first turn."
        st.session_state.turn_start_time = time.time() # Reset timer
        st.success("Game setup complete!")
        st.rerun() # Rerun to start the first turn
    except ValueError as e:
        st.error(f"Error initializing game: {e}")
        st.session_state.turn_phase = "error"
    except Exception as e:
        st.error(f"An unexpected error occurred during setup: {e}")
        import traceback
        st.code(traceback.format_exc())
        st.session_state.turn_phase = "error"


# --- Main Game Area --- (Reduced nesting)
if st.session_state.game is not None and not st.session_state.game_over:
    game: Game = st.session_state.game
    human_player: Player = next((p for p in game.players if p.name == st.session_state.human_player_name), None)
    storyteller: Player = game.players[game.storyteller_index]

    # --- Display General Game Info --- (Sidebar)
    with st.sidebar:
        st.header("Game State")
        st.write(f"**Storyteller:** {storyteller.name}")
        st.write(f"**Current Clue:** {st.session_state.current_clue}")
        st.write(f"**Deck Size:** {len(game.deck)}")
        st.write(f"**Discard Pile:** {len(game.discard_pile)}")

        st.header("Scores")
        scores = {p.name: p.score for p in game.players}
        st.dataframe(sorted(scores.items(), key=lambda item: item[1], reverse=True), column_config={"value": "Score"})

        st.header("AI Log")
        log_content = "\n".join(st.session_state.ai_log)
        st.text_area("Log", log_content, height=250, key="ai_log_display", disabled=True)

    # --- Display Message / Status --- (Main Area)
    st.info(st.session_state.message)

    # --- Display Human Player Hand --- (Main Area)
    if human_player:
        st.header(f"{human_player.name}'s Hand (Score: {human_player.score})")
        if not human_player.hand:
            st.warning("(Hand is empty)")
        else:
            # Determine card interaction states
            is_storyteller_selecting_card = st.session_state.turn_phase == "storyteller_clue" and storyteller == human_player and st.session_state.storyteller_selected_card_index is None
            is_human_submitting = st.session_state.turn_phase == "player_submit" and storyteller != human_player and human_player.name not in st.session_state.player_actions

            cols = st.columns(len(human_player.hand))
            for i, card_file in enumerate(human_player.hand):
                card_path = human_player._get_full_card_path(card_file)

                if os.path.exists(card_path):
                     with cols[i]:
                         st.image(card_path, caption=f"Card {i}: {card_file}", use_container_width=True)

                         # Storyteller: Button to select this card
                         if is_storyteller_selecting_card:
                             if st.button(f"Select Card {i}", key=f"select_clue_card_{i}"):
                                  st.session_state.storyteller_selected_card_index = i
                                  st.session_state.message = f"Selected card {i}. Now enter your clue below."
                                  st.rerun()

                         # Non-Storyteller: Button to submit this card
                         elif is_human_submitting:
                              # Disable button if AI threads are running to prevent race conditions
                              if st.button(f"Submit Card {i}", key=f"submit_{i}", disabled=st.session_state.ai_threads_running):
                                   submitted_card = human_player.hand[i]
                                   st.session_state.human_submitted_card = submitted_card # Store for later removal
                                   st.session_state.player_actions[human_player.name] = {'action': 'submit', 'card': submitted_card}
                                   st.session_state.message = f"{human_player.name} submitted {submitted_card}. Waiting for others..."
                                   log_ai_action(f"Human submitted card '{submitted_card}'.")
                                   # Trigger check/AI phase on rerun
                                   st.rerun()
                else:
                    with cols[i]:
                        st.warning(f"Card image not found: {card_path}")

    # --- Handle Game Phases --- (Main Area)

    # --- Turn Start --- Trigger AI Storyteller or Human Clue Phase
    if st.session_state.turn_phase == "turn_start":
        log_ai_action(f"Turn start. Storyteller: {storyteller.name}")
        st.session_state.message = f"Turn Start: {storyteller.name} is the storyteller."
        st.session_state.board_cards_info = []
        st.session_state.current_clue = ""
        st.session_state.player_actions = {}
        st.session_state.storyteller_selected_card_index = None
        st.session_state.storyteller_submitted_card = None
        st.session_state.human_submitted_card = None

        if storyteller == human_player:
            st.session_state.turn_phase = "storyteller_clue"
            st.session_state.message = f"Your turn, {storyteller.name}. Select a card from your hand to start."
            log_ai_action("Human storyteller turn.")
            st.rerun()
        else:
            # AI Storyteller Action
            st.session_state.message = f"{storyteller.name} (AI) is thinking of a clue..."
            with st.spinner(f"{storyteller.name} (AI) is choosing a card and generating a clue..."):
                 clue, chosen_card_filename = storyteller.provide_clue() # This now calls the AI

            if clue and chosen_card_filename:
                 log_ai_action(f"{storyteller.name} chose card '{chosen_card_filename}' and gave clue: '{clue}'")
                 st.session_state.current_clue = clue
                 st.session_state.storyteller_submitted_card = chosen_card_filename # Store the card filename
                 st.session_state.player_actions[storyteller.name] = {'action': 'clue', 'card': chosen_card_filename, 'clue': clue}
                 st.session_state.message = f"{storyteller.name} (AI) gave clue: '{clue}'. Waiting for players to submit cards."
                 st.session_state.turn_phase = "player_submit"
            else:
                 # Handle AI failure (e.g., no cards, API error)
                 st.warning(f"{storyteller.name} (AI) could not provide a clue or card. Skipping turn.")
                 log_ai_action(f"Error: {storyteller.name} (AI) failed provide_clue(). Skipping turn.")
                 # Advance game state manually if provide_clue failed
                 game._advance_storyteller()
                 game._replenish_hands()
                 st.session_state.turn_phase = "turn_start" # Restart turn logic

            st.rerun()

    # --- Human Storyteller Input Phase --- (Only if human is storyteller)
    if st.session_state.turn_phase == "storyteller_clue" and storyteller == human_player:
        if st.session_state.storyteller_selected_card_index is not None:
            selected_index = st.session_state.storyteller_selected_card_index

            if 0 <= selected_index < len(human_player.hand):
                selected_card_file = human_player.hand[selected_index]
                card_path = human_player._get_full_card_path(selected_card_file)

                st.subheader("Provide Clue for Selected Card")
                st.write(f"You selected Card {selected_index}: {selected_card_file}")
                if os.path.exists(card_path):
                    st.image(card_path, width=150)
                else:
                    st.warning(f"Image not found: {card_path}")

                with st.form(key='clue_input_form'):
                    clue_input = st.text_input("Enter your clue:", key="clue_text")
                    submit_clue_button = st.form_submit_button(label='Submit Clue')

                    if submit_clue_button:
                        if not clue_input:
                            st.warning("Clue cannot be empty.")
                        else:
                            # Don't pop card yet, just record it
                            chosen_card_filename = human_player.hand[selected_index]
                            st.session_state.current_clue = clue_input
                            st.session_state.storyteller_submitted_card = chosen_card_filename # Store card
                            st.session_state.player_actions[storyteller.name] = {'action': 'clue', 'card': chosen_card_filename, 'clue': clue_input}
                            st.session_state.message = f"{storyteller.name} gave clue: '{clue_input}'. Waiting for players to submit cards."
                            st.session_state.turn_phase = "player_submit"
                            st.session_state.storyteller_selected_card_index = None # Reset UI state
                            log_ai_action(f"Human storyteller gave clue: '{clue_input}' for card '{chosen_card_filename}'")
                            st.rerun()
            else:
                 st.warning("Selected card index is no longer valid. Please select again.")
                 log_ai_action("Error: Human storyteller selected invalid card index.")
                 st.session_state.storyteller_selected_card_index = None
                 st.rerun()
        else:
             # Wait for human to click a card selection button
             pass

    # --- Player Card Submission Phase --- (Trigger AI submissions)
    if st.session_state.turn_phase == "player_submit":
        storyteller_action = st.session_state.player_actions.get(storyteller.name)
        if not storyteller_action or storyteller_action['action'] != 'clue':
             st.warning("Waiting for storyteller to provide clue and card...")
        else:
            num_submissions_needed = len(game.players) - 1
            num_submitted = sum(1 for action in st.session_state.player_actions.values() if action.get('action') == 'submit')

            ai_action_taken = False
            # Trigger AI submissions
            for player in game.players:
                 if player != storyteller and player.is_ai and player.name not in st.session_state.player_actions:
                      st.write(f"{player.name} (AI) is choosing a card for clue: '{st.session_state.current_clue}'...")
                      with st.spinner(f"{player.name} (AI) is selecting a card..."): # Show spinner
                           submitted_card_filename = player.submit_card(st.session_state.current_clue) # Calls AI
                      
                      if submitted_card_filename:
                           st.session_state.player_actions[player.name] = {'action': 'submit', 'card': submitted_card_filename}
                           st.write(f"{player.name} (AI) submitted a card.")
                           log_ai_action(f"{player.name} (AI) submitted card '{submitted_card_filename}' for clue '{st.session_state.current_clue}'")
                           num_submitted += 1
                           ai_action_taken = True
                      else:
                           # Handle AI having no cards or failing to submit
                           st.warning(f"{player.name} (AI) has no cards or failed to submit.")
                           log_ai_action(f"Warning: {player.name} (AI) failed submit_card() for clue '{st.session_state.current_clue}'")
                           # If AI cannot submit, treat as if they have submitted (or reduce needed count)
                           num_submissions_needed -= 1 # Or mark them as 'passed'
                           ai_action_taken = True # Still counts as an action processed

            # Only rerun if an AI actually did something to avoid infinite loops
            if ai_action_taken:
                 st.rerun()

            # Check completion only after AI actions are done for this cycle
            elif num_submitted >= num_submissions_needed:
                st.session_state.message = "All players submitted. Preparing board for guessing."
                log_ai_action("All players submitted cards.")
                # Collate cards for the board
                board = []
                if storyteller_action: # Storyteller card first
                     board.append({'player_name': storyteller.name, 'card_filename': storyteller_action['card']})
                
                for p_name, action in st.session_state.player_actions.items():
                      if action.get('action') == 'submit':
                           board.append({'player_name': p_name, 'card_filename': action['card']})
                
                random.shuffle(board) # Shuffle submitted cards
                st.session_state.board_cards_info = board
                st.session_state.turn_phase = "player_guess"
                # Clear submit actions, keep clue action
                st.session_state.player_actions = {storyteller.name: storyteller_action}
                st.rerun()
            else:
                # Waiting for human or remaining AIs
                waiting_players = [p.name for p in game.players if p != storyteller and p.name not in st.session_state.player_actions]
                st.session_state.message = f"Waiting for submissions from: {', '.join(waiting_players)}"


    # --- Player Guessing Phase --- (Trigger AI guesses)
    if st.session_state.turn_phase == "player_guess":
        st.header(f"Guess the Card for Clue: '{st.session_state.current_clue}'")
        if not st.session_state.board_cards_info:
            st.warning("No cards on the board to guess.")
        else:
            board_filenames = [sub['card_filename'] for sub in st.session_state.board_cards_info]
            human_action = st.session_state.player_actions.get(human_player.name) if human_player else None
            human_has_guessed = human_action and human_action.get('action') == 'guess'

            cols = st.columns(len(st.session_state.board_cards_info))
            for i, submission_info in enumerate(st.session_state.board_cards_info):
                card_filename = submission_info['card_filename']
                submitter_name = submission_info['player_name']
                card_path = os.path.join(DEFAULT_CARDS_DIR, card_filename) # Use default dir

                is_human_card = human_player and submitter_name == human_player.name

                with cols[i]:
                    if os.path.exists(card_path):
                        st.image(card_path, caption=f"Card {i}", use_container_width=True)
                    else:
                        st.warning(f"Image not found: {card_path}")

                    # Guess button for human
                    can_human_guess = human_player and storyteller != human_player and not human_has_guessed
                    if can_human_guess and not is_human_card:
                        if st.button(f"Guess Card {i}", key=f"guess_{i}", disabled=st.session_state.ai_threads_running):
                                st.session_state.player_actions[human_player.name] = {'action': 'guess', 'guess_index': i}
                                st.session_state.message = f"{human_player.name} guessed Card {i}. Waiting for others..."
                                log_ai_action(f"Human guessed index {i} ({card_filename})")
                                st.rerun()
                    elif is_human_card:
                        st.caption("(Your Card)")
                    elif human_has_guessed and human_action['guess_index'] == i:
                        st.caption("(Your Guess)")
                    elif storyteller.name == submitter_name:
                        # Maybe add a subtle indicator later if needed for debugging?
                        pass # Don't reveal storyteller card yet

            # Check completion and trigger AI guesses
            num_guesses_needed = len(game.players) - 1
            num_guessed = sum(1 for action in st.session_state.player_actions.values() if action.get('action') == 'guess')

            ai_action_taken = False
            # Trigger AI guesses
            for player in game.players:
                if player.is_ai and player != storyteller and player.name not in st.session_state.player_actions:
                    st.write(f"{player.name} (AI) is guessing for clue: '{st.session_state.current_clue}'...")
                    # Find the card AI submitted to pass to guess_card method
                    ai_submitted_card_filename = None
                    for sub_info in st.session_state.board_cards_info:
                        if sub_info['player_name'] == player.name:
                            ai_submitted_card_filename = sub_info['card_filename']
                            break
                    if ai_submitted_card_filename is None:
                        st.error(f"Could not find the card submitted by AI {player.name} for guessing phase.")
                        log_ai_action(f"Error: Failed to find submitted card for AI {player.name} to guess.")
                        # Mark as guessed to avoid blocking? Or error out?
                        # For now, let it block and show the error.
                        continue
                    
                    with st.spinner(f"{player.name} (AI) is guessing..."):
                        guess_index = player.guess_card(board_filenames, st.session_state.current_clue, ai_submitted_card_filename) # Calls AI

                    if 0 <= guess_index < len(board_filenames):
                        st.session_state.player_actions[player.name] = {'action': 'guess', 'guess_index': guess_index}
                        st.write(f"{player.name} (AI) guessed Card {guess_index}.")
                        log_ai_action(f"{player.name} (AI) guessed index {guess_index} ({board_filenames[guess_index]}) for clue '{st.session_state.current_clue}'")
                        num_guessed += 1
                        ai_action_taken = True
                    else:
                        st.error(f"AI {player.name} returned an invalid guess index: {guess_index}")
                        log_ai_action(f"Error: AI {player.name} returned invalid guess index {guess_index}.")
                        # Mark as guessed to avoid blocking?
                        num_guesses_needed -= 1 # Treat as unable to guess
                        ai_action_taken = True

             # Rerun if an AI took action
            if ai_action_taken:
                st.rerun()

             # Check if ready to score
            elif num_guessed >= num_guesses_needed:
                st.session_state.message = "All players guessed. Calculating scores..."
                log_ai_action("All players guessed.")
                st.session_state.turn_phase = "scoring"
                st.rerun()
            else:
                # Waiting for human or remaining AIs
                waiting_players = [p.name for p in game.players if p != storyteller and p.name not in st.session_state.player_actions]
                st.session_state.message = f"Waiting for guesses from: {', '.join(waiting_players)}"


    # --- Scoring and Turn End Phase --- (Logic needs slight adjustment for failed actions)
    if st.session_state.turn_phase == "scoring":
        st.header("Scoring Round")
        storyteller_action = st.session_state.player_actions.get(storyteller.name)
        # Filter only *successful* guesses for scoring
        guesses_dict = {p_name: action['guess_index']
                        for p_name, action in st.session_state.player_actions.items()
                        if action.get('action') == 'guess' and action.get('guess_index') is not None}

        if storyteller_action and storyteller_action.get('action') == 'clue':
            storyteller_card_filename = storyteller_action.get('card')
            if not storyteller_card_filename:
                 st.error("Critical error: Storyteller action recorded but card filename missing.")
                 log_ai_action("Error: Storyteller card missing in action dict.")
                 st.session_state.turn_phase = "error"
                 st.rerun()

            # Prepare board info for scoring method (needs player objects)
            board_for_scoring = []
            player_map = {p.name: p for p in game.players}
            for submission_info in st.session_state.board_cards_info:
                player_obj = player_map.get(submission_info['player_name'])
                if player_obj:
                    # The Game._update_scores expects {'player': Player, 'card': CardFilename}
                    board_for_scoring.append({'player': player_obj, 'card': submission_info['card_filename']})
                else:
                    st.error(f"Could not find player object for {submission_info['player_name']} during scoring prep.")
                    st.session_state.turn_phase = "error"
                    st.rerun()

            # --- Reveal Who Submitted Which Card --- (Display)
            st.subheader("Card Submissions Revealed:")
            reveal_cols = st.columns(len(board_for_scoring))
            storyteller_card_index = -1
            for i, sub in enumerate(board_for_scoring):
                card_p = os.path.join(DEFAULT_CARDS_DIR, sub['card'])
                caption_text = f"Card {i}: {sub['player'].name}"
                if sub['player'] == storyteller:
                    caption_text += " (Storyteller)"
                    storyteller_card_index = i # Find the index for display
                with reveal_cols[i]:
                    if os.path.exists(card_p):
                        st.image(card_p, caption=caption_text, use_container_width=True)
                    else:
                        st.warning(f"Image missing: {card_p}")

            # --- Reveal Guesses --- (Display)
            st.subheader("Guesses & Results:")
            if storyteller_card_index == -1:
                st.error("Critical: Storyteller card index not found for revealing results.")
            else:
                for player_name, guess_idx in guesses_dict.items():
                    guessed_card_owner = board_for_scoring[guess_idx]['player'].name
                    is_correct = (guess_idx == storyteller_card_index)
                    result_emoji = "✅" if is_correct else "❌"
                    st.write(f"- {player_name} guessed Card {guess_idx} (submitted by {guessed_card_owner}) {result_emoji}")

            # --- Call the actual scoring --- (Logic)
            try:
                st.write("Calculating score updates...")
                original_game_board = game.board
                game.board = board_for_scoring # Temporarily set for scoring method
                storyteller_submission_for_scoring = {'player': storyteller, 'card': storyteller_card_filename}

                game._update_scores(storyteller_submission_for_scoring, guesses_dict)

                game.board = original_game_board # Restore original board state
                st.success("Scores updated! See sidebar.")
                log_ai_action("Scoring complete.")

                # Removed card popping here - Player methods now handle it during action

            except Exception as e:
                st.error(f"Error during scoring calculation: {e}")
                import traceback
                st.code(traceback.format_exc())
                log_ai_action(f"Error during scoring: {e}")
                st.session_state.turn_phase = "error"
                game.board = original_game_board
            finally:
                # This block runs whether scoring succeeded or raised an error (unless phase changed to error)
                if st.session_state.turn_phase != "error":
                    # Add all cards from the display board to the discard pile
                    discarded_cards = [sub['card'] for sub in board_for_scoring]
                    game.discard_pile.extend(discarded_cards)
                    st.session_state.board_cards_info = [] # Clear display board

                    game._replenish_hands()
                    game._advance_storyteller()

                    if game.is_game_over():
                        st.session_state.game_over = True
                        st.session_state.turn_phase = "game_end"
                        st.session_state.message = "Game Over!"
                        log_ai_action("Game Over.")
                    else:
                        st.session_state.turn_phase = "turn_start" # Ready for next turn
                        st.session_state.message = "Scoring complete. Ready for next turn."
                        st.session_state.turn_start_time = time.time() # Reset timer

                    # Short delay before rerunning
                    time.sleep(2) # Slightly shorter delay
                    st.rerun()
                # No else needed here: if phase is 'error', we just let the error state handle it

        else:
            st.error("Cannot score: Storyteller action missing or invalid.")
            log_ai_action("Error: Storyteller action missing for scoring.")
            st.session_state.turn_phase = "error"


# --- Game End --- (Display final results)
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
        log_ai_action("Restarting game.")
        # Clear session state to restart
        for key in list(st.session_state.keys()):
             if key != 'ai_log': # Optionally keep AI log across restarts
                  del st.session_state[key]
        st.rerun()

# --- Error State --- (Provide restart option)
if st.session_state.turn_phase == "error":
    st.error(f"An error occurred. Last message: {st.session_state.message}. Check console/log or restart.")
    if st.button("Restart Game"):
        log_ai_action("Restarting game due to error.")
        # Clear session state to restart
        for key in list(st.session_state.keys()):
            if key != 'ai_log': # Optionally keep AI log
                del st.session_state[key]
        st.rerun()