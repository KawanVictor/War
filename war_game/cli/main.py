import random
from pathlib import Path
import json
from war_game.models.game_state import GameState
from war_game.models.player import Player
from war_game.services.map_loader import load_map
from war_game.services.turn_manager import TurnManager
from war_game.cli.prompts import ask_int, ask_str, ask_yes_no

DATA_DIR = Path(__file__).resolve().parents[2] / "war_game" / "data"

def initial_setup(num_players=3):
    # mantém o conteúdo igual
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
    state = GameState(territories=territories, players=players, deck=deck)
    return state

def prompt_placement(tm, reinforcements):
    player = tm.state.current_player()
    print("Territórios disponíveis para colocar tropas:", list(player.territories))
    total = reinforcements
    placements = {}
    while total > 0:
        territory = ask_str(f"Em qual território colocar tropas? (restam {total}): ", valid_options=list(player.territories))
        qty = ask_int(f"Quantas tropas colocar em {territory}? ", min_val=1, max_val=total)
        placements[territory] = placements.get(territory, 0) + qty
        total -= qty
        if total > 0:
            if not ask_yes_no("Deseja continuar colocando tropas?"):
                break
    return placements

def prompt_attack(tm):
    player = tm.state.current_player()
    while True:
        print("Posso atacar de:")
        attack_from = [t for t in player.territories if tm.state.territories[t].armies > 1]
        if not attack_from:
            print("Nenhum território com tropas suficientes para atacar.")
            break
        print(attack_from)
        from_territory = ask_str("De qual território deseja atacar? (ou 'n' para pular): ", valid_options=attack_from + ["n"])
        if from_territory == "n":
            break
        neighbors = [n for n in tm.state.territories[from_territory].neighbors if tm.state.territories[n].owner_id != player.id]
        if not neighbors:
            print("Esse território não tem vizinhos inimigos.")
            continue
        print("Territórios inimigos vizinhos:", neighbors)
        to_territory = ask_str("Qual território deseja atacar? ", valid_options=neighbors)
        max_dice = min(3, tm.state.territories[from_territory].armies - 1)
        dice = ask_int(f"Quantos dados quer usar para atacar? (1 a {max_dice}): ", min_val=1, max_val=max_dice)
        result = tm.do_attack(from_territory, to_territory, dice)
        print("Resultado do ataque:", result)
        if not ask_yes_no("Quer atacar novamente?"):
            break

def main():
    state = initial_setup(3)
    tm = TurnManager(state, DATA_DIR)
    while True:
        p = state.current_player()
        print(f"\n=== Turno de {p.name} ({p.color}) ===")
        reinf = tm.start_turn()
        print(f"Reforços disponíveis: {reinf}")

        placements = prompt_placement(tm, reinf)
        tm.place_reinforcements(placements)

        prompt_attack(tm)
        tm.end_turn()

if __name__ == "__main__":
    main()
