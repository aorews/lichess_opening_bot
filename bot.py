import threading
import random
import sys

import berserk

from api import Lichess
from opening import Opening

MOVE_THERSHOLD = 0.05


class Bot:
    def __init__(self) -> None:
        # Berserk api wrapper. Used for event listeners
        self.session = berserk.TokenSession(TOKEN)
        self.client = berserk.Client(self.session)

        # Additional api wrapper to query lichess database
        self.api = Lichess(TOKEN)

        # Get openings list on startup
        Opening.collect_data()

        # Dicts game_id:entity to save and pass data in Game class because Game instance created in the next event
        self.bot_color = dict()
        self.next_challenge = dict()
        self.next_opening = dict()

        self.run()

    def run(self):
        for event in self.client.bots.stream_incoming_events():
            if (event['type'] == 'challenge' and 
                event['challenge']['variant']['key'] == 'standard' and 
                event['challenge']['color'] != 'random'
                ):

                game_id = event['challenge']['id']
                
                if event['challenge']['challenger']['id'] != 'opening_bot':
                    self.client.bots.accept_challenge(game_id)
                    self.bot_color[game_id] = 'black' if event['challenge']['color'] == 'white' else 'white'

                    self.next_challenge[game_id] = {
                    'username': event['challenge']['challenger']['id'],
                    'rated': False,
                    'color': self.bot_color[game_id],
                    'variant': 'standard'
                    }
                    self.next_opening[game_id] = None
                else:
                    self.bot_color[game_id] = event['challenge']['color']

                    self.next_challenge[game_id] = {
                    'username': event['challenge']['destUser']['id'],
                    'rated': False,
                    'color': self.bot_color[game_id],
                    'variant': 'standard'
                    }
                    self.next_opening[game_id] = Opening.get_favorite(event['challenge']['destUser']['id'])

            elif event['type'] == 'challenge':
                self.client.bots.decline_challenge(event['challenge']['id'])
            elif event['type'] == 'gameStart':
                game_id = event['game']['id']
                game = Game(self.client, game_id, self.bot_color[game_id], self.next_challenge[game_id], self.api, self.next_opening[game_id])
                game.start()

class Game(threading.Thread):
    def __init__(self, client, game_id, bot_color, next_challenge, api, opening, **kwargs):
        super().__init__(**kwargs)
        self.username = next_challenge['username']
        self.game_id = game_id
        self.client = client
        self.stream = client.bots.stream_game_state(game_id)
        self.current_state = next(self.stream)
        self.color = bot_color
        self.next_challenge = next_challenge
        self.move = -2
        self.opening = opening
        self.stored_game_state = None

        self.api = api

        print(self.username, self.color, self.opening, sep='\n')

        self.client.bots.post_message(self.game_id, 'Please provide correct name of opening from lichess database! For example:')
        self.client.bots.post_message(self.game_id, 'Italian Game: Deutz Gambit')
        self.client.bots.post_message(self.game_id, 'or')
        self.client.bots.post_message(self.game_id, 'Sicilian Defense: Hyperaccelerated Dragon')

        if opening is not None:
            if self.color == 'white':
                self.move = 0
                self.start_as_white(self.opening)
            else:
                self.move = 1
                if self.stored_game_state is not None:
                    self.handle_state_change(self.stored_game_state)


    def run(self):
        for event in self.stream:
            if event['type'] in ['gameState']:
                self.handle_state_change(event)
            elif event['type'] == 'chatLine':
                self.handle_chat_line(event)
    
    def get_next_move(self, moves):
        moves_db = self.api.get_lichess_database(moves)
        if moves_db['opening'] != None:
            self.client.bots.post_message(self.game_id, f'{moves_db["opening"]["name"]}')
        try:
            next_move = self.opening[self.move]
            self.client.bots.make_move(self.game_id, next_move)
        except:
            threshold = (moves_db['white'] + moves_db['draws'] + moves_db['black']) * MOVE_THERSHOLD
            next_moves = list()
            for move in moves_db['moves']:
                if move['white'] + move['draws'] + move['black'] >= threshold:
                    next_moves.append(move['uci'])
            if len(next_moves) != 0:
                next_move = random.choice(next_moves)
                self.client.bots.post_message(self.game_id, f'Choosing out of {int(threshold / MOVE_THERSHOLD)} games!')
                self.client.bots.make_move(self.game_id, next_move)
            else:
                self.client.bots.post_message(self.game_id, 'Out of moves!')
                self.client.bots.resign_game(self.game_id)
                self.client.challenges.create(**self.next_challenge)
        

    
    def start_as_white(self, moves):
        if moves is None:
            self.get_next_move('')
        else:
            self.get_next_move(moves)
        self.move += 1

    def handle_state_change(self, game_state):
        if self.move>0 and (self.move % 2 == 0 and self.color == 'white' or self.move % 2 == 1 and self.color == 'black'):
            self.get_next_move(game_state['moves'])
        elif self.move<0:
            self.stored_game_state = game_state
        self.move += 1

        
    def handle_chat_line(self, chat_line):
        if chat_line['username'] != 'opening_bot' and self.move<0:
            if self.opening is None:
                self.opening = Opening.get(chat_line['text'])
                if len(self.opening) != 0:
                    self.client.bots.post_message(self.game_id, "Opening found!")
                else:
                    self.client.bots.post_message(self.game_id, "Opening not found!")
                Opening.set_favorite(self.username, self.opening)

            if self.color == 'white':
                self.move = 0
                self.start_as_white(self.opening)
            else:
                self.move = 1
                if self.stored_game_state is not None:
                    self.handle_state_change(self.stored_game_state)


    
    def recieve_opening(self):
        self.client.bots.post_message(self.game_id, "Please, write full name of opening.")


if __name__ == "__main__":
    TOKEN = sys.argv[1]
    Bot()