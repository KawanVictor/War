import json
import random
from collections import Counter
from pathlib import Path
from war_game.rules.reinforcements import calc_total_reinforcements
from war_game.rules.cards import can_redeem_set, redeem_cards
from war_game.rules.combat import attack_once, max_defend_dice
from war_game.rules.missions import check_victory_by_mission
from war_game.models.game_state import GameState
from war_game.rules.errors import RuleError

class TurnManager:
    def __init__(self, state: GameState, data_dir: Path):
        self.state = state
        self.data_dir = data_dir
        self.trades_done = 0

    def _require_phase(self, phase: str, message: str):
        if self.state.winner_id is not None:
            raise RuleError("A partida já terminou.")
        if self.state.phase != phase:
            raise RuleError(message)

    def _check_victory(self):
        player = self.state.current_player()
        remaining = [p for p in self.state.players if p.territories]
        if len(remaining) == 1:
            self.state.winner_id = remaining[0].id
        elif check_victory_by_mission(self.state, player.id):
            self.state.winner_id = player.id

    def start_turn(self) -> int:
        self._require_phase("waiting", "O turno já foi iniciado.")
        self.state.conquered_this_turn = False
        reinforcements = calc_total_reinforcements(self.state, self.data_dir)
        self.state.reinforcements_left = reinforcements
        self.state.phase = "placing"
        return reinforcements

    def place_reinforcements(self, placements: dict):
        self._require_phase("placing", "Não é hora de posicionar tropas.")
        player = self.state.current_player()
        for territory, count in placements.items():
            if territory not in player.territories:
                raise RuleError(f"{territory} não pertence ao jogador da vez.")
            if type(count) is not int or count < 1:
                raise RuleError("A quantidade de tropas deve ser um inteiro positivo.")
        total = sum(placements.values())
        if total > self.state.reinforcements_left:
            raise RuleError(f"Só restam {self.state.reinforcements_left} reforço(s) para posicionar.")
        for territory, count in placements.items():
            self.state.territories[territory].armies += count
        self.state.reinforcements_left -= total
        if self.state.reinforcements_left == 0:
            self.state.phase = "attacking"
        self._check_victory()

    def trade_cards_if_any(self, chosen=None) -> int:
        if not chosen:
            return 0
        self._require_phase("placing", "Cartas só podem ser trocadas antes de posicionar os reforços.")
        chosen = tuple(chosen)
        player = self.state.current_player()
        defs = {c["id"]: c for c in json.loads((self.data_dir / "cards.json").read_text(encoding="utf-8"))}
        if len(chosen) != 3 or Counter(chosen) - Counter(player.cards):
            raise RuleError("Escolha 3 cartas da sua mão.")
        if not can_redeem_set(list(chosen), defs):
            raise RuleError("As cartas escolhidas não formam uma troca válida.")
        gained = redeem_cards(self.state, self.data_dir, chosen, self.trades_done)
        self.trades_done += 1
        self.state.reinforcements_left += gained
        return gained

    def do_attack(self, from_t: str, to_t: str, attack_dice: int) -> dict:
        self._require_phase("attacking", "Inicie o turno e posicione todos os reforços antes de atacar.")
        if to_t not in self.state.territories:
            raise RuleError("Território inexistente.")
        defender = self.state.territories[to_t]
        defender_id = defender.owner_id
        defend_dice = max_defend_dice(defender.armies)
        result = attack_once(self.state, from_t, to_t, attack_dice, defend_dice)
        result["eliminated"] = None
        if result["conquered"]:
            loser = self.state.players[defender_id]
            if not loser.territories:
                attacker = self.state.current_player()
                loser.alive = False
                loser.eliminated_by = attacker.id
                attacker.cards.extend(loser.cards)
                loser.cards.clear()
                result["eliminated"] = loser.id
            self._check_victory()
        return result

    def end_turn(self):
        self._require_phase("attacking", "Inicie o turno e posicione todos os reforços antes de encerrar.")
        state = self.state
        if state.conquered_this_turn:
            if not state.deck and state.discard:
                state.deck, state.discard = state.discard, []
                random.shuffle(state.deck)
            if state.deck:
                state.current_player().cards.append(state.deck.pop())
        for _ in state.players:
            state.current_player_index = (state.current_player_index + 1) % len(state.players)
            if state.current_player().alive:
                break
        state.phase = "waiting"
        state.reinforcements_left = 0
