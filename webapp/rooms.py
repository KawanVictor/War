import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from war_game.models.game_state import GameState
from war_game.rules.errors import RuleError
from war_game.services.serialization import state_from_json, state_to_json
from war_game.services.setup import MAX_PLAYERS, MIN_PLAYERS, new_game
from war_game.services.turn_manager import TurnManager

DATA_DIR = Path(__file__).resolve().parents[1] / "war_game" / "data"

MAX_ROOMS = 200
MAX_ROOM_ID_LENGTH = 40
DEFAULT_TTL_HOURS = 24.0

class Room:
    """Uma sala: primeiro uma sala de espera, depois uma partida.

    Cada pessoa é identificada por um token guardado no navegador, de modo que quem
    recarrega a página ou perde a conexão volta para o mesmo assento.
    """

    def __init__(self, room_id: str):
        self.id = room_id
        self.num_players = 3
        self.members: List[str] = []  # tokens na ordem de chegada; o primeiro é o anfitrião
        self.seats: Dict[str, int] = {}  # token -> assento, definido quando a partida começa
        self.bots: Set[int] = set()  # assentos jogados pelo computador
        self.substituted: Set[int] = set()  # assentos de pessoas ausentes que o computador assumiu
        self.state: Optional[GameState] = None
        self.tm: Optional[TurnManager] = None
        self.last_activity = time.time()

    @property
    def started(self) -> bool:
        return self.state is not None

    def touch(self):
        self.last_activity = time.time()

    def host(self) -> Optional[str]:
        return self.members[0] if self.members else None

    def add_member(self, token: str) -> bool:
        """Coloca alguém na sala de espera. Devolve False se já não há lugar."""
        if token in self.members:
            return True
        if self.started or len(self.members) >= MAX_PLAYERS:
            return False
        self.members.append(token)
        return True

    def remove_member(self, token: str):
        if not self.started and token in self.members:
            self.members.remove(token)

    def seat_of(self, token: str) -> Optional[int]:
        """Assento do jogador na partida, ou a posição na sala de espera. None para espectadores."""
        if self.started:
            return self.seats.get(token)
        return self.members.index(token) if token in self.members else None

    def configure(self, num_players):
        if self.started:
            raise RuleError("A partida já começou.")
        if type(num_players) is not int or not MIN_PLAYERS <= num_players <= MAX_PLAYERS:
            raise RuleError(f"O número de jogadores deve estar entre {MIN_PLAYERS} e {MAX_PLAYERS}.")
        self.num_players = num_players

    def start(self):
        """Começa a partida: quem está na sala ocupa os primeiros assentos e o computador joga os demais."""
        if self.started:
            raise RuleError("A partida já começou.")
        if not self.members:
            raise RuleError("Não há ninguém na sala.")
        humans = self.members[:self.num_players]
        self.state = new_game(DATA_DIR, self.num_players)
        self.tm = TurnManager(self.state, DATA_DIR)
        self.seats = {token: seat for seat, token in enumerate(humans)}
        self.bots = set(range(len(humans), self.num_players))

    def substitute(self, seat: int):
        """Passa para o computador o lugar de uma pessoa que saiu. Ela reassume quando voltar."""
        if not self.started or seat not in self.seats.values():
            raise RuleError("Esse lugar não é de uma pessoa.")
        if seat in self.bots:
            raise RuleError("Esse lugar já está com o computador.")
        self.bots.add(seat)
        self.substituted.add(seat)

    def restore(self, seat: Optional[int]) -> bool:
        """Devolve o lugar à pessoa que voltou. Diz se havia algo a devolver."""
        if seat is None or seat not in self.substituted:
            return False
        self.substituted.discard(seat)
        self.bots.discard(seat)
        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "num_players": self.num_players,
            "members": self.members,
            "seats": self.seats,
            "bots": sorted(self.bots),
            "substituted": sorted(self.substituted),
            "last_activity": self.last_activity,
            "state": state_to_json(self.state) if self.state else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        room = cls(data["id"])
        room.num_players = data["num_players"]
        room.members = list(data["members"])
        room.seats = {token: int(seat) for token, seat in data["seats"].items()}
        room.bots = set(data["bots"])
        room.substituted = set(data.get("substituted", []))
        room.last_activity = data["last_activity"]
        if data["state"]:
            room.state = state_from_json(data["state"])
            room.tm = TurnManager(room.state, DATA_DIR)
        return room

class RoomManager:
    """Guarda as salas em memória e, se houver um diretório configurado, salva as partidas em disco."""

    def __init__(self, storage_dir: Optional[Path] = None, ttl_hours: float = DEFAULT_TTL_HOURS):
        self.rooms: Dict[str, Room] = {}
        self.storage_dir = storage_dir
        self.ttl_seconds = ttl_hours * 3600
        if storage_dir:
            storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_all()

    def _path(self, room_id: str) -> Path:
        # O nome do arquivo vem de um hash, então o id da sala nunca vira um caminho
        assert self.storage_dir is not None
        return self.storage_dir / (hashlib.sha256(room_id.encode("utf-8")).hexdigest()[:32] + ".json")

    def _load_all(self):
        assert self.storage_dir is not None
        for path in self.storage_dir.glob("*.json"):
            try:
                room = Room.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, KeyError, TypeError, OSError):
                continue  # arquivo corrompido ou de outra versão: a sala é ignorada
            self.rooms[room.id] = room

    def get(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def get_or_create(self, room_id: str) -> Room:
        if room_id not in self.rooms:
            if len(self.rooms) >= MAX_ROOMS:
                raise RuleError("O servidor atingiu o limite de salas. Tente mais tarde.")
            self.rooms[room_id] = Room(room_id)
        return self.rooms[room_id]

    def save(self, room: Room):
        """Registra atividade e grava a partida. Salas de espera não vão para o disco."""
        room.touch()
        if not self.storage_dir or not room.started:
            return
        path = self._path(room.id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(room.to_dict(), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def remove(self, room_id: str):
        self.rooms.pop(room_id, None)
        if self.storage_dir:
            self._path(room_id).unlink(missing_ok=True)

    def purge_stale(self, now: Optional[float] = None) -> List[str]:
        """Remove as salas sem atividade há mais tempo que o limite. Devolve os ids removidos."""
        now = time.time() if now is None else now
        stale = [rid for rid, room in self.rooms.items() if now - room.last_activity > self.ttl_seconds]
        for rid in stale:
            self.remove(rid)
        return stale

def _from_env() -> RoomManager:
    storage = os.environ.get("WAR_DATA_DIR", str(Path(__file__).resolve().parents[1] / "instance" / "rooms"))
    ttl = float(os.environ.get("WAR_ROOM_TTL_HOURS", DEFAULT_TTL_HOURS))
    return RoomManager(Path(storage) if storage else None, ttl)

rooms = _from_env()
