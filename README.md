# War (Risk) em Python

[![CI](https://github.com/KawanVictor/War/actions/workflows/ci.yml/badge.svg)](https://github.com/KawanVictor/War/actions/workflows/ci.yml)

![Partida em andamento na versão web](docs/screenshot.png)

Implementação do jogo de tabuleiro War (inspirado em Risk), com:

- Motor de regras em Python (reforços, combate, cartas, missões, turnos)
- Versão web em Flask e Flask-SocketIO, para partidas online em tempo real
- Versão de terminal
- Jogadores controlados pelo computador, para jogar sozinho ou completar a mesa

Dá para jogar partidas completas, do sorteio das missões à vitória. O que ainda falta está em [Limitações conhecidas](#limitações-conhecidas).

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

Abra `http://localhost:50001` no navegador.

**Sala de espera.** Digite o nome de uma sala e clique em **Entrar**. Quem entra primeiro cria a sala, escolhe o total de jogadores (2 a 6) e clica em **Iniciar partida**. As pessoas ocupam os primeiros lugares, na ordem em que entraram; os lugares que sobrarem são jogados pelo computador. Para jogar sozinho, basta iniciar a partida sem esperar ninguém. Quem entra depois que a partida começou, ou além do total de jogadores, só assiste.

**Seu lugar fica guardado.** Recarregar a página ou perder a conexão não tira você da partida: ao voltar para a mesma sala, na mesma aba, você reassume o mesmo jogador. Cada aba do navegador conta como uma pessoa diferente.

**Se alguém sair e não voltar.** O painel **Jogadores** marca a pessoa como ausente e, depois de 30 segundos, qualquer jogador pode passar o lugar dela para o computador, para a partida não ficar parada. O computador continua o turno de onde ela parou. Se a pessoa voltar, reassume o lugar na hora.

**Objetivo.** Cada jogador recebe uma missão secreta, mostrada no painel lateral. Vence quem cumprir a própria missão ou for o último com territórios.

**Primeira rodada.** No primeiro turno de cada jogador só se posicionam tropas; ataques e remanejamento começam na rodada seguinte.

Em cada turno:

1. Clique em **Iniciar turno** quando for a sua vez.
2. Para trocar cartas, selecione 3 no painel **Suas cartas** (mesmo símbolo ou três símbolos diferentes; o curinga vale por qualquer um) e clique em **Trocar**. As tropas da troca entram nos reforços do turno. Com 5 ou mais cartas a troca é obrigatória.
3. Clique nos seus territórios para posicionar os reforços. O seletor **Tropas por clique** define quantas vão de cada vez (1, 2, 3, 5, 10 ou todas). É preciso posicionar todas antes de atacar ou encerrar.
4. Para atacar, clique em um território seu com pelo menos 2 tropas e depois em um vizinho inimigo destacado. O painel **Último ataque** mostra os dados. A origem continua selecionada para atacar de novo; clique nela para soltar.
5. Ao conquistar um território, as tropas que atacaram seguem para ele. Se quiser levar mais, use a caixa que aparece acima do mapa.
6. Para remanejar, clique em **Remanejar tropas**, escolha um território seu e clique em um vizinho seu. Depois de começar o remanejamento não dá mais para atacar, e cada tropa só se move uma vez por turno.
7. Clique em **Encerrar turno**.

**O mapa.** Cada território é uma região na cor do dono, com o número de tropas no centro; os seus têm o número contornado de amarelo. As linhas ligam territórios vizinhos, e as tracejadas são rotas por mar. A que sai pelas bordas liga o Alasca a Vladivostok.

#### Configuração do servidor

Por padrão o servidor atende só a própria máquina e grava as partidas em `instance/rooms/`, de onde são recarregadas quando ele reinicia. Tudo isso se ajusta por variáveis de ambiente:

| Variável | Padrão | Para que serve |
| --- | --- | --- |
| `WAR_HOST` | `127.0.0.1` | Endereço em que o servidor escuta. Use `0.0.0.0` para jogar com outras máquinas da rede. |
| `WAR_PORT` | `50001` | Porta. |
| `WAR_DATA_DIR` | `instance/rooms` | Pasta das partidas salvas. Vazio desliga a gravação. |
| `WAR_ROOM_TTL_HOURS` | `24` | Horas sem atividade até uma sala ser apagada. |
| `WAR_ABANDON_SECONDS` | `30` | Segundos que uma pessoa precisa estar fora para os outros poderem passar o lugar dela ao computador. |
| `WAR_CORS_ORIGINS` | (vazio) | Origens extras autorizadas a conectar, separadas por vírgula. Sem isso, só a própria página do servidor conecta. |

O servidor limita a quantidade de ações por conexão e o número de salas, mas não tem contas nem senha de sala: quem souber o nome de uma sala em espera pode entrar nela. Para expor na internet, coloque-o atrás de um proxy com HTTPS.

### Versão terminal

```bash
python -m war_game.cli.main
```

Partida local no mesmo terminal, até alguém vencer. As escolhas são feitas por menus numerados, e a missão e as cartas de cada jogador aparecem no início do turno dele. Use `Ctrl+C` para sair antes.

Por padrão são 3 pessoas. Para mudar o total ou jogar contra o computador:

```bash
python -m war_game.cli.main --jogadores 4 --computador 3
```

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
python -m pytest        # testes
python -m ruff check .  # lint
python -m mypy          # tipos
```

Os testes do motor ficam em `war_game/tests/` e os do servidor em `webapp/tests/`.

Os testes em `webapp/tests/test_browser.py` abrem a página em um navegador de verdade contra um servidor rodando. Eles são pulados se o Playwright não estiver instalado:

```bash
pip install -r requirements-browser.txt
python -m playwright install chromium
python -m pytest -m browser
```

O GitHub Actions roda, a cada push e pull request, o lint e a checagem de tipos, a suíte em Python 3.10, 3.12 e 3.13, e os testes de navegador.

## Estrutura

```
├── war_game/
│   ├── models/      # Territory, Player, Card, Mission, GameState
│   ├── rules/       # combate, reforços, cartas, missões
│   ├── services/    # mapa, criação da partida, turnos, computador, salvar/carregar
│   ├── cli/         # jogo no terminal
│   ├── data/        # mapa, continentes, cartas e missões em JSON
│   └── tests/
├── webapp/
│   ├── app.py               # aplicação Flask, configuração e ponto de entrada
│   ├── socket_handlers.py   # eventos Socket.IO (sala de espera e jogadas)
│   ├── rooms.py             # salas, assentos, gravação em disco e limpeza
│   ├── state_adapter.py     # conversão do estado para JSON
│   ├── templates/           # página do jogo
│   ├── static/              # game.js, estilos, posições do mapa e cliente Socket.IO
│   └── tests/
├── docs/                    # imagem usada neste README
├── pyproject.toml
├── requirements.txt         # dependências com versão fixa
├── requirements-dev.txt     # + pytest, ruff e mypy
├── requirements-browser.txt # + Playwright, para os testes de navegador
└── README.md
```

## Regras implementadas

- Mapa com 42 territórios em 6 continentes, distribuídos aleatoriamente entre os jogadores, com os nomes do tabuleiro do War
- Primeira rodada só de posicionamento
- Reforços: um a cada 3 territórios (mínimo 3), mais o bônus de continentes completos
- Combate com até 3 dados de ataque e 2 de defesa; empates favorecem a defesa
- Depois de conquistar, o jogador escolhe quantas tropas a mais levar para o território
- Baralho de 44 cartas (uma por território e 2 curingas); quem conquista ganha uma ao fim do turno, e o descarte é reembaralhado quando o baralho acaba
- Troca de cartas por tropas (4, 6, 8, 10, 12, 15 e depois de 5 em 5), com 2 tropas extras em um território próprio que apareça nas cartas; obrigatória com 5 ou mais cartas
- Remanejamento entre territórios próprios vizinhos; cada tropa se move uma vez por turno e sempre fica pelo menos uma
- Missões secretas sorteadas no início: conquistar continentes, conquistar um número de territórios ou destruir uma cor
- Eliminação de jogadores (as cartas do eliminado vão para quem o eliminou) e fim de partida por missão cumprida ou último sobrevivente

## Limitações conhecidas

- As fronteiras são as do tabuleiro do Risk. Os nomes são os do War, aplicados ao território equivalente, mas algumas ligações do War brasileiro são diferentes. Nos arquivos de dados os territórios continuam identificados pelo nome em inglês do Risk.
- O mapa é estilizado: as regiões são geradas a partir da posição de cada território, não seguem o contorno real dos países.
- Passar o lugar de quem saiu para o computador depende de outro jogador clicar; não é automático. Se todas as pessoas saírem, a partida fica parada até alguém voltar.
- O jogador do computador segue regras simples (reforça a fronteira mais ameaçada e ataca quando tem vantagem); não persegue a própria missão.
- Quem recebe 5 ou mais cartas ao eliminar um adversário só é obrigado a trocar no turno seguinte.
- O lugar é lembrado por aba: fechar a aba, ou abrir a partida em outro navegador, entra como espectador.

## Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE). O cliente Socket.IO em `webapp/static/vendor/` também é distribuído sob a licença MIT, pelos seus autores.
