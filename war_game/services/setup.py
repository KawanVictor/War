import json
import random
from pathlib import Path
from war_game.models.game_state import GameState
from war_game.models.player import Player
from war_game.rules.errors import RuleError
from war_game.rules.missions import load_missions
from war_game.services.map_loader import load_map

COLORS = ["red", "blue", "green", "yellow", "purple", "black"]
MIN_PLAYERS = 2
MAX_PLAYERS = len(COLORS)

def new_game(data_dir: Path, num_players: int = 3) -> GameState:
    if type(num_players) is not int or not MIN_PLAYERS <= num_players <= MAX_PLAYERS:
        raise RuleError(f"O número de jogadores deve estar entre {MIN_PLAYERS} e {MAX_PLAYERS}.")
    territories = load_map(data_dir)
    players = [Player(id=i, name=f"Jogador {i+1}", color=COLORS[i]) for i in range(num_players)]
    names = list(territories.keys())
    random.shuffle(names)
    for i, n in enumerate(names):
        pid = i % num_players
        territories[n].owner_id = pid
        territories[n].armies = 1
        players[pid].territories.add(n)
    deck_defs = json.loads((data_dir / "cards.json").read_text(encoding="utf-8"))
    deck = [c["id"] for c in deck_defs]
    random.shuffle(deck)
    missions = dict(enumerate(random.sample(load_missions(data_dir), num_players)))
    return GameState(territories=territories, players=players, deck=deck, missions=missions)
