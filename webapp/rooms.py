from typing import Dict, Optional
from pathlib import Path
from war_game.services.setup import new_game
from war_game.services.turn_manager import TurnManager

DATA_DIR = Path(__file__).resolve().parents[1] / "war_game" / "data"

class Room:
    def __init__(self, room_id: str, num_players: int = 3):
        self.id = room_id
        self.state = new_game(DATA_DIR, num_players)
        self.tm = TurnManager(self.state, DATA_DIR)

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def get(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def get_or_create(self, room_id: str, num_players: int = 3) -> Room:
        if room_id not in self.rooms:
            self.rooms[room_id] = Room(room_id, num_players)
        return self.rooms[room_id]

rooms = RoomManager()
