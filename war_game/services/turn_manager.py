from pathlib import Path
from war_game.rules.reinforcements import calc_total_reinforcements
from war_game.rules.cards import redeem_cards
from war_game.rules.combat import attack_once, max_defend_dice
from war_game.models.game_state import GameState
from war_game.rules.errors import RuleError

class TurnManager:
    def __init__(self, state: GameState, data_dir: Path):
        self.state = state
        self.data_dir = data_dir
        self.trades_done = 0

    def start_turn(self) -> int:
        self.state.conquered_this_turn = False
        return calc_total_reinforcements(self.state, self.data_dir)

    def place_reinforcements(self, placements: dict):
        player = self.state.current_player()
        for territory, count in placements.items():
            if territory not in player.territories:
                raise RuleError(f"{territory} não pertence ao jogador da vez.")
            if type(count) is not int or count < 1:
                raise RuleError("A quantidade de tropas deve ser um inteiro positivo.")
        for territory, count in placements.items():
            self.state.territories[territory].armies += count

    def trade_cards_if_any(self, chosen=None) -> int:
        if chosen:
            gained = redeem_cards(self.state, self.data_dir, chosen, self.trades_done)
            self.trades_done += 1
            return gained
        return 0

    def do_attack(self, from_t: str, to_t: str, attack_dice: int) -> dict:
        if to_t not in self.state.territories:
            raise RuleError("Território inexistente.")
        defend_dice = max_defend_dice(self.state.territories[to_t].armies)
        return attack_once(self.state, from_t, to_t, attack_dice, defend_dice)

    def end_turn(self):
        if self.state.conquered_this_turn and self.state.deck:
            self.state.current_player().cards.append(self.state.deck.pop())
        self.state.current_player_index = (self.state.current_player_index + 1) % len(self.state.players)
