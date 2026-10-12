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

MAX_CARDS_WITHOUT_TRADE = 4  # com 5 ou mais cartas a troca é obrigatória

class TurnManager:
    """Aplica as jogadas sobre um GameState. Todo o estado da partida fica no GameState."""

    def __init__(self, state: GameState, data_dir: Path):
        self.state = state
        self.data_dir = data_dir
        self._card_defs: dict = {}

    @property
    def trades_done(self) -> int:
        return self.state.trades_done

    @trades_done.setter
    def trades_done(self, value: int):
        self.state.trades_done = value

    def _require_phase(self, phases, message: str):
        if self.state.winner_id is not None:
            raise RuleError("A partida já terminou.")
        if self.state.phase not in ([phases] if isinstance(phases, str) else phases):
            raise RuleError(message)

    def _label(self, territory: str) -> str:
        return self.state.territories[territory].label

    def card_defs(self) -> dict:
        if not self._card_defs:
            cards = json.loads((self.data_dir / "cards.json").read_text(encoding="utf-8"))
            self._card_defs = {c["id"]: c for c in cards}
        return self._card_defs

    def _check_victory(self):
        player = self.state.current_player()
        remaining = [p for p in self.state.players if p.territories]
        if len(remaining) == 1:
            self.state.winner_id = remaining[0].id
        elif check_victory_by_mission(self.state, player.id):
            self.state.winner_id = player.id

    def in_setup_round(self) -> bool:
        """Na primeira rodada cada jogador só posiciona tropas; não há ataque nem remanejamento."""
        return self.state.setup_turns_left > 0

    def must_trade(self) -> bool:
        return len(self.state.current_player().cards) > MAX_CARDS_WITHOUT_TRADE

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
        if self.must_trade():
            raise RuleError("Com 5 ou mais cartas é obrigatório trocar antes de posicionar as tropas.")
        for territory, count in placements.items():
            if territory not in self.state.territories:
                raise RuleError("Território inexistente.")
            if territory not in player.territories:
                raise RuleError(f"{self._label(territory)} não pertence ao jogador da vez.")
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
        defs = self.card_defs()
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
        if self.in_setup_round():
            raise RuleError("Na primeira rodada só se posicionam tropas; os ataques começam na rodada seguinte.")
        if to_t not in self.state.territories:
            raise RuleError("Território inexistente.")
        defender = self.state.territories[to_t]
        defender_id = defender.owner_id
        if defender_id is None:
            raise RuleError(f"{defender.label} não tem dono.")
        defend_dice = max_defend_dice(defender.armies)
        self.state.conquest = None
        result = attack_once(self.state, from_t, to_t, attack_dice, defend_dice)
        result["eliminated"] = None
        if result["conquered"]:
            self.state.conquest = {"from": from_t, "to": to_t}
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

    def max_occupy(self) -> int:
        """Quantas tropas a mais podem seguir para o território recém-conquistado."""
        conquest = self.state.conquest
        if self.state.phase != "attacking" or not conquest:
            return 0
        return max(0, self.state.territories[conquest["from"]].armies - 1)

    def occupy(self, count: int):
        """Move mais tropas do território atacante para o que acabou de ser conquistado."""
        self._require_phase("attacking", "Não há território recém-conquistado para ocupar.")
        conquest = self.state.conquest
        if not conquest:
            raise RuleError("Não há território recém-conquistado para ocupar.")
        if type(count) is not int or count < 1:
            raise RuleError("A quantidade de tropas deve ser um inteiro positivo.")
        if count > self.max_occupy():
            raise RuleError(f"Só é possível mover mais {self.max_occupy()} tropa(s).")
        self.state.territories[conquest["from"]].armies -= count
        self.state.territories[conquest["to"]].armies += count
        self._check_victory()

    def begin_fortify(self):
        """Encerra os ataques e abre o remanejamento. Cada tropa só pode se mover uma vez por turno."""
        self._require_phase("attacking", "O remanejamento só começa depois da fase de ataque.")
        if self.in_setup_round():
            raise RuleError("Na primeira rodada só se posicionam tropas; não há remanejamento.")
        player = self.state.current_player()
        self.state.conquest = None
        # Tropas que ainda podem ser remanejadas a partir de cada território neste turno
        self.state.movable = {t: self.state.territories[t].armies for t in player.territories}
        self.state.phase = "fortifying"

    def max_fortify(self, from_t: str) -> int:
        """Quantas tropas ainda podem sair de `from_t` no remanejamento (sempre fica pelo menos uma)."""
        if self.state.phase != "fortifying" or from_t not in self.state.movable:
            return 0
        return max(0, min(self.state.movable[from_t], self.state.territories[from_t].armies - 1))

    def fortify(self, from_t: str, to_t: str, count: int):
        self._require_phase("fortifying", "Não é hora de remanejar tropas.")
        player = self.state.current_player()
        if from_t not in self.state.territories or to_t not in self.state.territories:
            raise RuleError("Território inexistente.")
        if from_t not in player.territories or to_t not in player.territories:
            raise RuleError("Só é possível remanejar entre territórios próprios.")
        if to_t not in self.state.territories[from_t].neighbors:
            raise RuleError(f"{self._label(to_t)} não faz fronteira com {self._label(from_t)}.")
        if type(count) is not int or count < 1:
            raise RuleError("A quantidade de tropas deve ser um inteiro positivo.")
        if count > self.max_fortify(from_t):
            raise RuleError(f"Só é possível mover {self.max_fortify(from_t)} tropa(s) de {self._label(from_t)}.")
        self.state.territories[from_t].armies -= count
        self.state.territories[to_t].armies += count
        self.state.movable[from_t] -= count
        self._check_victory()

    def end_turn(self):
        self._require_phase(("attacking", "fortifying"), "Inicie o turno e posicione todos os reforços antes de encerrar.")
        state = self.state
        state.movable = {}
        state.conquest = None
        if state.setup_turns_left > 0:
            state.setup_turns_left -= 1
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
