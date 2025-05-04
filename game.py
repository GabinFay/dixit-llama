import random
import os
import time # Added for slight delay in AI turns
# from config import HAND_SIZE, MAX_SCORE, CARDS_DIRECTORY # Assuming config.py exists

# Import AI functions
from ai_interface import generate_clue_for_image, choose_card_for_clue, guess_storyteller_card

# Placeholder for card representation (e.g., image file paths)
Card = str

class Player:
    def __init__(self, name, is_ai=False, cards_dir="cards"):
        self.name = name
        self.score = 0
        self.hand: list[Card] = [] # List of card filenames (e.g., "001.png")
        self.is_ai = is_ai
        self.cards_dir = cards_dir # Store cards directory path

    def _get_full_card_path(self, card_filename):
        """Helper to get the full path to a card image."""
        return os.path.join(self.cards_dir, card_filename)

    def _display_hand(self):
        print(f"{self.name}'s hand:")
        if not self.hand:
            print("  (Empty)")
            return
        for i, card_file in enumerate(self.hand):
            print(f"  {i}: {card_file}")

    def provide_clue(self):
        """Storyteller provides a clue and selects a card. Returns (clue, chosen_card_filename)."""
        if not self.hand:
            print(f"{self.name} has no cards to play.")
            return None, None

        if self.is_ai:
            print(f"{self.name} (AI) is choosing a card and thinking of a clue...")
            # AI Logic:
            # 1. Select a card index (randomly for now, could be smarter later)
            #    Could ask AI to pick its "most evocative" card, but let's keep it simple.
            chosen_card_index = random.randrange(len(self.hand))
            chosen_card_filename = self.hand[chosen_card_index]
            chosen_card_path = self._get_full_card_path(chosen_card_filename)
            print(f"{self.name} (AI) tentatively chose card {chosen_card_filename} (index {chosen_card_index}). Generating clue...")

            # 2. Generate clue using AI for the chosen card
            clue = generate_clue_for_image(chosen_card_path)
            if clue is None:
                print(f"Warning: AI {self.name} failed to generate clue for {chosen_card_filename}. Using fallback.")
                clue = f"AI Clue: {chosen_card_filename.split('.')[0]}" # Fallback clue

            # 3. Remove card from hand *using the index*
            self.hand.pop(chosen_card_index)
            print(f"{self.name} (AI) confirmed card {chosen_card_filename} with clue: '{clue}'")
            return clue, chosen_card_filename
        else:
            # Human Input
            self._display_hand()
            while True:
                try:
                    clue = input(f"{self.name}, enter your clue: ")
                    if not clue:
                        print("Clue cannot be empty.")
                        continue

                    card_index_str = input(f"Choose card index (0-{len(self.hand)-1}): ")
                    card_index = int(card_index_str)
                    if 0 <= card_index < len(self.hand):
                        chosen_card_filename = self.hand.pop(card_index)
                        print(f"{self.name} chose card {chosen_card_filename} with clue '{clue}'")
                        return clue, chosen_card_filename
                    else:
                        print("Invalid index.")
                except ValueError:
                    print("Invalid input. Please enter a number for the index.")
                except IndexError:
                     print("Error: Hand index out of bounds unexpectedly.")

    def submit_card(self, clue):
        """Non-storyteller submits a card matching the clue. Returns submitted_card_filename."""
        if not self.hand:
            print(f"{self.name} has no cards to submit.")
            return None

        if self.is_ai:
            print(f"{self.name} (AI) is choosing a card for the clue: '{clue}'...")
            # AI Logic:
            # 1. Get full paths for AI evaluation
            hand_paths = [self._get_full_card_path(f) for f in self.hand]
            # 2. Use AI to choose the best card *index*
            chosen_index = choose_card_for_clue(hand_paths, clue)

            if chosen_index is None or not (0 <= chosen_index < len(self.hand)):
                # Fallback if AI fails or returns invalid index
                print(f"Warning: AI {self.name} failed to choose valid card index via AI ({chosen_index}). Choosing randomly.")
                chosen_index = random.randrange(len(self.hand))

            # 3. Get the filename and remove from hand using the index
            submitted_card_filename = self.hand.pop(chosen_index)
            print(f"{self.name} (AI) submitted card {submitted_card_filename} (index {chosen_index})")
            return submitted_card_filename
        else:
            # Human Input
            self._display_hand()
            print(f"{self.name}, choose a card for the clue: '{clue}'")
            while True:
                try:
                    card_index_str = input(f"Choose card index (0-{len(self.hand)-1}): ")
                    card_index = int(card_index_str)
                    if 0 <= card_index < len(self.hand):
                        submitted_card_filename = self.hand.pop(card_index)
                        print(f"{self.name} submitted card {submitted_card_filename}")
                        return submitted_card_filename
                    else:
                        print("Invalid index.")
                except ValueError:
                    print("Invalid input. Please enter a number for the index.")
                except IndexError:
                     print("Error: Hand index out of bounds unexpectedly.")


    def guess_card(self, displayed_cards, clue, player_submitted_card_filename):
        """Player guesses the storyteller's card *index*.
        `displayed_cards` is a list of card filenames on the board.
        `player_submitted_card_filename` is the filename the current player submitted (or None if storyteller/failed).
        Returns the guessed index (relative to `displayed_cards`).
        """
        print(f"{self.name}, guess the storyteller's card for clue '{clue}':")
        for i, card_filename in enumerate(displayed_cards):
            is_own = " (Your Card)" if card_filename == player_submitted_card_filename else ""
            print(f"  {i}: {card_filename}{is_own}")

        if self.is_ai:
            print(f"{self.name} (AI) is guessing...")
            # AI Logic:
            # 1. Get full paths for board cards
            board_paths = [self._get_full_card_path(f) for f in displayed_cards]
            player_card_path = self._get_full_card_path(player_submitted_card_filename) if player_submitted_card_filename else None

            # 2. Use AI to guess the index
            guess_index = guess_storyteller_card(board_paths, clue, player_card_path)

            # Basic validation on returned index
            if not (0 <= guess_index < len(displayed_cards)):
                 print(f"Warning: AI returned invalid guess index {guess_index}. Guessing randomly (excluding own)." )
                 possible_indices = [i for i, fname in enumerate(displayed_cards) if fname != player_submitted_card_filename]
                 guess_index = random.choice(possible_indices) if possible_indices else 0
            # Ensure AI doesn't guess its own card (redundant check)
            elif displayed_cards[guess_index] == player_submitted_card_filename:
                 print(f"Warning: AI guess ({guess_index}) matched own card. Re-choosing randomly." )
                 possible_indices = [i for i, fname in enumerate(displayed_cards) if fname != player_submitted_card_filename]
                 guess_index = random.choice(possible_indices) if possible_indices else 0

            print(f"{self.name} (AI) guessed index {guess_index} ({displayed_cards[guess_index]})")
            return guess_index
        else:
            # Human Input
            while True:
                try:
                    guess_index_str = input(f"Enter your guess index (0-{len(displayed_cards)-1}): ")
                    guess_index = int(guess_index_str)

                    # Validate index range first
                    if not (0 <= guess_index < len(displayed_cards)):
                         print("Invalid index.")
                         continue

                    # Prevent voting for own card
                    if displayed_cards[guess_index] == player_submitted_card_filename:
                         print("You cannot vote for your own card. Try again.")
                         continue

                    # Valid guess
                    print(f"{self.name} guessed index {guess_index} ({displayed_cards[guess_index]})")
                    return guess_index

                except ValueError:
                    print("Invalid input. Please enter a number for the index.")
                # IndexError check might be redundant due to range check above, but keep for safety
                except IndexError:
                    print("Index out of range.")


class Game:
    def __init__(self, player_names, hand_size=6, max_score=30, cards_directory="cards"):
        self.hand_size = hand_size
        self.max_score = max_score
        self.cards_directory = cards_directory # Store directory
        # Initialize deck first
        self.deck = self._load_and_shuffle_cards(self.cards_directory)
        # Pass cards_dir to Player
        self.players = [Player(name, is_ai=("AI" in name), cards_dir=self.cards_directory) for name in player_names]

        # Check deck sufficiency and attempt dummy card creation AFTER players are initialized
        if not self.deck or len(self.deck) < len(self.players) * self.hand_size:
             print(f"Warning: Not enough cards ({len(self.deck)}) in '{self.cards_directory}'. Attempting to create dummy files.")
             if self._create_dummy_cards(len(player_names), hand_size):
                  self.deck = self._load_and_shuffle_cards(self.cards_directory) # Reload deck
                  if not self.deck or len(self.deck) < len(self.players) * self.hand_size:
                       raise ValueError(f"Still not enough cards after creating dummies. Need at least {len(self.players) * self.hand_size}.")
             else:
                  raise ValueError(f"Failed to create dummy cards. Not enough cards to start.")

        self._deal_cards()
        self.storyteller_index = 0
        self.discard_pile: list[Card] = []
        self.board = [] # Cards currently in play: { 'player': Player, 'card': CardFilename }
        self.current_clue = ""

    def _create_dummy_cards(self, num_players, hand_size):
        """Creates dummy card files if the directory is missing or empty."""
        # Calculate how many cards are currently in the deck (if any)
        current_deck_size = len(self.deck) if self.deck else 0

        if not os.path.isdir(self.cards_directory):
             print(f"Creating card directory: {self.cards_directory}")
             os.makedirs(self.cards_directory, exist_ok=True)

        num_needed = num_players * hand_size + (num_players * 5) # Estimate needed
        num_to_create = max(0, num_needed - current_deck_size) # Only create if needed

        if num_to_create == 0:
            print("Sufficient dummy cards likely exist.")
            return True # No need to create more

        print(f"Attempting to create {num_to_create} dummy card files...")
        created_count = 0
        try:
            existing_files = os.listdir(self.cards_directory)
            max_existing_num = 0
            for fname in existing_files:
                 if fname.lower().endswith('.png'):
                      try:
                           num = int(fname.split('.')[0])
                           max_existing_num = max(max_existing_num, num)
                      except (ValueError, IndexError): pass

            for i in range(max_existing_num + 1, max_existing_num + 1 + num_to_create):
                filename = f"{i:03d}.png"
                filepath = os.path.join(self.cards_directory, filename)
                try:
                    with open(filepath, 'w') as f:
                        f.write("") # Create empty files
                    created_count += 1
                except IOError as e:
                    print(f"Error creating dummy file {filename}: {e}")
                    # Don't necessarily fail the whole process, maybe enough were created
            if created_count > 0:
                 print(f"Created {created_count} dummy card files.")
            return True # Signal success even if some minor errors occurred
        except Exception as e:
             print(f"Error during dummy card creation setup: {e}")
             return False

    def _load_and_shuffle_cards(self, cards_directory):
        """Loads card identifiers (filenames) from the directory and shuffles them."""
        try:
            if not os.path.isdir(cards_directory):
                 print(f"Card directory '{cards_directory}' not found.")
                 return []
            cards = [f for f in os.listdir(cards_directory) if os.path.isfile(os.path.join(cards_directory, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not cards:
                print(f"Warning: No card image files found in {cards_directory}.")
                return []
            print(f"Loaded {len(cards)} cards from {cards_directory}.")
            random.shuffle(cards)
            return cards
        except Exception as e:
            print(f"Error loading cards from '{cards_directory}': {e}")
            return []

    def _deal_cards(self):
        """Deals cards to each player."""
        print("Dealing cards...")
        for player in self.players:
            # Clear existing hand first?
            # player.hand = [] # Uncomment if hands shouldn't accumulate on restart
            while len(player.hand) < self.hand_size and self.deck:
                player.hand.append(self.deck.pop())

    def play_turn(self):
        """Plays a full turn of the game."""
        if self.is_game_over():
            print("Attempted to play turn, but game is already over.")
            return

        storyteller = self.players[self.storyteller_index]
        print(f"\n--- Turn Start: {storyteller.name}'s turn (Storyteller) ---")

        # 1. Storyteller provides clue and card
        clue, storyteller_chosen_card = storyteller.provide_clue()
        if storyteller_chosen_card is None:
            print(f"{storyteller.name} has no cards to play. Skipping turn.")
            self._advance_storyteller()
            self._replenish_hands()
            return
        self.current_clue = clue
        storyteller_submission = {'player': storyteller, 'card': storyteller_chosen_card}

        # 2. Other players submit cards
        player_submissions = []
        print("\n--- Players Submit Cards ---")
        for player in self.players:
            if player != storyteller:
                submitted_card = player.submit_card(self.current_clue)
                if submitted_card:
                    player_submissions.append({'player': player, 'card': submitted_card})
                else:
                    print(f"Warning: {player.name} could not submit a card.")

        # 3. Prepare and display the board
        self.board = [storyteller_submission] + player_submissions
        random.shuffle(self.board)
        print(f"\n--- Cards on Board (Shuffled) ---")
        displayed_filenames = [submission['card'] for submission in self.board]
        for i, filename in enumerate(displayed_filenames):
            print(f"  {i}: {filename}")

        # 4. Players (not storyteller) guess
        guesses = {} # player.name -> guessed_index
        print("\n--- Players Guess ---")
        for player in self.players:
            if player != storyteller:
                # Find the card the player submitted (needed for guess method)
                player_submitted_card_filename = None
                for sub in player_submissions:
                    if sub['player'] == player:
                        player_submitted_card_filename = sub['card']
                        break
                if player_submitted_card_filename is None:
                     print(f"Warning: Could not find submitted card for {player.name} before guessing.")
                     # AI might still guess, human needs input

                # Use player's guess method
                guess_index = player.guess_card(displayed_filenames, self.current_clue, player_submitted_card_filename)
                guesses[player.name] = guess_index

        # 5. Update scores
        print("\n--- Scoring --- ")
        self._update_scores(storyteller_submission, guesses)

        # 6. Discard used cards
        used_cards = [submission['card'] for submission in self.board]
        self.discard_pile.extend(used_cards)
        self.board = []
        self.current_clue = ""
        print(f"Discarded {len(used_cards)} cards.")

        # 7. Replenish hands
        print("\n--- Replenishing Hands ---")
        self._replenish_hands()

        # 8. Advance storyteller
        self._advance_storyteller()

        # Print scores
        self.print_scores()


    def _update_scores(self, storyteller_submission, guesses):
        """Calculates and updates scores based on guesses."""
        storyteller = storyteller_submission['player']
        storyteller_card_filename = storyteller_submission['card']
        try:
            storyteller_card_index = -1
            for i, submission in enumerate(self.board):
                if submission['card'] == storyteller_card_filename:
                    storyteller_card_index = i
                    break
            if storyteller_card_index == -1:
                 print("Critical Error: Storyteller card not found on board during scoring.")
                 return
        except Exception as e:
             print(f"Error finding storyteller card index: {e}")
             return

        correct_guess_players = []
        for p_name, guess_idx in guesses.items():
            player = next((p for p in self.players if p.name == p_name), None)
            if player and guess_idx == storyteller_card_index:
                 correct_guess_players.append(player)

        num_guessers = len(self.players) - 1

        if num_guessers <= 0: # Avoid division by zero or weird logic if only 1 player
             print("Not enough players to score properly.")
             return

        if len(correct_guess_players) == num_guessers or len(correct_guess_players) == 0:
            print("All or no one guessed the storyteller's card correctly.")
            for player in self.players:
                if player != storyteller:
                    player.score += 2
                    print(f" +2 points for {player.name}.")
        else:
            print("Some players guessed the storyteller's card correctly.")
            storyteller.score += 3
            print(f" +3 points for {storyteller.name} (Storyteller).")
            for player in correct_guess_players:
                player.score += 3
                print(f" +3 points for {player.name} (Correct guess).")

        for p_name, guess_idx in guesses.items():
             guesser = next((p for p in self.players if p.name == p_name), None)
             if guesser and guess_idx != storyteller_card_index:
                 try:
                     fooled_player = self.board[guess_idx]['player']
                     if fooled_player != storyteller:
                          fooled_player.score += 1
                          print(f" +1 bonus point for {fooled_player.name} (fooled {guesser.name}).")
                 except IndexError:
                      print(f"Warning: Invalid guess index {guess_idx} encountered during bonus scoring.")


    def _advance_storyteller(self):
        """Moves the storyteller role to the next player."""
        self.storyteller_index = (self.storyteller_index + 1) % len(self.players)
        print(f"\nStoryteller is now: {self.players[self.storyteller_index].name}")

    def _replenish_hands(self):
        """Draws cards for players until they reach the hand size."""
        if not self.deck:
             print("Deck is empty. Attempting to reshuffle discard pile.")
             if not self.discard_pile:
                  print("Discard pile is also empty. Cannot replenish hands.")
                  return # Cannot replenish
             self.deck.extend(self.discard_pile)
             random.shuffle(self.deck)
             self.discard_pile = []
             print(f"Reshuffled {len(self.deck)} cards from discard pile into deck.")

        for player in self.players:
            drew_count = 0
            while len(player.hand) < self.hand_size and self.deck:
                player.hand.append(self.deck.pop())
                drew_count += 1
            if not self.deck and len(player.hand) < self.hand_size:
                 print(f"Warning: Deck became empty, {player.name} could not draw up to {self.hand_size} cards (has {len(player.hand)})." )

    def is_game_over(self):
        """Checks if the game end condition is met."""
        if any(player.score >= self.max_score for player in self.players):
             print(f"Game over: A player reached {self.max_score} points.")
             return True

        # Check if anyone *needs* to draw but can't (deck and discard are both empty)
        needs_draw = False
        for p in self.players:
             if len(p.hand) < self.hand_size:
                  needs_draw = True
                  break
        if needs_draw and not self.deck and not self.discard_pile:
             print("Game over: Deck and discard pile are empty, and players cannot replenish hands fully.")
             return True

        return False

    def print_scores(self):
        print("\nCurrent Scores:")
        sorted_players = sorted(self.players, key=lambda p: p.score, reverse=True)
        for player in sorted_players:
            print(f"  {player.name}: {player.score}")

    def get_winner(self):
        """Determines the winner(s) based on the highest score."""
        if not self.players: return []
        max_score = -1
        for player in self.players:
            if player.score > max_score:
                max_score = player.score
        if max_score < 0: return [] # No scores yet / no players
        winners = [player.name for player in self.players if player.score == max_score]
        return winners

# Removed the __main__ block here, as it's handled in main.py 