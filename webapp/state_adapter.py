def territory_to_dict(t):
    return {
        "name": t.name,
        "continent": t.continent,
        "neighbors": list(t.neighbors),
        "ownerId": t.owner_id,
        "armies": t.armies
    }

def player_to_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "color": p.color,
        "alive": p.alive,
        "territories": list(p.territories),
        "cards": p.cards
    }

def state_to_dict(state):
    return {
        "territories": {k: territory_to_dict(v) for k, v in state.territories.items()},
        "players": [player_to_dict(p) for p in state.players],
        "currentPlayerIndex": state.current_player_index,
        "deckCount": len(state.deck)
    }
