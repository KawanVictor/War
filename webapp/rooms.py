from typing import Dict
from pathlib import Path
import json, random
from war_game.models.game_state import GameState
from war_game.models.player import Player
from war_game.services.map_loader import load_map
from war_game.services.turn_manager import TurnManager

DATA_DIR = Path(__file__).resolve().parents[1] / "war_game" / "data"

class Room:
    def __init__(self, room_id: str, num_players: int = 3):
        self.id = room_id
        self.state = self._initial_setup(num_players)
        self.tm = TurnManager(self.state, DATA_DIR)

    def _initial_setup(self, num_players: int) -> GameState:
        territories = load_map(DATA_DIR)
        players = [Player(id=i, name=f"Jogador {i+1}", color=["red","blue","green","yellow","purple","black"][i]) for i in range(num_players)]
        names = list(territories.keys())
        random.shuffle(names)
        for i, n in enumerate(names):
            pid = i % num_players
            territories[n].owner_id = pid
            territories[n].armies = 1
            players[pid].territories.add(n)
        deck_defs = json.loads((DATA_DIR / "cards.json").read_text(encoding="utf-8"))
        deck = [c["id"] for c in deck_defs]
        random.shuffle(deck)
        return GameState(territories=territories, players=players, deck=deck)

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def get_or_create(self, room_id: str, num_players: int = 3) -> Room:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id, num_players)
        return self.rooms[room_id]

rooms = RoomManager()
