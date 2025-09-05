from war_game.rules.cards import can_redeem_set

def test_redeem_combos():
    cards = ["c1", "c1", "c2", "c3"]
    card_defs = {
        "c1": {"icon": "infantry"},
        "c2": {"icon": "cavalry"},
        "c3": {"icon": "artillery"},
    }
    combos = can_redeem_set(cards, card_defs)
    assert any(isinstance(c, tuple) and len(c) == 3 for c in combos)
