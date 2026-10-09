import json
from pathlib import Path
from war_game.models.game_state import GameState

def continent_bonus_map(data_dir: Path):
    return {c["name"]: c["bonus"] for c in json.loads((data_dir / "continents.json").read_text(encoding="utf-8"))}

def calc_base_reinforcements(num_territories: int) -> int:
    return max(3, num_territories // 3)

def has_full_continent(state: GameState, player_id: int, continent: str) -> bool:
    owners = [t.owner_id for t in state.territories.values() if t.continent == continent]
    return bool(owners) and all(o == player_id for o in owners)

def calc_total_reinforcements(state: GameState, data_dir: Path) -> int:
    player = state.current_player()
    base = calc_base_reinforcements(len(player.territories))
    bonuses = continent_bonus_map(data_dir)
    bonus = sum(b for c, b in bonuses.items() if has_full_continent(state, player.id, c))
    return base + bonus
