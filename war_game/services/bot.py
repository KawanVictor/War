"""Jogador controlado pelo computador. Joga um turno inteiro usando só as jogadas do TurnManager."""
from typing import List
from war_game.rules.cards import can_redeem_set
from war_game.services.turn_manager import TurnManager

MAX_ATTACKS_PER_TURN = 60

def _enemy_neighbors(tm: TurnManager, name: str) -> List[str]:
    state = tm.state
    owner = state.territories[name].owner_id
    return [n for n in state.territories[name].neighbors if state.territories[n].owner_id != owner]

def _threat(tm: TurnManager, name: str) -> int:
    """Tropas inimigas vizinhas menos as tropas do próprio território."""
    state = tm.state
    return sum(state.territories[n].armies for n in _enemy_neighbors(tm, name)) - state.territories[name].armies

def _trade(tm: TurnManager):
    player = tm.state.current_player()
    while tm.state.winner_id is None:
        combos = can_redeem_set(player.cards, tm.card_defs())
        if not combos:
            break
        tm.trade_cards_if_any(combos[0])

def _place(tm: TurnManager):
    state = tm.state
    player = state.current_player()
    while state.reinforcements_left > 0 and state.winner_id is None:
        border = [t for t in player.territories if _enemy_neighbors(tm, t)]
        # Sem fronteira inimiga não há o que defender; qualquer território serve
        target = max(border or sorted(player.territories), key=lambda t: (_threat(tm, t), t))
        tm.place_reinforcements({target: 1})

def _attack(tm: TurnManager) -> List[dict]:
    state = tm.state
    player = state.current_player()
    log = []
    for _ in range(MAX_ATTACKS_PER_TURN):
        if state.winner_id is not None:
            break
        options = [
            (state.territories[a].armies - state.territories[b].armies, a, b)
            for a in player.territories if state.territories[a].armies >= 3
            for b in _enemy_neighbors(tm, a)
            if state.territories[a].armies > state.territories[b].armies + 1
        ]
        if not options:
            break
        _, src, dst = max(options)
        result = tm.do_attack(src, dst, min(3, state.territories[src].armies - 1))
        log.append({"from": src, "to": dst, **result})
        if result["conquered"] and state.winner_id is None:
            # Leva o grosso das tropas adiante se o território de origem ficou sem inimigos por perto
            spare = tm.max_occupy()
            if spare > 0:
                keep = 0 if not _enemy_neighbors(tm, src) else spare // 2
                if spare - keep > 0:
                    tm.occupy(spare - keep)
    return log

def _fortify(tm: TurnManager):
    state = tm.state
    player = state.current_player()
    tm.begin_fortify()
    # Distância, em territórios próprios, de cada território até a fronteira com um inimigo
    distance = {t: 0 for t in player.territories if _enemy_neighbors(tm, t)}
    queue = sorted(distance)
    while queue:
        current = queue.pop(0)
        for n in sorted(state.territories[current].neighbors):
            if n in player.territories and n not in distance:
                distance[n] = distance[current] + 1
                queue.append(n)
    # Tropas de territórios cercados só por aliados dão um passo na direção da fronteira
    for src in sorted(player.territories):
        if state.winner_id is not None:
            break
        if distance.get(src, 0) == 0 or tm.max_fortify(src) == 0:
            continue
        closer = [n for n in state.territories[src].neighbors if distance.get(n, distance[src]) < distance[src]]
        if closer:
            dst = max(closer, key=lambda t: (-distance[t], _threat(tm, t), t))
            tm.fortify(src, dst, tm.max_fortify(src))

def play_turn(tm: TurnManager) -> List[dict]:
    """Joga o turno do jogador da vez até o fim e devolve a lista de ataques feitos.

    O turno pode já estar em andamento (quando o computador assume o lugar de quem saiu):
    o computador continua da fase em que a partida está.
    """
    state = tm.state
    log: List[dict] = []
    if state.phase == "waiting":
        tm.start_turn()
    if state.phase == "placing":
        _trade(tm)
        _place(tm)
    if state.winner_id is None and state.phase == "attacking" and not tm.in_setup_round():
        log = _attack(tm)
        if state.winner_id is None:
            _fortify(tm)
    if state.winner_id is None:
        tm.end_turn()
    return log
