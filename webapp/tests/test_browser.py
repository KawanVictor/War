"""Testes da página em um navegador de verdade, contra um servidor rodando.

Precisam do Playwright (`pip install -r requirements-browser.txt` e `playwright install chromium`).
Sem ele, são pulados.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import pytest

sync_api = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.browser

ROOT = Path(__file__).resolve().parents[2]

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = free_port()
    env = {**os.environ, "WAR_PORT": str(port), "WAR_HOST": "127.0.0.1",
           "WAR_DATA_DIR": str(tmp_path_factory.mktemp("partidas"))}
    proc = subprocess.Popen([sys.executable, "-m", "webapp.app"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(url, timeout=1).close()
                break
            except OSError:
                assert proc.poll() is None, "o servidor encerrou antes de responder"
                time.sleep(0.1)
        else:
            pytest.fail("o servidor não respondeu a tempo")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)

@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            instance = pw.chromium.launch()
        except sync_api.Error as e:
            pytest.skip(f"Chromium do Playwright não está instalado: {e}")
        yield instance
        instance.close()

@pytest.fixture
def page(browser, server):
    """Uma aba nova (jogador novo) com os erros de JavaScript e de rede coletados."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.problems = []
    page.on("pageerror", lambda e: page.problems.append(f"erro de script: {e}"))
    page.on("console", lambda m: page.problems.append(f"console: {m.text}") if m.type == "error" else None)
    page.on("requestfailed", lambda r: page.problems.append(f"falha de rede: {r.url}"))
    # A página não pode depender de nada fora do próprio servidor
    page.on("request", lambda r: page.problems.append(f"pedido externo: {r.url}")
            if not r.url.startswith((server, "data:", server.replace("http", "ws"))) else None)
    yield page
    context.close()

def wait_js(page, expression, arg=None, timeout=10.0):
    """Espera uma expressão JavaScript ficar verdadeira na página.

    O wait_for_function do Playwright avalia o texto com eval dentro da página, o que a
    política de segurança de conteúdo do servidor bloqueia; page.evaluate não passa por ela.
    """
    deadline = time.monotonic() + timeout
    while True:
        if page.evaluate(expression, arg):
            return
        assert time.monotonic() < deadline, f"tempo esgotado esperando: {expression}"
        page.wait_for_timeout(50)

def text(page, selector):
    return page.locator(selector).inner_text()

def open_room(page, server, room):
    page.goto(server)
    page.fill("#roomId", room)
    page.click("#btnJoin")
    wait_js(page, "room => document.getElementById('lobbyInfo').textContent.includes(room)", arg=room)

def start_against_computer(page, server, room, players="3"):
    open_room(page, server, room)
    page.select_option("#numPlayers", players)
    wait_js(page, "document.getElementById('lobbyBots').textContent.includes('computador')")
    page.click("#btnStartGame")
    wait_js(page, "document.querySelectorAll('#map polygon.cell').length === 42")
    wait_js(page, "document.getElementById('mission').textContent !== '-'")

def wait_phase(page, phase):
    wait_js(page, "p => document.getElementById('phase').textContent === p", arg=phase)

def place_everything(page):
    page.select_option("#qty", "all")
    page.locator("#map g.territory.own").first.click()

def play_setup_turn(page):
    """Joga o turno da primeira rodada (só posicionamento) e espera a vez voltar."""
    page.click("#btnStartTurn")
    wait_phase(page, "Posicionando tropas")
    place_everything(page)
    wait_phase(page, "Primeira rodada")
    page.click("#btnEndTurn")
    wait_js(page, "!document.getElementById('btnStartTurn').disabled")

def test_lobby_and_map_render(page, server):
    open_room(page, server, "navegador-mapa")
    assert page.locator("#lobby").is_visible() and not page.locator("#map").is_visible()
    assert "1 pessoa na sala" in text(page, "#lobbyInfo")
    assert page.is_disabled("#btnStartTurn")

    start_against_computer(page, server, "navegador-mapa")
    assert not page.locator("#lobby").is_visible() and page.locator("#map").is_visible()
    assert page.locator("#map g.territory").count() == 42
    assert page.locator("#map g.territory.own").count() == 14
    assert page.locator("#players .player-row").count() == 3
    assert "computador" in text(page, "#players")
    assert text(page, "#me") == "Jogador 1 (vermelho)"
    # nomes em português, do tabuleiro do War
    names = page.locator("#map g.territory .name").all_text_contents()
    assert "Brasil" in names and "Vladivostok" in names and not any("Brazil" in n for n in names)
    assert page.problems == []

def test_turn_with_multiple_troops_per_click(page, server):
    start_against_computer(page, server, "navegador-turno")
    page.click("#btnStartTurn")
    wait_phase(page, "Posicionando tropas")
    total = int(text(page, "#reinforcements"))
    assert total >= 3

    own = page.locator("#map g.territory.own").first
    before = int(own.locator(".armies").text_content())
    page.select_option("#qty", "2")
    own.click()
    wait_js(page, "n => document.getElementById('reinforcements').textContent === String(n)", arg=total - 2)
    assert int(page.locator("#map g.territory.own").first.locator(".armies").text_content()) == before + 2

    place_everything(page)
    wait_phase(page, "Primeira rodada")
    assert "só se posicionam tropas" in text(page, "#hint")
    assert page.is_disabled("#btnFortify")

    page.click("#btnEndTurn")
    wait_js(page, "!document.getElementById('btnStartTurn').disabled")
    assert text(page, "#log").count("(computador) jogou") == 2
    assert page.problems == []

PICK_BASE = r"""() => {
  // Pelo título de cada território: um território próprio com vizinho inimigo e vizinho próprio
  const info = g => {
    const [head, , borders] = g.querySelector('title').textContent.split('\n');
    return {
      name: g.dataset.name,
      label: head.replace(/ \([^)]*\)$/, ''),
      borders: borders.replace('Fronteiras: ', '').split(', '),
    };
  };
  const own = [...document.querySelectorAll('#map g.territory.own')].map(info);
  const ownLabels = new Set(own.map(t => t.label));
  const pick = own.find(t => t.borders.some(b => ownLabels.has(b)) && t.borders.some(b => !ownLabels.has(b)));
  return pick ? pick.name : null;
}"""

def armies_of(page, name):
    return int(page.locator(f'#map g.territory[data-name="{name}"] .armies').text_content())

def test_attack_shows_dice_and_fortify_moves_troops(page, server):
    start_against_computer(page, server, "navegador-ataque", players="2")
    play_setup_turn(page)

    page.click("#btnStartTurn")
    wait_phase(page, "Posicionando tropas")
    name = page.evaluate(PICK_BASE)
    assert name, "nenhum território serve de base para o teste"
    source = page.locator(f'#map g.territory[data-name="{name}"]')
    page.select_option("#qty", "all")
    source.click()
    wait_phase(page, "Ataque")

    source.click()
    wait_js(page, "document.querySelectorAll('#map g.territory.target').length > 0")
    assert page.locator("#map polygon.cell.selected").count() == 1
    assert page.locator("#map g.territory.dimmed").count() > 0
    page.locator("#map g.territory.target").first.click()
    wait_js(page, "document.querySelectorAll('#dice .die').length >= 2")
    assert page.locator("#dice .die.attack").count() >= 1 and page.locator("#dice .die.defense").count() >= 1
    assert "atacou" in text(page, "#dice") and "atacou" in text(page, "#log")

    # Remanejamento: abre a fase e move 1 tropa para um vizinho próprio, se ainda houver tropa para mover
    page.click("#btnFortify")
    wait_phase(page, "Remanejamento")
    assert page.locator("#map g.territory.selected").count() == 0
    before = armies_of(page, name)
    if before > 1:
        page.select_option("#qty", "1")
        source.click()
        wait_js(page, "document.querySelectorAll('#map g.territory.target').length > 0")
        page.locator("#map g.territory.target").first.click()
        wait_js(page, 
            "([n, a]) => Number(document.querySelector(`#map g.territory[data-name=\"${n}\"] .armies`).textContent) === a",
            arg=[name, before - 1])
    page.click("#btnEndTurn")
    wait_js(page, "document.getElementById('phase').textContent !== 'Remanejamento'")
    assert page.problems == []

def test_reload_keeps_the_seat(page, server):
    start_against_computer(page, server, "navegador-recarga")
    mission = text(page, "#mission")
    page.click("#btnStartTurn")
    wait_phase(page, "Posicionando tropas")

    page.reload()
    page.fill("#roomId", "navegador-recarga")
    page.click("#btnJoin")
    wait_js(page, "document.querySelectorAll('#map polygon.cell').length === 42")
    wait_phase(page, "Posicionando tropas")
    assert text(page, "#me") == "Jogador 1 (vermelho)"
    assert text(page, "#mission") == mission
    assert page.problems == []

def test_second_tab_is_another_player(browser, server, page):
    open_room(page, server, "navegador-dois")
    other_context = browser.new_context()
    other = other_context.new_page()
    try:
        open_room(other, server, "navegador-dois")
        wait_js(page, "document.getElementById('lobbyInfo').textContent.includes('2 pessoas')")
        assert "Aguardando quem criou a sala" in text(other, "#lobbyInfo")
        assert not other.locator("#lobbyHost").is_visible()
        page.select_option("#numPlayers", "2")
        page.click("#btnStartGame")
        wait_js(other, "document.querySelectorAll('#map polygon.cell').length === 42")
        assert text(other, "#me") == "Jogador 2 (azul)"
        assert "Aguardando Jogador 1" in text(other, "#hint")
        assert other.is_disabled("#btnStartTurn")
    finally:
        other_context.close()

def test_absent_player_can_be_handed_to_the_computer(browser, server, page):
    """Com o tempo de espera padrão, o botão aparece e o servidor explica que ainda é cedo."""
    open_room(page, server, "navegador-ausente")
    other_context = browser.new_context()
    other = other_context.new_page()
    open_room(other, server, "navegador-ausente")
    wait_js(page, "document.getElementById('lobbyInfo').textContent.includes('2 pessoas')")
    page.select_option("#numPlayers", "2")
    page.click("#btnStartGame")
    wait_js(page, "document.querySelectorAll('#map polygon.cell').length === 42")
    wait_js(other, "document.querySelectorAll('#map polygon.cell').length === 42")
    assert page.locator("#players button.substitute").count() == 0

    other_context.close()
    wait_js(page, "document.querySelectorAll('#players button.substitute').length === 1")
    assert "ausente" in text(page, "#players")
    assert "Jogador 2" in text(page, "#players button.substitute")
    page.click("#players button.substitute")
    wait_js(page, "document.getElementById('log').textContent.includes('Aguarde mais')")
    assert page.problems == []

def test_layout_fits_a_phone_screen(browser, server):
    context = browser.new_context(viewport={"width": 400, "height": 800})
    page = context.new_page()
    try:
        start_against_computer(page, server, "navegador-celular")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        context.close()
