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

Todos os comandos abaixo devem ser executados de dentro da pasta `War/` interna (a que contém `war_game/` e `webapp/`):

```bash
cd War
```

### Versão web

```bash
python -m webapp.app
```

Abra `http://localhost:50001` no navegador. Cada aba ou navegador que entra na mesma sala ocupa um assento; a partida é de 3 jogadores, então abra três abas para jogar sozinho.

Em cada turno:

1. Clique em **Iniciar turno** quando for a sua vez.
2. Clique nos seus territórios para posicionar os reforços, uma tropa por clique.
3. Para atacar, clique em um território seu com pelo menos 2 tropas e depois em um território inimigo vizinho.
4. Clique em **Encerrar turno**.

A página carrega o cliente Socket.IO de um CDN, então o navegador precisa de acesso à internet. O servidor escuta em `0.0.0.0` e aceita conexões de qualquer origem, o que serve para testes em rede local, mas não para exposição pública.

### Versão terminal

```bash
python -m war_game.cli.main
```

Partida local de 3 jogadores no mesmo terminal. Use `Ctrl+C` para sair.

## Testes

```bash
pip install pytest
python -m pytest
```

## Estrutura

```
War/
├── war_game/
│   ├── models/      # Territory, Player, Card, Mission, GameState
│   ├── rules/       # combate, reforços, cartas, missões
│   ├── services/    # carregamento do mapa e gerenciador de turnos
│   ├── cli/         # jogo no terminal
│   ├── data/        # mapa, continentes e cartas em JSON
│   └── tests/
└── webapp/
    ├── app.py               # aplicação Flask e ponto de entrada
    ├── socket_handlers.py   # eventos Socket.IO (join, start_turn, place, attack, end_turn)
    ├── rooms.py             # salas e criação da partida
    ├── state_adapter.py     # conversão do estado para JSON
    ├── templates/           # página do jogo
    └── static/
```

## Regras implementadas

- Mapa com 42 territórios em 6 continentes, distribuídos aleatoriamente entre os jogadores
- Reforços: um a cada 3 territórios (mínimo 3), mais o bônus de continentes completos
- Combate com até 3 dados de ataque e 2 de defesa; empates favorecem a defesa
- Conquista de território e carta ao fim do turno para quem conquistou

## Limitações conhecidas

- Não há eliminação de jogadores nem condição de vitória; a partida não termina sozinha
- A troca de cartas existe no motor, mas não está disponível no terminal nem na web
- Não há fase de remanejamento de tropas
- As missões ainda não foram implementadas
- O servidor confia no cliente: não limita a quantidade de reforços nem confere o dono do território atacante
- A partida web é sempre de 3 jogadores; a partir do 4º, quem entra divide o assento do Jogador 1
