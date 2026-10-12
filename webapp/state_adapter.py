import json
from war_game.rules.cards import can_redeem_set, next_trade_value

def continents_to_list(data_dir):
    data = json.loads((data_dir / "continents.json").read_text(encoding="utf-8"))
    return [{"name": c["name"], "label": c.get("label", c["name"]), "bonus": c["bonus"]} for c in data]

def territory_to_dict(t):
    return {
        "name": t.name,
        "label": t.label,
        "continent": t.continent,
        "neighbors": list(t.neighbors),
        "ownerId": t.owner_id,
        "armies": t.armies
    }

def player_to_dict(p):
    # A mão é secreta: os outros jogadores só veem a quantidade de cartas
    return {
        "id": p.id,
        "name": p.name,
        "color": p.color,
        "alive": p.alive,
        "territories": list(p.territories),
        "cardCount": len(p.cards)
    }

def state_to_dict(state, tm=None):
    # As missões são secretas e não entram aqui; cada jogador recebe a sua em separado
    return {
        "territories": {k: territory_to_dict(v) for k, v in state.territories.items()},
        "players": [player_to_dict(p) for p in state.players],
        "currentPlayerIndex": state.current_player_index,
        "deckCount": len(state.deck),
        "phase": state.phase,
        "reinforcementsLeft": state.reinforcements_left,
        "winnerId": state.winner_id,
        "continents": continents_to_list(tm.data_dir) if tm else [],
        "nextTradeValue": next_trade_value(tm.trades_done) if tm else None,
        # Tropas que cada território ainda pode ceder no remanejamento
        "movable": {t: tm.max_fortify(t) for t in state.current_player().territories}
                   if tm and state.phase == "fortifying" else {}
    }

def hand_to_dict(state, tm, player_id):
    """Cartas de um jogador, com as trocas possíveis. Enviado só para o dono."""
    defs = tm.card_defs()
    cards = state.players[player_id].cards
    return {
        "cards": [
            {
                "id": cid,
                "icon": defs[cid]["icon"],
                "territory": state.territories[defs[cid]["territory"]].label if defs[cid]["territory"] else None,
            }
            for cid in cards
        ],
        "combos": [list(c) for c in can_redeem_set(cards, defs)],
    }
