import json
from war_game.services.map_loader import load_map

def test_map_has_42_territories(data_dir):
    assert len(load_map(data_dir)) == 42

def test_neighbors_exist_and_are_symmetric(data_dir):
    territories = load_map(data_dir)
    for t in territories.values():
        assert t.name not in t.neighbors
        for n in t.neighbors:
            assert n in territories, f"{t.name} -> {n} não existe"
            assert t.name in territories[n].neighbors, f"{n} não lista {t.name} como vizinho"

def test_map_is_connected(data_dir):
    territories = load_map(data_dir)
    start = next(iter(territories))
    seen, stack = {start}, [start]
    while stack:
        for n in territories[stack.pop()].neighbors:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    assert seen == set(territories)

def test_continents_match_map(data_dir):
    continents = {c["name"] for c in json.loads((data_dir / "continents.json").read_text(encoding="utf-8"))}
    assert continents == {t.continent for t in load_map(data_dir).values()}

def test_cards_are_valid(data_dir):
    territories = load_map(data_dir)
    cards = json.loads((data_dir / "cards.json").read_text(encoding="utf-8"))
    assert len({c["id"] for c in cards}) == len(cards)
    for c in cards:
        assert c["icon"] in {"infantry", "cavalry", "artillery", "wild"}
        assert (c["territory"] is None) == (c["icon"] == "wild")
        assert c["territory"] is None or c["territory"] in territories
