import random
from typing import Tuple, List
from war_game.models.game_state import GameState

def roll_dice(num: int) -> List[int]:
    return sorted([random.randint(1, 6) for _ in range(num)], reverse=True)

def max_attack_dice(armies: int) -> int:
    return min(3, max(0, armies - 1))

def max_defend_dice(armies: int) -> int:
    return min(2, armies)

def resolve_battle(attacking: List[int], defending: List[int]) -> Tuple[int, int]:
    losses_attacker = 0
    losses_defender = 0
    for a, d in zip(attacking, defending):
        if a > d:
            losses_defender += 1
        else:
            losses_attacker += 1  # empates favorecem defesa
    return losses_attacker, losses_defender

def attack_once(state: GameState, from_t: str, to_t: str, attack_dice: int, defend_dice: int):
    a_t = state.territories[from_t]
    d_t = state.territories[to_t]
    assert to_t in a_t.neighbors
    assert a_t.owner_id != d_t.owner_id
    assert attack_dice <= max_attack_dice(a_t.armies)
    assert defend_dice <= max_defend_dice(d_t.armies)

    a_rolls = roll_dice(attack_dice)
    d_rolls = roll_dice(defend_dice)
    la, ld = resolve_battle(a_rolls, d_rolls)

    a_t.armies -= la
    d_t.armies -= ld

    conquered = False
    if d_t.armies == 0:
        old_owner = d_t.owner_id
        d_t.owner_id = a_t.owner_id
        state.players[old_owner].territories.remove(d_t.name)
        state.players[a_t.owner_id].territories.add(d_t.name)
        move = min(max(attack_dice, 1), a_t.armies - 1 if a_t.armies > 1 else 0)
        if move > 0:
            a_t.armies -= move
            d_t.armies += move
        state.conquered_this_turn = True
        conquered = True

    return {
        "attacker_rolls": a_rolls,
        "defender_rolls": d_rolls,
        "losses_attacker": la,
        "losses_defender": ld,
        "conquered": conquered
    }
