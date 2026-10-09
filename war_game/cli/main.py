from pathlib import Path
from war_game.rules.errors import RuleError
from war_game.services.setup import new_game
from war_game.services.turn_manager import TurnManager
from war_game.cli.prompts import ask_int, ask_str, ask_yes_no

DATA_DIR = Path(__file__).resolve().parents[2] / "war_game" / "data"

def initial_setup(num_players=3):
    return new_game(DATA_DIR, num_players)

def prompt_placement(tm):
    state = tm.state
    player = state.current_player()
    print("Territórios disponíveis para colocar tropas:", sorted(player.territories))
    while state.reinforcements_left > 0 and state.winner_id is None:
        total = state.reinforcements_left
        territory = ask_str(f"Em qual território colocar tropas? (restam {total}): ", valid_options=sorted(player.territories))
        qty = ask_int(f"Quantas tropas colocar em {territory}? ", min_val=1, max_val=total)
        tm.place_reinforcements({territory: qty})

def prompt_attack(tm):
    state = tm.state
    player = state.current_player()
    while state.winner_id is None:
        print("Posso atacar de:")
        attack_from = sorted(t for t in player.territories if state.territories[t].armies > 1)
        if not attack_from:
            print("Nenhum território com tropas suficientes para atacar.")
            break
        print(attack_from)
        from_territory = ask_str("De qual território deseja atacar? (ou 'n' para pular): ", valid_options=attack_from + ["n"])
        if from_territory == "n":
            break
        neighbors = sorted(n for n in state.territories[from_territory].neighbors if state.territories[n].owner_id != player.id)
        if not neighbors:
            print("Esse território não tem vizinhos inimigos.")
            continue
        print("Territórios inimigos vizinhos:", neighbors)
        to_territory = ask_str("Qual território deseja atacar? ", valid_options=neighbors)
        max_dice = min(3, state.territories[from_territory].armies - 1)
        dice = ask_int(f"Quantos dados quer usar para atacar? (1 a {max_dice}): ", min_val=1, max_val=max_dice)
        try:
            result = tm.do_attack(from_territory, to_territory, dice)
        except RuleError as e:
            print("Jogada inválida:", e)
            continue
        print("Resultado do ataque:", result)
        if result["eliminated"] is not None:
            print(f"{state.players[result['eliminated']].name} foi eliminado!")
        if state.winner_id is not None or not ask_yes_no("Quer atacar novamente?"):
            break

def main():
    state = initial_setup(3)
    tm = TurnManager(state, DATA_DIR)
    while state.winner_id is None:
        p = state.current_player()
        print(f"\n=== Turno de {p.name} ({p.color}) ===")
        print("Missão:", state.missions[p.id].description)
        reinf = tm.start_turn()
        print(f"Reforços disponíveis: {reinf}")

        prompt_placement(tm)
        prompt_attack(tm)
        if state.winner_id is None:
            tm.end_turn()

    winner = state.players[state.winner_id]
    print(f"\n*** {winner.name} ({winner.color}) venceu a partida! ***")

if __name__ == "__main__":
    main()
