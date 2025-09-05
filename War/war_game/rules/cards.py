import json
from pathlib import Path
from typing import List, Tuple
from war_game.models.game_state import GameState

PROGRESSION = [4, 6, 8, 10, 12, 15]

def next_trade_value(trades_done: int) -> int:
    if trades_done < len(PROGRESSION):
        return PROGRESSION[trades_done]
    return PROGRESSION[-1] + 5 * (trades_done - len(PROGRESSION) + 1)

def can_redeem_set(cards: List[str], card_defs: dict):
    combos = []
    ids = cards[:]
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                icons = [card_defs[ids[i]]["icon"], card_defs[ids[j]]["icon"], card_defs[ids[k]]["icon"]]
                if "wild" in icons or len(set(icons)) == 1 or len(set(icons)) == 3:
                    combos.append((ids[i], ids[j], ids[k]))
    return combos

def redeem_cards(state: GameState, data_dir: Path, chosen: Tuple[str, str, str], trades_done: int) -> int:
    defs = {c["id"]: c for c in json.loads((data_dir / "cards.json").read_text(encoding="utf-8"))}
    value = next_trade_value(trades_done)
    player = state.current_player()
    for cid in chosen:
        player.cards.remove(cid)
        state.discard.append(cid)
    owned_bonus_applied = False
    for cid in chosen:
        terr = defs[cid]["territory"]
        if terr and terr in player.territories and not owned_bonus_applied:
            state.territories[terr].armies += 2
            owned_bonus_applied = True
            break
    return value
