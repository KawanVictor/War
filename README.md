# War (Risk) em Python

Implementação do jogo de tabuleiro War (inspirado em Risk), com:

- Motor de regras em Python (reforços, combate, cartas, turnos)
- Interface CLI interativa para jogar no terminal
- Servidor web em Flask usando Flask-SocketIO para partidas online em tempo real
- Estrutura modular para testes e fácil expansão

O projeto está em desenvolvimento: dá para jogar turnos completos, mas várias regras ainda faltam (veja [Limitações conhecidas](#limitações-conhecidas)).

## Instalação

Testado com Python 3.12. Recomenda-se usar um ambiente virtual:

```bash
git clone https://github.com/KawanVictor/War.git
cd War
python -m venv .venv
```

Ative o ambiente:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Como jogar

Execute os comandos abaixo na raiz do repositório.

### Versão web

```bash
python -m webapp.app
```

Abra `http://localhost:50001` no navegador. Cada aba ou navegador que entra na mesma sala ocupa um assento; a partida é de 3 jogadores, então abra três abas para jogar sozinho. Quem entra com a sala cheia assiste como espectador.

Cada jogador recebe uma missão secreta, mostrada no topo da página. Vence quem cumprir a própria missão ou for o último com territórios.

Em cada turno:

1. Clique em **Iniciar turno** quando for a sua vez.
2. Clique nos seus territórios para posicionar os reforços, uma tropa por clique. É preciso posicionar todos antes de atacar ou encerrar.
3. Para atacar, clique em um território seu com pelo menos 2 tropas e depois em um território inimigo vizinho.
4. Clique em **Encerrar turno**.

A página carrega o cliente Socket.IO de um CDN, então o navegador precisa de acesso à internet. O servidor escuta em `0.0.0.0` e aceita conexões de qualquer origem, o que serve para testes em rede local, mas não para exposição pública.

### Versão terminal

```bash
python -m war_game.cli.main
```

Partida local de 3 jogadores no mesmo terminal, até alguém vencer. A missão de cada jogador aparece no início do turno dele. Use `Ctrl+C` para sair antes.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Os testes do motor ficam em `war_game/tests/` e os do servidor web em `webapp/tests/`.

## Estrutura

```
├── war_game/
│   ├── models/      # Territory, Player, Card, Mission, GameState
│   ├── rules/       # combate, reforços, cartas, missões
│   ├── services/    # carregamento do mapa, criação da partida e gerenciador de turnos
│   ├── cli/         # jogo no terminal
│   ├── data/        # mapa, continentes, cartas e missões em JSON
│   └── tests/
├── webapp/
│   ├── app.py               # aplicação Flask e ponto de entrada
│   ├── socket_handlers.py   # eventos Socket.IO (join, start_turn, place, attack, end_turn)
│   ├── rooms.py             # salas e criação da partida
│   ├── state_adapter.py     # conversão do estado para JSON
│   ├── templates/           # página do jogo
│   ├── static/
│   └── tests/
├── pyproject.toml
├── requirements.txt         # dependências com versão fixa
├── requirements-dev.txt     # dependências + pytest
└── README.md
```

## Regras implementadas

- Mapa com 42 territórios em 6 continentes, distribuídos aleatoriamente entre os jogadores
- Reforços: um a cada 3 territórios (mínimo 3), mais o bônus de continentes completos
- Combate com até 3 dados de ataque e 2 de defesa; empates favorecem a defesa
- Conquista de território e carta ao fim do turno para quem conquistou; o descarte é reembaralhado quando o baralho acaba
- Turno em fases validadas pelo motor: iniciar, posicionar todos os reforços, atacar, encerrar
- Missões secretas sorteadas no início: conquistar continentes, conquistar um número de territórios ou destruir uma cor
- Eliminação de jogadores (as cartas do eliminado vão para quem o eliminou) e fim de partida por missão cumprida ou último sobrevivente

## Limitações conhecidas

- A troca de cartas existe no motor (soma as tropas aos reforços do turno), mas não está disponível no terminal nem na web
- Não há fase de remanejamento de tropas
- Cada território começa com 1 tropa; não há a rodada inicial de distribuição de exércitos
- A partida web é sempre de 3 jogadores (o motor aceita de 2 a 6)
- Quem perde a conexão libera o assento; ao voltar, ocupa o primeiro assento livre, que pode não ser o mesmo
