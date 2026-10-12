from pathlib import Path
from war_game.rules.cards import can_redeem_set, next_trade_value
from war_game.rules.errors import RuleError
from war_game.services.setup import new_game
from war_game.services.turn_manager import TurnManager
from war_game.cli.prompts import ask_int, ask_yes_no

DATA_DIR = Path(__file__).resolve().parents[2] / "war_game" / "data"

COLOR_LABELS = {"red": "vermelho", "blue": "azul", "green": "verde", "yellow": "amarelo", "purple": "roxo", "black": "preto"}
ICON_LABELS = {"infantry": "Infantaria", "cavalry": "Cavalaria", "artillery": "Artilharia", "wild": "Curinga"}

def initial_setup(num_players=3):
    return new_game(DATA_DIR, num_players)

def player_label(player):
    return f"{player.name} ({COLOR_LABELS.get(player.color, player.color)})"

def choose_territory(state, prompt, names, allow_skip=False):
    """Mostra um menu numerado de territórios e devolve o escolhido (ou None se o jogador pular)."""
    names = sorted(names, key=lambda n: state.territories[n].label)
    for i, n in enumerate(names, 1):
        t = state.territories[n]
        print(f"  {i:2}. {t.label} ({t.armies})")
    if allow_skip:
        print("   0. Pular")
    choice = ask_int(prompt, min_val=0 if allow_skip else 1, max_val=len(names))
    return names[choice - 1] if choice else None

def describe_card(state, defs, card_id):
    card = defs[card_id]
    icon = ICON_LABELS.get(card["icon"], card["icon"])
    return icon if not card["territory"] else f"{icon} - {state.territories[card['territory']].label}"

def prompt_trade(tm):
    state = tm.state
    player = state.current_player()
    defs = tm.card_defs()
    if player.cards:
        print("Suas cartas:", "; ".join(describe_card(state, defs, c) for c in player.cards))
    while True:
        combos = can_redeem_set(player.cards, defs)
        if not combos:
            break
        value = next_trade_value(tm.trades_done)
        print(f"Trocas possíveis (valem {value} tropas):")
        for i, combo in enumerate(combos, 1):
            print(f"  {i:2}. " + "; ".join(describe_card(state, defs, c) for c in combo))
        print("   0. Não trocar")
        choice = ask_int("Qual troca deseja fazer? ", min_val=0, max_val=len(combos))
        if not choice:
            break
        gained = tm.trade_cards_if_any(combos[choice - 1])
        print(f"Troca feita: +{gained} tropas. Reforços disponíveis: {state.reinforcements_left}")

def prompt_placement(tm):
    state = tm.state
    player = state.current_player()
    while state.reinforcements_left > 0 and state.winner_id is None:
        total = state.reinforcements_left
        print(f"Onde colocar tropas? (restam {total})")
        territory = choose_territory(state, "Território: ", player.territories)
        label = state.territories[territory].label
        qty = ask_int(f"Quantas tropas colocar em {label}? ", min_val=1, max_val=total)
        tm.place_reinforcements({territory: qty})

def prompt_attack(tm):
    state = tm.state
    player = state.current_player()
    while state.winner_id is None:
        attack_from = [
            t for t in player.territories
            if state.territories[t].armies > 1
            and any(state.territories[n].owner_id != player.id for n in state.territories[t].neighbors)
        ]
        if not attack_from:
            print("Nenhum território em condições de atacar.")
            break
        print("De qual território deseja atacar?")
        from_territory = choose_territory(state, "Território: ", attack_from, allow_skip=True)
        if from_territory is None:
            break
        neighbors = [n for n in state.territories[from_territory].neighbors if state.territories[n].owner_id != player.id]
        print("Qual território deseja atacar?")
        to_territory = choose_territory(state, "Território: ", neighbors, allow_skip=True)
        if to_territory is None:
            continue
        max_dice = min(3, state.territories[from_territory].armies - 1)
        dice = ask_int(f"Quantos dados quer usar para atacar? (1 a {max_dice}): ", min_val=1, max_val=max_dice)
        try:
            result = tm.do_attack(from_territory, to_territory, dice)
        except RuleError as e:
            print("Jogada inválida:", e)
            continue
        print(f"Dados do ataque: {result['attacker_rolls']} | dados da defesa: {result['defender_rolls']}")
        print(f"Ataque perdeu {result['losses_attacker']}, defesa perdeu {result['losses_defender']}.")
        if result["conquered"]:
            print(f"{state.territories[to_territory].label} foi conquistado!")
        if result["eliminated"] is not None:
            print(f"{player_label(state.players[result['eliminated']])} foi eliminado!")
        if state.winner_id is not None or not ask_yes_no("Quer atacar novamente?"):
            break

def prompt_fortify(tm):
    state = tm.state
    player = state.current_player()
    if state.winner_id is not None or not ask_yes_no("Deseja remanejar tropas?"):
        return
    tm.begin_fortify()
    while state.winner_id is None:
        sources = [
            t for t in player.territories
            if tm.max_fortify(t) > 0 and any(n in player.territories for n in state.territories[t].neighbors)
        ]
        if not sources:
            print("Não há mais tropas que possam ser remanejadas.")
            break
        print("De qual território deseja mover tropas?")
        from_territory = choose_territory(state, "Território: ", sources, allow_skip=True)
        if from_territory is None:
            break
        targets = [n for n in state.territories[from_territory].neighbors if n in player.territories]
        print("Para qual território?")
        to_territory = choose_territory(state, "Território: ", targets, allow_skip=True)
        if to_territory is None:
            continue
        qty = ask_int("Quantas tropas mover? ", min_val=1, max_val=tm.max_fortify(from_territory))
        tm.fortify(from_territory, to_territory, qty)

def main():
    state = initial_setup(3)
    tm = TurnManager(state, DATA_DIR)
    while state.winner_id is None:
        p = state.current_player()
        print(f"\n=== Turno de {player_label(p)} ===")
        print("Missão:", state.missions[p.id].description)
        reinf = tm.start_turn()
        print(f"Reforços disponíveis: {reinf}")

        prompt_trade(tm)
        prompt_placement(tm)
        prompt_attack(tm)
        prompt_fortify(tm)
        if state.winner_id is None:
            tm.end_turn()

    print(f"\n*** {player_label(state.players[state.winner_id])} venceu a partida! ***")

if __name__ == "__main__":
    main()
