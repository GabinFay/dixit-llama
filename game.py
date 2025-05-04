import random
import os
import time # Added for slight delay in AI turns
# from config import HAND_SIZE, MAX_SCORE, CARDS_DIRECTORY # Assuming config.py exists

# Placeholder for card representation (e.g., image file paths)
Card = str

class Player:
    def __init__(self, name, is_ai=False):
        self.name = name
        self.score = 0
        self.hand = []
        self.is_ai = is_ai

    def _display_hand(self):
        print(f"{self.name}'s hand:")
        if not self.hand:
            print("  (Empty)")
            return
        for i, card in enumerate(self.hand):
            print(f"  {i}: {card}")

    def provide_clue(self):
        """Storyteller provides a clue and selects a card."""
        self._display_hand()
        if not self.hand:
            print(f"{self.name} has no cards to play.")
            return None, None # Return None if no cards

        if self.is_ai:
            print(f"{self.name} (AI) is thinking of a clue...")
            time.sleep(1) # Simulate thinking
            # AI Placeholder: Choose first card, make up a simple clue
            chosen_card = self.hand.pop(0)
            clue = f"AI Clue for {chosen_card.split('.')[0]}" # Simple clue based on filename
            print(f"{self.name} (AI) chose card {chosen_card} with clue: '{clue}'")
            return clue, chosen_card
        else:
            # Human Input
            while True:
                try:
                    clue = input(f"{self.name}, enter your clue: ")
                    if not clue:
                        print("Clue cannot be empty.")
                        continue

                    card_index_str = input(f"Choose card index (0-{len(self.hand)-1}): ")
                    card_index = int(card_index_str)
                    if 0 <= card_index < len(self.hand):
                        chosen_card = self.hand.pop(card_index)
                        print(f"{self.name} chose card {chosen_card} with clue '{clue}'")
                        return clue, chosen_card
                    else:
                        print("Invalid index.")
                except ValueError:
                    print("Invalid input. Please enter a number for the index.")
                except IndexError:
                     print("Error: Hand index out of bounds unexpectedly.") # Should be caught by validation

    def submit_card(self, clue):
        """Non-storyteller submits a card matching the clue."""
        self._display_hand()
        if not self.hand:
            print(f"{self.name} has no cards to submit.")
            return None

        print(f"{self.name}, choose a card for the clue: '{clue}'")
        if self.is_ai:
            print(f"{self.name} (AI) is choosing a card...")
            time.sleep(1)
            # AI Placeholder: Submit the first card
            submitted_card = self.hand.pop(0)
            print(f"{self.name} (AI) submitted card {submitted_card}")
            return submitted_card
        else:
            # Human Input
            while True:
                try:
                    card_index_str = input(f"Choose card index (0-{len(self.hand)-1}): ")
                    card_index = int(card_index_str)
                    if 0 <= card_index < len(self.hand):
                        submitted_card = self.hand.pop(card_index)
                        print(f"{self.name} submitted card {submitted_card}")
                        return submitted_card
                    else:
                        print("Invalid index.")
                except ValueError:
                    print("Invalid input. Please enter a number for the index.")
                except IndexError:
                     print("Error: Hand index out of bounds unexpectedly.")


    def guess_card(self, displayed_cards):
        """Player guesses which card was the storyteller's."""
        print(f"{self.name}, guess the storyteller's card from the following:")
        for i, card in enumerate(displayed_cards):
            print(f"  {i}: {card}")
        # Note: Players cannot vote for their own submitted card, but this isn't implemented yet.
        # This would require tracking which card belongs to whom on the board.

        if self.is_ai:
            print(f"{self.name} (AI) is guessing...")
            time.sleep(1)
            # AI Placeholder: Guess a random card (excluding potentially own card - basic check)
            possible_guesses = list(range(len(displayed_cards)))
            # Very basic check: If AI submitted a card, don't guess it (This needs proper tracking)
            # For now, just guess randomly among all.
            guess_index = random.choice(possible_guesses)
            print(f"{self.name} (AI) guessed index {guess_index}")
            return guess_index
        else:
            # Human Input
            while True:
                try:
                    guess_index_str = input(f"Enter your guess index (0-{len(displayed_cards)-1}): ")
                    guess_index = int(guess_index_str)
                    # TODO: Add validation to prevent voting for own card
                    if 0 <= guess_index < len(displayed_cards):
                        print(f"{self.name} guessed index {guess_index}")
                        return guess_index
                    else:
                        print("Invalid index.")
                except ValueError:
                    print("Invalid input. Please enter a number for the index.")


class Game:
    def __init__(self, player_names, hand_size=6, max_score=30, cards_directory="cards"):
        # Assign players distinguishing AI based on name convention (or could pass is_ai flags)
        self.players = [Player(name, is_ai=("AI" in name)) for name in player_names]
        self.hand_size = hand_size
        self.max_score = max_score
        self.cards_directory = cards_directory
        self.deck = self._load_and_shuffle_cards(self.cards_directory)
        if not self.deck or len(self.deck) < len(self.players) * self.hand_size:
            raise ValueError(f"Not enough cards in '{self.cards_directory}' to start the game.")
        # self.hands = {player.name: [] for player in self.players} # Player class now manages its own hand
        self._deal_cards()
        self.storyteller_index = 0
        self.discard_pile = []
        self.board = [] # Cards currently in play: { 'player': Player, 'card': Card } # Changed structure
        self.current_clue = ""
        # self.storyteller_card = None # Store storyteller's card within self.board now

    def _load_and_shuffle_cards(self, cards_directory):
        """Loads card identifiers (e.g., filenames) from the directory and shuffles them."""
        try:
            cards = [f for f in os.listdir(cards_directory) if os.path.isfile(os.path.join(cards_directory, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not cards:
                print(f"Warning: No cards found in {cards_directory}. Please add card images.")
                return []
            print(f"Loaded {len(cards)} cards from {cards_directory}.")
            random.shuffle(cards)
            return cards
        except FileNotFoundError:
            print(f"Error: Cards directory '{cards_directory}' not found.")
            return []

    def _deal_cards(self):
        """Deals cards to each player."""
        print("Dealing cards...")
        for player in self.players:
            while len(player.hand) < self.hand_size and self.deck:
                player.hand.append(self.deck.pop())
            # print(f"Dealt hand to {player.name}: {player.hand}") # Debug print

    def play_turn(self):
        """Plays a full turn of the game."""
        if self.is_game_over():
            print("Attempted to play turn, but game is already over.")
            return

        storyteller = self.players[self.storyteller_index]
        print(f"\n--- Turn Start: {storyteller.name}'s turn (Storyteller) ---")

        # 1. Storyteller provides clue and card
        clue, storyteller_chosen_card = storyteller.provide_clue()
        if storyteller_chosen_card is None: # Handle case where storyteller has no cards
            print(f"{storyteller.name} has no cards to play. Skipping turn.")
            self._advance_storyteller()
            self._replenish_hands() # Replenish even if skipped
            return
        self.current_clue = clue
        storyteller_submission = {'player': storyteller, 'card': storyteller_chosen_card}

        # 2. Other players submit cards
        player_submissions = [] # List of {'player': Player, 'card': Card}
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
        random.shuffle(self.board) # Shuffle the dictionaries
        print(f"\n--- Cards on Board (Shuffled) ---")
        for i, submission in enumerate(self.board):
            print(f"  {i}: {submission['card']}") # Only show card filenames

        # 4. Players (not storyteller) guess
        guesses = {} # player.name -> guessed_index
        print("\n--- Players Guess ---")
        for player in self.players:
            if player != storyteller:
                # Find the index of the card the player submitted (if any)
                player_submitted_card_index = -1
                for i, sub in enumerate(self.board):
                    if sub['player'] == player:
                        player_submitted_card_index = i
                        break
                
                # Use player's guess method (which handles AI/human)
                # We need to prevent guessing own card here if possible
                # The guess_card method itself needs modification to accept invalid indices
                while True: 
                    guess_index = player.guess_card([s['card'] for s in self.board])
                    if guess_index == player_submitted_card_index:
                         print(f"{player.name}, you cannot vote for your own card. Try again.")
                         if player.is_ai: # Prevent AI infinite loop
                              print("AI chose own card, retrying randomly...")
                              possible_guesses = list(range(len(self.board)))
                              possible_guesses.pop(player_submitted_card_index)
                              if not possible_guesses: # Should not happen in normal game
                                   guess_index = 0 
                              else: 
                                   guess_index = random.choice(possible_guesses)
                              print(f"{player.name} (AI) re-guessed index {guess_index}")
                              guesses[player.name] = guess_index
                              break # Exit loop for AI retry
                         # For human, loop continues based on input
                    elif 0 <= guess_index < len(self.board):
                         guesses[player.name] = guess_index
                         break # Valid guess
                    else:
                         # This case should be handled within guess_card, but as fallback:
                         print(f"Invalid index {guess_index} received. Please try again.") 
                         # For AI, guess_card should return valid index

        # 5. Update scores
        print("\n--- Scoring --- ")
        self._update_scores(storyteller_submission, guesses)

        # 6. Discard used cards
        used_cards = [submission['card'] for submission in self.board]
        self.discard_pile.extend(used_cards)
        self.board = [] # Clear the board
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
        storyteller_card = storyteller_submission['card']
        try:
            # Find the index of the storyteller's card on the shuffled board
            storyteller_card_index = -1
            for i, submission in enumerate(self.board):
                if submission['card'] == storyteller_card:
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

        # Rule 1: All guessers found the storyteller's card OR no guesser found it.
        if len(correct_guess_players) == num_guessers or len(correct_guess_players) == 0:
            print("All or no one guessed the storyteller's card correctly.")
            for player in self.players:
                if player != storyteller:
                    player.score += 2
                    print(f" +2 points for {player.name}.")
        # Rule 2: Some (but not all) guessers found the storyteller's card.
        else:
            print("Some players guessed the storyteller's card correctly.")
            storyteller.score += 3
            print(f" +3 points for {storyteller.name} (Storyteller).")
            for player in correct_guess_players:
                player.score += 3
                print(f" +3 points for {player.name} (Correct guess).")

        # Rule 3: Bonus points for fooling others
        for p_name, guess_idx in guesses.items():
             guesser = next((p for p in self.players if p.name == p_name), None)
             if guesser and guess_idx != storyteller_card_index:
                # Find the player whose card was incorrectly guessed
                 try:
                     fooled_player = self.board[guess_idx]['player']
                     # Ensure the fooled player isn't the storyteller (they don't get points this way)
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
        for player in self.players:
            drew_count = 0
            while len(player.hand) < self.hand_size and self.deck:
                player.hand.append(self.deck.pop())
                drew_count += 1
            if drew_count > 0:
                 print(f" {player.name} drew {drew_count} card(s). Remaining deck: {len(self.deck)}")
            if not self.deck and len(player.hand) < self.hand_size:
                 print(f"Warning: Deck is empty, {player.name} could not draw up to {self.hand_size} cards.")

    def is_game_over(self):
        """Checks if the game end condition is met."""
        if any(player.score >= self.max_score for player in self.players):
             print(f"Game over: A player reached {self.max_score} points.")
             return True
        # Game also ends if the deck runs out and players need to draw cards
        # This is implicitly handled now by checking replenish needs vs deck size
        if not self.deck and any(len(p.hand) < self.hand_size for p in self.players):
             # Check if anyone *needs* to draw but can't
             needs_draw = False
             for p in self.players:
                  if len(p.hand) < self.hand_size:
                       needs_draw = True
                       break
             if needs_draw:
                  print("Game over: Deck is empty and players cannot replenish hands fully.")
                  return True
                  
        return False

    def print_scores(self):
        print("\nCurrent Scores:")
        # Sort players by score descending for display
        sorted_players = sorted(self.players, key=lambda p: p.score, reverse=True)
        for player in sorted_players:
            print(f"  {player.name}: {player.score}")

    def get_winner(self):
        """Determines the winner(s) based on the highest score."""
        if not self.players: return [] # No players
        max_score = -1
        # Find max score first
        for player in self.players:
            if player.score > max_score:
                max_score = player.score
        
        # Collect all players with max score
        winners = [player.name for player in self.players if player.score == max_score]
        return winners

# Removed the __main__ block here, as it's handled in main.py 