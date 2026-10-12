"""Converte um GameState em um dicionário JSON e de volta, para salvar partidas em disco."""
from dataclasses import asdict
from war_game.models.game_state import GameState
from war_game.models.mission import Mission
from war_game.models.player import Player
from war_game.models.territory import Territory

FORMAT_VERSION = 1

def state_to_json(state: GameState) -> dict:
    return {
        "version": FORMAT_VERSION,
        "territories": [
            {"name": t.name, "label": t.label, "continent": t.continent, "neighbors": sorted(t.neighbors),
             "owner_id": t.owner_id, "armies": t.armies}
            for t in state.territories.values()
        ],
        "players": [
            {"id": p.id, "name": p.name, "color": p.color, "alive": p.alive, "eliminated_by": p.eliminated_by,
             "territories": sorted(p.territories), "cards": list(p.cards)}
            for p in state.players
        ],
        "deck": list(state.deck),
        "discard": list(state.discard),
        "missions": {str(pid): asdict(m) for pid, m in (state.missions or {}).items()},
        "current_player_index": state.current_player_index,
        "conquered_this_turn": state.conquered_this_turn,
        "phase": state.phase,
        "reinforcements_left": state.reinforcements_left,
        "winner_id": state.winner_id,
        "trades_done": state.trades_done,
        "movable": dict(state.movable),
        "conquest": dict(state.conquest) if state.conquest else None,
        "setup_turns_left": state.setup_turns_left,
    }

def state_from_json(data: dict) -> GameState:
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"Versão de partida salva não suportada: {data.get('version')!r}")
    territories = {
        t["name"]: Territory(name=t["name"], continent=t["continent"], neighbors=set(t["neighbors"]),
                             owner_id=t["owner_id"], armies=t["armies"], label=t["label"])
        for t in data["territories"]
    }
    players = [
        Player(id=p["id"], name=p["name"], color=p["color"], alive=p["alive"], eliminated_by=p["eliminated_by"],
               territories=set(p["territories"]), cards=list(p["cards"]))
        for p in data["players"]
    ]
    return GameState(
        territories=territories,
        players=players,
        deck=list(data["deck"]),
        discard=list(data["discard"]),
        missions={int(pid): Mission(**m) for pid, m in data["missions"].items()},
        current_player_index=data["current_player_index"],
        conquered_this_turn=data["conquered_this_turn"],
        phase=data["phase"],
        reinforcements_left=data["reinforcements_left"],
        winner_id=data["winner_id"],
        trades_done=data["trades_done"],
        movable=dict(data["movable"]),
        conquest=dict(data["conquest"]) if data["conquest"] else None,
        setup_turns_left=data["setup_turns_left"],
    )
