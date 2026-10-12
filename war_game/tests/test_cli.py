import builtins
import random
import pytest
from war_game.cli import main as cli

def test_default_arguments():
    args = cli.parse_args([])
    assert (args.jogadores, args.computador) == (3, 0)

@pytest.mark.parametrize("argv", [
    ["--jogadores", "1"], ["--jogadores", "7"],
    ["--jogadores", "3", "--computador", "3"],   # ninguém para jogar
    ["--computador", "-1"],
])
def test_invalid_arguments(argv):
    with pytest.raises(SystemExit):
        cli.parse_args(argv)

@pytest.mark.parametrize("seed", [0, 1, 2])
def test_one_person_against_computers_plays_to_the_end(seed, monkeypatch, capsys):
    """Uma pessoa que só posiciona tropas e nunca ataca: os menus funcionam e a partida termina."""
    random.seed(seed)
    transcript = []
    calls = 0

    def fake_input(prompt=""):
        nonlocal calls
        calls += 1
        assert calls < 20000, "o jogo não terminou"
        shown = capsys.readouterr().out  # o que foi impresso desde a última resposta
        transcript.append(shown)
        if "(s/n)" in prompt:
            return "n"
        # Menus que permitem pular (ataque) ou recusar (troca opcional) recebem 0; os demais, a primeira opção
        return "0" if "0. Pular" in shown or "0. Não trocar" in shown else "1"

    monkeypatch.setattr(builtins, "input", fake_input)
    cli.main(["--jogadores", "3", "--computador", "2"])
    output = "".join(transcript) + capsys.readouterr().out
    assert "venceu a partida" in output
    assert "jogado pelo computador" in output
    assert "Primeira rodada: só posicionamento" in output
