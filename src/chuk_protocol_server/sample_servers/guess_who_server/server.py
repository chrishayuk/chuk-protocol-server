#!/usr/bin/env python3
# sample_servers/guess_who_server.py
"""
Guess Who Telnet Server

A telnet server that hosts a text-based version of the Guess Who game.
This implementation uses the modular telnet server framework.
"""
import asyncio
import logging
import random
from typing import List, Dict, Any

# Import from the modular telnet framework
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler
from chuk_protocol_server.servers.telnet_server import TelnetServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('guess-who-server')

# Updated character database:
# - Hair color is "none" if the character is bald
CHARACTERS = [
    {"name": "Alex", "gender": "male", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Alfred", "gender": "male", "hair_color": "none",  "hair_type": "bald", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Anita", "gender": "female", "hair_color": "blonde", "hair_type": "long", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Anne", "gender": "female", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Bernard", "gender": "male", "hair_color": "brown", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": True},
    {"name": "Bill", "gender": "male", "hair_color": "none",  "hair_type": "bald", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Charles", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Claire", "gender": "female", "hair_color": "red", "hair_type": "short", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "David", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Eric", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": True},
    {"name": "Frans", "gender": "male", "hair_color": "red", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "George", "gender": "male", "hair_color": "white", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": True},
    {"name": "Herman", "gender": "male", "hair_color": "none",  "hair_type": "bald", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Joe", "gender": "male", "hair_color": "blonde", "hair_type": "short", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "Maria", "gender": "female", "hair_color": "brown", "hair_type": "long", "glasses": False, "facial_hair": False, "hat": True},
    {"name": "Max", "gender": "male", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Paul", "gender": "male", "hair_color": "white", "hair_type": "short", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "Peter", "gender": "male", "hair_color": "white", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Philip", "gender": "male", "hair_color": "black", "hair_type": "short", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Richard", "gender": "male", "hair_color": "none",  "hair_type": "bald", "glasses": False, "facial_hair": True, "hat": False},
    {"name": "Robert", "gender": "male", "hair_color": "brown", "hair_type": "short", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Sam", "gender": "male", "hair_color": "none",  "hair_type": "bald", "glasses": True, "facial_hair": False, "hat": False},
    {"name": "Susan", "gender": "female", "hair_color": "white", "hair_type": "long", "glasses": False, "facial_hair": False, "hat": False},
    {"name": "Tom", "gender": "male", "hair_color": "none",  "hair_type": "bald", "glasses": True, "facial_hair": False, "hat": False}
]

VALID_QUESTIONS = [
    "is it a man?",
    "is it a woman?",
    "do they have glasses?",
    "do they have a hat?",
    "do they have facial hair?",
    "do they have black hair?",
    "do they have blonde hair?",
    "do they have brown hair?",
    "do they have red hair?",
    "do they have white hair?",
    "are they bald?",
    "do they have short hair?",
    "do they have long hair?",
]

class GuessWhoHandler(TelnetHandler):
    """
    Handler for Guess Who telnet sessions.
    This handler manages the game state and processes player input.
    """

    async def on_connect(self) -> None:
        """Initialize game state when a client connects."""
        await super().on_connect()
        self.game_started = False
        self.remaining_characters = CHARACTERS.copy()
        self.secret_character = None
        self.questions_asked = 0
        self.max_questions = 10

    async def show_help(self) -> None:
        """Display help information about the game."""
        await self.send_line("\nGUESS WHO - HELP")
        await self.send_line("----------------")
        await self.send_line("COMMANDS (type exactly as shown):")
        await self.send_line("  start         - Start a new game")
        await self.send_line("  list          - Show remaining possible characters")
        await self.send_line("  guess [name]  - Make a final guess (e.g., 'guess alex')")
        await self.send_line("  help          - Show this help")
        await self.send_line("  quit          - Exit the game")
        await self.send_line("\nQUESTIONS (type exactly as shown):")
        for question in VALID_QUESTIONS:
            await self.send_line(f"  {question}")
        await self.send_line("\nYou have 10 questions before you must guess!")
        await self.send_line("----------------\n")

    async def display_characters(self) -> None:
        """Display the list of remaining characters."""
        if not self.remaining_characters:
            await self.send_line("No characters remain! Something went wrong.")
            return
            
        await self.send_line("\nREMAINING CHARACTERS:")
        await self.send_line("---------------------")
        
        # Calculate the maximum name length for alignment
        max_name_length = max(len(character["name"]) for character in self.remaining_characters)
        
        for character in sorted(self.remaining_characters, key=lambda x: x["name"]):
            name = character["name"].ljust(max_name_length)
            gender = character["gender"]

            # If bald, just show "bald"
            if character["hair_type"] == "bald":
                hair_info = "bald"
            else:
                hair_info = f"{character['hair_color']} {character['hair_type']} hair"
            
            features = []
            if character["glasses"]:
                features.append("glasses")
            if character["facial_hair"]:
                features.append("facial hair")
            if character["hat"]:
                features.append("hat")
                
            features_str = ", ".join(features) if features else "no accessories"
            
            await self.send_line(f"{name} - {gender}, {hair_info}, {features_str}")
        
        await self.send_line(f"\nRemaining characters: {len(self.remaining_characters)}")
        await self.send_line(f"Questions asked: {self.questions_asked}/{self.max_questions}")
        await self.send_line("---------------------\n")

    async def start_game(self) -> None:
        """Start a new game."""
        self.remaining_characters = CHARACTERS.copy()
        self.secret_character = random.choice(CHARACTERS)
        self.questions_asked = 0
        self.game_started = True
        
        logger.info(f"Started new game for {self.addr}. Secret character: {self.secret_character['name']}")
        
        await self.send_line("\n" + "=" * 50)
        await self.send_line("WELCOME TO GUESS WHO!")
        await self.send_line("=" * 50)
        await self.send_line("I've selected a secret character. Can you guess who it is?")
        await self.send_line(f"You can ask up to {self.max_questions} yes/no questions.")
        await self.send_line("\nAVAILABLE COMMANDS:")
        await self.send_line("  list          - Show all possible characters")
        await self.send_line("  help          - Show all commands & questions")
        await self.send_line("  guess [name]  - Make your final guess (e.g., 'guess alex')")
        await self.send_line("\nEXAMPLE QUESTIONS:")
        await self.send_line("  is it a man?")
        await self.send_line("  do they have glasses?")
        await self.send_line("  do they have red hair?")
        await self.send_line("  (type 'help' to see all available questions)")
        await self.send_line("=" * 50 + "\n")
        
        await self.display_characters()

    async def handle_question(self, question: str) -> None:
        """
        Handle a yes/no question from the player.
        
        Args:
            question: The player's question
        """
        # First, enforce the maximum question limit
        if self.questions_asked >= self.max_questions:
            await self.send_line(
                "\nYou've already used all your questions. "
                "Make your final guess with 'guess [name]' or type 'help' for instructions."
            )
            return
        
        question = question.lower().strip()
        
        if question not in VALID_QUESTIONS:
            await self.send_line("That doesn't seem to be a valid question. Type 'help' to see example questions.")
            return
            
        self.questions_asked += 1
        logger.info(f"Client {self.addr} asked: {question}")
        
        answer = False  # Default

        # Gender questions
        if question == "is it a man?":
            answer = (self.secret_character["gender"] == "male")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["gender"] == "male") == answer
            ]
        
        elif question == "is it a woman?":
            answer = (self.secret_character["gender"] == "female")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["gender"] == "female") == answer
            ]
        
        # Accessories
        elif question == "do they have glasses?":
            answer = self.secret_character["glasses"]
            self.remaining_characters = [c for c in self.remaining_characters if c["glasses"] == answer]
        
        elif question == "do they have a hat?":
            answer = self.secret_character["hat"]
            self.remaining_characters = [c for c in self.remaining_characters if c["hat"] == answer]
        
        elif question == "do they have facial hair?":
            answer = self.secret_character["facial_hair"]
            self.remaining_characters = [c for c in self.remaining_characters if c["facial_hair"] == answer]
        
        # Hair type
        elif question == "are they bald?":
            answer = (self.secret_character["hair_type"] == "bald")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_type"] == "bald") == answer
            ]
        
        elif question == "do they have short hair?":
            answer = (self.secret_character["hair_type"] == "short")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_type"] == "short") == answer
            ]
        
        elif question == "do they have long hair?":
            answer = (self.secret_character["hair_type"] == "long")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_type"] == "long") == answer
            ]
        
        # Hair color
        elif question == "do they have black hair?":
            answer = (self.secret_character["hair_color"] == "black")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_color"] == "black") == answer
            ]
        
        elif question == "do they have blonde hair?":
            answer = (self.secret_character["hair_color"] == "blonde")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_color"] == "blonde") == answer
            ]
        
        elif question == "do they have brown hair?":
            answer = (self.secret_character["hair_color"] == "brown")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_color"] == "brown") == answer
            ]
        
        elif question == "do they have red hair?":
            answer = (self.secret_character["hair_color"] == "red")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_color"] == "red") == answer
            ]
        
        elif question == "do they have white hair?":
            answer = (self.secret_character["hair_color"] == "white")
            self.remaining_characters = [
                c for c in self.remaining_characters
                if (c["hair_color"] == "white") == answer
            ]
        
        # Send Yes/No answer
        await self.send_line(f"Answer: {'Yes' if answer else 'No'}")
        
        # If there's exactly one character left, prompt the player to guess
        if len(self.remaining_characters) == 1:
            await self.send_line("\nI think you know who it is now! Type 'guess [name]' to make your final guess.")
        
        # If user hit the max question limit exactly, notify them
        if self.questions_asked >= self.max_questions:
            await self.send_line("\nYou've used all your questions! Make your final guess with 'guess [name]'.")
        
        await self.display_characters()
            
    async def make_guess(self, guess: str) -> None:
        """Process the player's final guess."""
        name = guess.strip().lower()
        
        correct = (name == self.secret_character["name"].lower())
        
        if correct:
            await self.send_line("\n🎉 CONGRATULATIONS! 🎉")
            await self.send_line(f"You correctly guessed that the character was {self.secret_character['name']}!")
            await self.send_line(f"It took you {self.questions_asked} questions.")
        else:
            await self.send_line("\n❌ Sorry, that's incorrect! ❌")
            await self.send_line(f"The character was {self.secret_character['name']}.")
        
        await self.send_line("\nType 'start' to play again or 'quit' to exit.")
        self.game_started = False

    async def on_command_submitted(self, command: str) -> None:
        """
        Process a command from the player.
        This is the main entry point for processing player input.
        """
        command = command.strip().lower()
        
        if command == 'quit':
            await self.send_line("Thanks for playing Guess Who! Goodbye!")
            # The client will be disconnected by the parent handler
            return
            
        elif command == 'help':
            await self.show_help()
            
        elif command == 'start':
            await self.start_game()
            
        elif command == 'list' and self.game_started:
            await self.display_characters()
            
        elif command.startswith('guess ') and self.game_started:
            await self.make_guess(command[6:])
            
        elif self.game_started and command in VALID_QUESTIONS:
            await self.handle_question(command)
            
        else:
            if not self.game_started:
                await self.send_line("Game not started. Type 'start' to begin or 'help' for instructions.")
            else:
                await self.send_line("I don't understand that command. Type 'help' for instructions.")

    async def send_welcome(self) -> None:
        """Send a welcome message to the player."""
        await self.send_line("=============================================")
        await self.send_line("      WELCOME TO THE GUESS WHO SERVER!      ")
        await self.send_line("=============================================")
        await self.send_line("COMMANDS (type exactly as shown):")
        await self.send_line("  start         - Begin a new game")
        await self.send_line("  help          - View all commands & questions")
        await self.send_line("  quit          - Disconnect")
        await self.send_line("=============================================")
    
    async def process_line(self, line: str) -> bool:
        """
        Override process_line to properly handle commands in both simple and telnet modes.
        
        This ensures the game works consistently across all transports.
        
        Args:
            line: The line to process
            
        Returns:
            True to continue processing, False to terminate the connection
        """
        logger.debug(f"GuessWhoHandler process_line => {line!r}")
        
        # Check for exit commands first
        if line.lower() in ['quit', 'exit', 'q']:
            await self.send_line("Thanks for playing Guess Who! Goodbye!")
            await self.end_session()
            return False
        
        # Process the command through on_command_submitted
        await self.on_command_submitted(line)
        
        # Continue processing
        return True

async def main():
    """Main entry point for the Guess Who server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    host, port = '0.0.0.0', 8023
    server = TelnetServer(host, port, GuessWhoHandler)
    
    try:
        logger.info(f"Starting Guess Who Server on {host}:{port}")
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user.")
    except Exception as e:
        logger.error(f"Error running server: {e}")
    finally:
        logger.info("Server has shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        logger.info("Server process exiting.")