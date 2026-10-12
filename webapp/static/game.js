"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const LAYOUT_URL = new URL("map_layout.json", document.currentScript.src);
const CELL_RADIUS = 62;

// Cores dos jogadores, pela cor definida no servidor
const COLORS = {
  red:    { bg: "#d62828", fg: "white", label: "vermelho" },
  blue:   { bg: "#2a6fbf", fg: "white", label: "azul" },
  green:  { bg: "#3a8f4b", fg: "white", label: "verde" },
  yellow: { bg: "#e0a526", fg: "#222",  label: "amarelo" },
  purple: { bg: "#8e44d6", fg: "white", label: "roxo" },
  black:  { bg: "#3b3b3b", fg: "white", label: "preto" },
};
const CONTINENT_COLORS = {
  "North America": "#e9c46a", "South America": "#f4a261", "Europe": "#8ecae6",
  "Africa": "#e07a5f", "Asia": "#90be6d", "Australia": "#c77dff",
};
const ICONS = { infantry: "Infantaria", cavalry: "Cavalaria", artillery: "Artilharia", wild: "Curinga" };
const DICE = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];

window.addEventListener("load", async () => {
  const layout = await (await fetch(LAYOUT_URL)).json();

  let gameState = null;
  let lobby = null;
  let missionText = "-";
  let currentPlayerIndex = null;
  let myPlayerIndex = null;
  let reinforcements = 0;
  let phase = "waiting";
  let selectedTerritory = null;
  let hand = { cards: [], combos: [] };
  let selectedCards = [];
  let boardDrawn = false;

  const $ = id => document.getElementById(id);
  const logElement = $("log");
  const hintElem = $("hint");
  const meElem = $("me");
  const missionElem = $("mission");
  const currentPlayerElem = $("currentPlayer");
  const reinforcementsElem = $("reinforcements");
  const phaseElem = $("phase");
  const playersElem = $("players");
  const cardsElem = $("cards");
  const diceElem = $("dice");
  const lobbyElem = $("lobby");
  const conquestElem = $("conquest");
  const occupyInput = $("occupyCount");
  const qtySelect = $("qty");
  const btnStartTurn = $("btnStartTurn");
  const btnFortify = $("btnFortify");
  const btnEndTurn = $("btnEndTurn");
  const btnTrade = $("btnTrade");
  const mapElem = $("map");
  const roomInput = $("roomId");

  mapElem.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  const boardLayer = svg("g");
  const cellLayer = svg("g");
  const edgeLayer = svg("g");
  const nodeLayer = svg("g");
  mapElem.append(boardLayer, cellLayer, edgeLayer, nodeLayer);
  const cells = buildCells();

  function svg(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  }

  // O atributo hidden não tem propriedade própria em elementos SVG, então vai pelo atributo
  function setHidden(el, hidden) {
    el.toggleAttribute("hidden", hidden);
  }

  function log(msg) {
    logElement.textContent += msg + "\n";
    logElement.scrollTop = logElement.scrollHeight;
  }

  // Identifica este navegador para o servidor devolver o mesmo assento depois de recarregar a página.
  // Fica na sessão da aba, então cada aba é um jogador diferente.
  function playerToken() {
    try {
      let token = sessionStorage.getItem("war-token");
      if (!token) {
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        token = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
        sessionStorage.setItem("war-token", token);
      }
      return token;
    } catch (e) {
      return null;  // sem armazenamento, o assento vale só enquanto a conexão durar
    }
  }

  function isMyTurn() {
    return myPlayerIndex !== null && myPlayerIndex === currentPlayerIndex;
  }

  function playerLabel(index) {
    const p = gameState && gameState.players[index];
    const color = p && COLORS[p.color];
    return `Jogador ${index + 1}` + (color ? ` (${color.label})` : "");
  }

  function territoryLabel(name) {
    const t = gameState && gameState.territories[name];
    return t ? t.label : name;
  }

  function clickAmount(max) {
    return qtySelect.value === "all" ? max : Math.min(Number(qtySelect.value), max);
  }

  // Guarda o estado recebido do servidor e redesenha a tela.
  // A fase e os reforços vêm do servidor; fora do próprio turno o jogador só espera.
  function applyState(s) {
    const finishedBefore = gameState !== null && gameState.winnerId !== null;
    const previousPhase = phase;
    gameState = s;
    lobby = null;
    currentPlayerIndex = s.currentPlayerIndex;
    if (s.winnerId !== null) {
      phase = "finished";
      reinforcements = 0;
    } else if (isMyTurn()) {
      phase = s.phase;
      reinforcements = s.reinforcementsLeft;
    } else {
      phase = "waiting";
      reinforcements = 0;
    }
    if (phase !== previousPhase || !canBeSource(selectedTerritory)) {
      selectedTerritory = null;
    }
    if (s.winnerId !== null && !finishedBefore) {
      log(`Fim de jogo! ${playerLabel(s.winnerId)} venceu a partida.`);
    }
    render();
  }

  function render() {
    setHidden(lobbyElem, !lobby);
    setHidden(mapElem, !gameState);
    if (lobby) renderLobby();
    if (!gameState) {
      hintElem.textContent = "";
      setHidden(conquestElem, true);
      btnStartTurn.disabled = btnFortify.disabled = btnEndTurn.disabled = btnTrade.disabled = true;
      return;
    }
    missionElem.textContent = myPlayerIndex === null ? "-" : missionText;
    if (myPlayerIndex !== null) {
      const me = gameState.players[myPlayerIndex];
      meElem.textContent = playerLabel(myPlayerIndex) + (me.alive ? "" : " - eliminado");
    } else {
      meElem.textContent = "Espectador";
    }
    currentPlayerElem.textContent = playerLabel(currentPlayerIndex);
    updateControls();
    renderPlayers();
    renderCards();
    renderConquest();
    renderMap();
  }

  function renderLobby() {
    const n = lobby.members;
    $("lobbyInfo").textContent = `${n} pessoa${n === 1 ? "" : "s"} na sala "${lobby.roomId}".`
      + (lobby.isHost ? "" : " Aguardando quem criou a sala iniciar a partida.");
    setHidden($("lobbyHost"), !lobby.isHost);
    $("numPlayers").value = String(lobby.numPlayers);
    const bots = lobby.numPlayers - n;
    $("lobbyBots").textContent = bots > 0
      ? `${bots} lugar${bots === 1 ? " será jogado" : "es serão jogados"} pelo computador.`
      : bots < 0
        ? `Há mais pessoas do que lugares: ${-bots} vai${bots === -1 ? "" : "o"} só assistir.`
        : "Todos os lugares são de pessoas.";
    meElem.textContent = lobby.you === null ? "Espectador" : `Jogador ${lobby.you + 1}`;
    missionElem.textContent = "-";
    currentPlayerElem.textContent = "-";
    phaseElem.textContent = "Sala de espera";
    reinforcementsElem.textContent = "0";
    playersElem.innerHTML = "";
  }

  function updateControls() {
    const setup = gameState.setupRound;
    btnStartTurn.disabled = !(phase === "waiting" && isMyTurn());
    btnFortify.disabled = !(phase === "attacking" && !setup);
    btnEndTurn.disabled = !(phase === "attacking" || phase === "fortifying");
    const phases = {
      placing: "Posicionando tropas", attacking: setup ? "Primeira rodada" : "Ataque",
      fortifying: "Remanejamento", waiting: "Esperando",
    };
    phaseElem.textContent = phase === "finished"
      ? `Fim de jogo - ${playerLabel(gameState.winnerId)} venceu`
      : phases[phase];
    reinforcementsElem.textContent = reinforcements;
    hintElem.textContent = hintText();
  }

  function hintText() {
    if (phase === "finished") return "";
    if (myPlayerIndex === null) return "Você está assistindo a partida.";
    if (!isMyTurn()) {
      const current = gameState.players[currentPlayerIndex];
      return `Aguardando ${playerLabel(currentPlayerIndex)}.`
        + (!current.connected && !current.bot ? " Ele saiu da sala; no painel Jogadores dá para passar o lugar ao computador." : "");
    }
    if (phase === "waiting") return "É a sua vez: clique em Iniciar turno.";
    if (phase === "placing") {
      if (gameState.mustTrade) return "Você tem 5 ou mais cartas: troque 3 delas antes de posicionar as tropas.";
      return `Clique nos seus territórios para posicionar os reforços (restam ${reinforcements}).`;
    }
    if (phase === "attacking") {
      if (gameState.setupRound) return "Na primeira rodada só se posicionam tropas. Clique em Encerrar turno.";
      return selectedTerritory
        ? `Atacando de ${territoryLabel(selectedTerritory)}: clique em um vizinho inimigo destacado, ou no próprio território para cancelar.`
        : "Clique em um território seu com 2 ou mais tropas para atacar, ou use Remanejar tropas / Encerrar turno.";
    }
    return selectedTerritory
      ? `Movendo de ${territoryLabel(selectedTerritory)}: clique em um vizinho seu destacado. Clique no próprio território para soltar.`
      : "Clique em um território seu para mover tropas a um vizinho seu. Cada tropa se move uma vez por turno.";
  }

  function renderPlayers() {
    playersElem.innerHTML = "";
    gameState.players.forEach(p => {
      const row = document.createElement("div");
      row.className = "player-row" + (p.id === currentPlayerIndex ? " current" : "") + (p.alive ? "" : " dead");
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = (COLORS[p.color] || {}).bg;
      const name = document.createElement("span");
      const role = p.id === myPlayerIndex ? " - você"
        : p.substituted ? " - computador (no lugar de quem saiu)"
        : p.bot ? " - computador"
        : !p.connected ? " - ausente" : "";
      name.textContent = playerLabel(p.id) + role;
      const numbers = document.createElement("span");
      numbers.className = "numbers";
      numbers.textContent = `${p.territories.length} territórios · ${p.cardCount} cartas`;
      row.append(swatch, name, numbers);
      playersElem.appendChild(row);
      // Quem está jogando pode passar ao computador o lugar de uma pessoa que saiu
      if (!p.connected && !p.bot && p.alive && myPlayerIndex !== null && gameState.winnerId === null) {
        const btn = document.createElement("button");
        btn.className = "substitute";
        btn.textContent = `Passar o lugar do Jogador ${p.id + 1} para o computador`;
        btn.title = "O computador joga por ele até que volte. É preciso esperar um pouco depois que a pessoa sai.";
        btn.addEventListener("click", () => sock.emit("substitute", { seat: p.id }));
        playersElem.appendChild(btn);
      }
    });
  }

  // --- dados e ocupação ---

  function renderDice(r) {
    const res = r.result;
    diceElem.innerHTML = "";
    const title = document.createElement("div");
    title.textContent = `${territoryLabel(r.from)} atacou ${territoryLabel(r.to)}`;
    diceElem.appendChild(title);
    [["Ataque", res.attacker_rolls, res.defender_rolls, "attack"],
     ["Defesa", res.defender_rolls, res.attacker_rolls, "defense"]].forEach(([label, rolls, other, cls]) => {
      const row = document.createElement("div");
      row.className = "dice-row";
      const name = document.createElement("span");
      name.textContent = label;
      row.appendChild(name);
      rolls.forEach((value, i) => {
        const die = document.createElement("span");
        die.className = "die " + cls;
        die.textContent = DICE[value];
        die.title = String(value);
        // Só os dados que têm par são comparados; no empate a defesa vence
        if (i < other.length) {
          const won = cls === "attack" ? value > other[i] : value >= other[i];
          die.classList.add(won ? "won" : "lost");
        }
        row.appendChild(die);
      });
      diceElem.appendChild(row);
    });
    const outcome = document.createElement("div");
    outcome.textContent = `Ataque perdeu ${res.losses_attacker}, defesa perdeu ${res.losses_defender}.`
      + (res.conquered ? " Território conquistado!" : "");
    diceElem.appendChild(outcome);
  }

  function renderConquest() {
    const c = gameState.conquest;
    const show = Boolean(c && isMyTurn() && phase === "attacking" && c.max > 0);
    setHidden(conquestElem, !show);
    if (!show) return;
    $("conquestText").textContent =
      `${territoryLabel(c.to)} conquistado. Mover mais tropas de ${territoryLabel(c.from)} (até ${c.max}):`;
    occupyInput.max = c.max;
    if (Number(occupyInput.value) > c.max || Number(occupyInput.value) < 1) occupyInput.value = c.max;
  }

  // --- cartas ---

  function selectedCombo() {
    const key = [...selectedCards].sort().join(",");
    return selectedCards.length === 3 && hand.combos.some(c => [...c].sort().join(",") === key);
  }

  function renderCards() {
    selectedCards = selectedCards.filter(id => hand.cards.some(c => c.id === id));
    cardsElem.innerHTML = "";
    if (hand.cards.length === 0) {
      const empty = document.createElement("span");
      empty.className = "empty";
      empty.textContent = "Nenhuma carta. Você ganha uma ao fim de cada turno em que conquistar um território.";
      cardsElem.appendChild(empty);
    }
    hand.cards.forEach(card => {
      const btn = document.createElement("button");
      btn.className = "card" + (selectedCards.includes(card.id) ? " selected" : "");
      const icon = document.createElement("strong");
      icon.textContent = ICONS[card.icon] || card.icon;
      btn.append(icon, document.createTextNode(card.territory || "Vale por qualquer símbolo"));
      btn.addEventListener("click", () => {
        if (selectedCards.includes(card.id)) {
          selectedCards = selectedCards.filter(id => id !== card.id);
        } else if (selectedCards.length < 3) {
          selectedCards.push(card.id);
        }
        renderCards();
      });
      cardsElem.appendChild(btn);
    });
    const value = gameState.nextTradeValue;
    btnTrade.textContent = value ? `Trocar 3 cartas por ${value} tropas` : "Trocar cartas";
    btnTrade.disabled = !(phase === "placing" && selectedCombo());
    if (phase !== "placing") {
      btnTrade.title = "A troca é feita no seu turno, antes de posicionar todos os reforços.";
    } else if (!selectedCombo()) {
      btnTrade.title = "Selecione 3 cartas com o mesmo símbolo ou 3 símbolos diferentes.";
    } else {
      btnTrade.title = "";
    }
  }

  // --- mapa ---

  function pos(name) {
    return layout.territories[name];
  }

  // Cada território é a região de pontos mais próximos do seu centro (célula de Voronoi),
  // limitada a um raio fixo para sobrar mar entre os continentes.
  function buildCells() {
    const result = {};
    const names = Object.keys(layout.territories);
    names.forEach(name => {
      const [px, py] = pos(name);
      let poly = [];
      for (let i = 0; i < 28; i++) {
        const a = (2 * Math.PI * i) / 28;
        poly.push([px + CELL_RADIUS * Math.cos(a), py + CELL_RADIUS * Math.sin(a)]);
      }
      names.forEach(other => {
        if (other === name || poly.length === 0) return;
        const [qx, qy] = pos(other);
        const dx = qx - px, dy = qy - py;
        if (Math.hypot(dx, dy) >= 2 * CELL_RADIUS) return;
        // Mantém o lado da mediatriz que fica mais perto deste território
        const mx = (px + qx) / 2, my = (py + qy) / 2;
        const side = ([x, y]) => (x - mx) * dx + (y - my) * dy;
        const clipped = [];
        poly.forEach((cur, i) => {
          const prev = poly[(i + poly.length - 1) % poly.length];
          const sc = side(cur), sp = side(prev);
          if ((sc <= 0) !== (sp <= 0)) {
            const t = sp / (sp - sc);
            clipped.push([prev[0] + t * (cur[0] - prev[0]), prev[1] + t * (cur[1] - prev[1])]);
          }
          if (sc <= 0) clipped.push(cur);
        });
        poly = clipped;
      });
      result[name] = poly.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    });
    return result;
  }

  // Fundo do tabuleiro: halo dos continentes, fronteiras e rótulos. Desenhado uma vez.
  function drawBoard() {
    const territories = Object.values(gameState.territories);
    // Um grupo por continente, para a transparência não acumular onde os círculos se sobrepõem
    const blobs = {};
    territories.forEach(t => {
      if (!blobs[t.continent]) {
        blobs[t.continent] = svg("g", { class: "continent-blob", fill: CONTINENT_COLORS[t.continent] || "#888" });
        boardLayer.appendChild(blobs[t.continent]);
      }
      const [x, y] = pos(t.name);
      blobs[t.continent].appendChild(svg("circle", { cx: x, cy: y, r: CELL_RADIUS + 10 }));
    });
    const drawn = new Set();
    territories.forEach(t => {
      t.neighbors.forEach(n => {
        const key = [t.name, n].sort().join("|");
        if (drawn.has(key)) return;
        drawn.add(key);
        const [x1, y1] = pos(t.name);
        const [x2, y2] = pos(n);
        if (Math.abs(x1 - x2) > layout.width / 2) {
          // Fronteira que dá a volta no mapa (Alasca-Vladivostok): sai pelas duas bordas
          const [lx, ly] = x1 < x2 ? [x1, y1] : [x2, y2];
          const [rx, ry] = x1 < x2 ? [x2, y2] : [x1, y1];
          edgeLayer.appendChild(svg("line", { class: "edge sea", x1: lx, y1: ly, x2: 0, y2: ly }));
          edgeLayer.appendChild(svg("line", { class: "edge sea", x1: rx, y1: ry, x2: layout.width, y2: ry }));
        } else {
          // Rotas por mar (territórios que não se encostam) ficam tracejadas
          const sea = Math.hypot(x1 - x2, y1 - y2) >= 2 * CELL_RADIUS + 14;
          edgeLayer.appendChild(svg("line", { class: "edge" + (sea ? " sea" : ""), x1, y1, x2, y2 }));
        }
      });
    });
    gameState.continents.forEach(c => {
      const [x, y] = layout.continents[c.name];
      const label = svg("text", { class: "continent-label", x, y, fill: CONTINENT_COLORS[c.name] || "#fff" });
      label.textContent = `${c.label} +${c.bonus}`;
      edgeLayer.appendChild(label);
    });
    boardDrawn = true;
  }

  // Quebra nomes longos em duas linhas, perto do meio
  function splitLabel(label) {
    if (label.length <= 11 || !label.includes(" ")) return [label];
    const words = label.split(" ");
    let best = 1;
    for (let i = 1; i < words.length; i++) {
      const left = words.slice(0, i).join(" ").length;
      const bestLeft = words.slice(0, best).join(" ").length;
      if (Math.abs(left - label.length / 2) < Math.abs(bestLeft - label.length / 2)) best = i;
    }
    return [words.slice(0, best).join(" "), words.slice(best).join(" ")];
  }

  function canBeSource(name) {
    const t = name && gameState.territories[name];
    if (!t || t.ownerId !== myPlayerIndex) return false;
    if (phase === "attacking") return t.armies > 1 && !gameState.setupRound;
    if (phase === "fortifying") return (gameState.movable[name] || 0) > 0;
    return false;
  }

  function isTarget(t) {
    if (!selectedTerritory || !gameState.territories[selectedTerritory].neighbors.includes(t.name)) return false;
    if (phase === "attacking") return t.ownerId !== myPlayerIndex;
    if (phase === "fortifying") return t.ownerId === myPlayerIndex;
    return false;
  }

  function renderMap() {
    if (!boardDrawn) drawBoard();
    cellLayer.innerHTML = "";
    nodeLayer.innerHTML = "";
    const raised = [];
    Object.values(gameState.territories).forEach(t => {
      const [x, y] = pos(t.name);
      const owner = t.ownerId !== null ? gameState.players[t.ownerId] : null;
      const color = (owner && COLORS[owner.color]) || { bg: "#666", fg: "white" };
      let state = "";
      if (t.name === selectedTerritory) state = "selected";
      else if (isTarget(t)) state = "target";
      else if (selectedTerritory) state = "dimmed";

      const cell = svg("polygon", { class: `cell ${state}`, points: cells[t.name], fill: color.bg });
      cell.dataset.name = t.name;
      cell.addEventListener("click", () => onTerritoryClick(t));
      // Células destacadas vão por cima, para o contorno não ficar escondido pelas vizinhas
      if (state === "selected" || state === "target") raised.push(cell);
      else cellLayer.appendChild(cell);

      const g = svg("g", { class: `territory ${state}`, transform: `translate(${x} ${y})` });
      g.dataset.name = t.name;
      if (t.ownerId === myPlayerIndex) g.classList.add("own");
      const title = svg("title");
      const continent = gameState.continents.find(c => c.name === t.continent);
      title.textContent = `${t.label} (${continent ? continent.label : t.continent})\n`
        + `${owner ? playerLabel(owner.id) : "Sem dono"} - ${t.armies} tropa(s)\n`
        + `Fronteiras: ${t.neighbors.map(territoryLabel).join(", ")}`;
      const badge = svg("circle", { class: "badge", r: 13, cy: -8 });
      const armies = svg("text", { class: "armies", y: -8 });
      armies.textContent = t.armies;
      const name = svg("text", { class: "name", y: 17, fill: color.fg });
      splitLabel(t.label).forEach((line, i) => {
        const span = svg("tspan", { x: 0, dy: i === 0 ? 0 : 12 });
        span.textContent = line;
        name.appendChild(span);
      });
      g.append(title, badge, armies, name);
      g.addEventListener("click", () => onTerritoryClick(t));
      nodeLayer.appendChild(g);
    });
    raised.forEach(cell => cellLayer.appendChild(cell));
  }

  function onTerritoryClick(t) {
    if (phase === "placing") {
      if (t.ownerId !== myPlayerIndex) {
        log("Só pode colocar tropas em territórios que você controla.");
        return;
      }
      // O servidor desconta o reforço e devolve o estado atualizado
      sock.emit("place", { placements: { [t.name]: clickAmount(reinforcements) } });
    } else if (phase === "attacking" || phase === "fortifying") {
      if (t.name === selectedTerritory) {
        selectedTerritory = null;
      } else if (selectedTerritory && isTarget(t)) {
        if (phase === "attacking") {
          const attackDice = Math.min(3, gameState.territories[selectedTerritory].armies - 1);
          sock.emit("attack", { from: selectedTerritory, to: t.name, dice: attackDice });
        } else {
          const count = clickAmount(gameState.movable[selectedTerritory] || 0);
          sock.emit("fortify", { from: selectedTerritory, to: t.name, count });
        }
        return;
      } else if (canBeSource(t.name)) {
        selectedTerritory = t.name;
      } else if (phase === "attacking") {
        log(gameState.setupRound
          ? "Na primeira rodada não há ataques."
          : selectedTerritory
            ? "O alvo precisa ser um território inimigo vizinho."
            : "Selecione um território seu com pelo menos 2 tropas para atacar.");
      } else {
        log(selectedTerritory
          ? "O destino precisa ser um território seu vizinho."
          : "Selecione um território seu que ainda tenha tropas para mover.");
      }
      render();
    } else if (phase === "finished") {
      log("A partida já terminou.");
    } else {
      log(isMyTurn() ? "Clique em Iniciar turno." : "Espere o seu turno.");
    }
  }

  // --- servidor ---

  const sock = io();

  function joinRoom() {
    const roomId = roomInput.value.trim() || "default";
    gameState = null;
    lobby = null;
    myPlayerIndex = null;
    hand = { cards: [], combos: [] };
    selectedCards = [];
    missionText = "-";
    meElem.textContent = "-";
    missionElem.textContent = "-";
    render();
    sock.emit("join", { roomId, token: playerToken() });
    log(`Entrando na sala "${roomId}"...`);
  }

  sock.on("connect", () => {
    log("Conectado ao servidor.");
    // Entra (ou volta a entrar, após uma reconexão) na sala
    joinRoom();
  });

  sock.on("disconnect", () => log("Conexão perdida. Tentando reconectar..."));

  sock.on("joined", data => {
    myPlayerIndex = data.playerIndex;
    // Quando a partida começa, a sala de espera deixa de existir
    if (data.started) lobby = null;
    if (data.started && myPlayerIndex !== null) {
      log(`Você é o Jogador ${myPlayerIndex + 1}`);
    }
  });

  sock.on("lobby", data => {
    lobby = data;
    gameState = null;
    myPlayerIndex = data.you;
    render();
  });

  sock.on("mission", m => {
    missionText = m.description;
    render();
  });

  sock.on("hand", h => {
    hand = h;
    render();
  });

  sock.on("message", m => log(m.text || JSON.stringify(m)));

  sock.on("state", applyState);

  sock.on("turn_started", p => {
    applyState(p.state);
    if (isMyTurn()) {
      log(`Turno iniciado. Reforços disponíveis: ${p.reinforcements}`);
    } else {
      log(`${playerLabel(p.state.currentPlayerIndex)} iniciou o turno.`);
    }
  });

  sock.on("attack_result", r => {
    const res = r.result;
    applyState(r.state);
    renderDice(r);
    log(`${territoryLabel(r.from)} atacou ${territoryLabel(r.to)}: dados ${res.attacker_rolls.join(", ")} contra ${res.defender_rolls.join(", ")}. `
      + `Ataque perdeu ${res.losses_attacker}, defesa perdeu ${res.losses_defender}.`
      + (res.conquered ? " Território conquistado!" : ""));
    if (res.eliminated !== null && res.eliminated !== undefined) {
      log(`${playerLabel(res.eliminated)} foi eliminado.`);
    }
  });

  $("btnJoin").addEventListener("click", joinRoom);
  $("numPlayers").addEventListener("change", e => sock.emit("configure", { numPlayers: Number(e.target.value) }));
  $("btnStartGame").addEventListener("click", () => sock.emit("start_game", {}));
  btnStartTurn.addEventListener("click", () => sock.emit("start_turn", {}));
  btnFortify.addEventListener("click", () => sock.emit("begin_fortify", {}));
  btnEndTurn.addEventListener("click", () => sock.emit("end_turn", {}));
  btnTrade.addEventListener("click", () => {
    sock.emit("trade", { cards: selectedCards });
    selectedCards = [];
  });
  $("btnOccupy").addEventListener("click", () => sock.emit("occupy", { count: Number(occupyInput.value) }));
});
