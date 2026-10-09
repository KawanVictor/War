from war_game.models.game_state import GameState
from war_game.models.mission import Mission
from war_game.rules.reinforcements import has_full_continent

FALLBACK_TERRITORIES = 24  # objetivo de quem recebe a missão de destruir a própria cor

def is_mission_complete(state: GameState, player_id: int, mission: Mission) -> bool:
    player = state.players[player_id]

    if mission.target_color is not None:
        target = next((p for p in state.players if p.color == mission.target_color), None)
        if target is None or target.id == player_id:
            return len(player.territories) >= FALLBACK_TERRITORIES
        if target.territories:
            return False

    if mission.continents or mission.extra_continents:
        owned = {t.continent for t in state.territories.values()
                 if has_full_continent(state, player_id, t.continent)}
        if not set(mission.continents) <= owned:
            return False
        if len(owned - set(mission.continents)) < mission.extra_continents:
            return False

    if mission.territories_required is not None:
        counted = [t for t in player.territories if state.territories[t].armies >= mission.min_armies]
        if len(counted) < mission.territories_required:
            return False

    return True

def check_victory_by_mission(state: GameState, player_id: int) -> bool:
    mission = (state.missions or {}).get(player_id)
    if mission is None:
        return False
    return is_mission_complete(state, player_id, mission)
