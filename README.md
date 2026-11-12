# Telemetria MS41

> App desktop para ler, gravar e analisar em tempo real os dados do motor de carros com ECU Siemens MS41 (BMW E36).

![Python](https://img.shields.io/badge/Python-3-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![ESP32](https://img.shields.io/badge/ESP32--C3-BLE-E7352C?logo=espressif&logoColor=white)

Trabalho de Conclusão de Curso (TCC) do curso de Ciência da Computação do **Centro Universitário do Instituto Mauá de Tecnologia (IMT)**.

---

## Sumário

- [Visão geral](#visão-geral)
- [Como funciona](#como-funciona)
- [Funcionalidades](#funcionalidades)
- [Parâmetros lidos](#parâmetros-lidos)
- [Tecnologias](#tecnologias)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Como rodar](#como-rodar)
- [Opções de linha de comando](#opções-de-linha-de-comando)
- [Documentação](#documentação)
- [Limitações conhecidas](#limitações-conhecidas)
- [Equipe](#equipe)

---

## Visão geral

Um módulo **ESP32-C3** ligado ao carro lê a ECU **Siemens MS41** pelo protocolo proprietário **DS2** da BMW (via K-Line) e publica as leituras por **Bluetooth LE**. O app desktop recebe essas leituras, mostra tudo ao vivo, grava sessões no banco e oferece análise, comparação e exportação.

O app atende dois perfis de uso:

| Papel | Quem é | O que muda |
|---|---|---|
| **Profissional** | Mecânico ou preparador | Cadastra clientes e os carros deles |
| **Particular** | Dono do carro | Cadastra os próprios carros, sem tela de clientes |

O firmware do ESP32 fica no repositório [`Aplicativo-DS2-MS41`](https://github.com/Johncall20/Aplicativo-DS2-MS41).

---

## Como funciona

```
ECU MS41 ──DS2/K-Line──▶ ESP32-C3 ──Bluetooth LE──▶ Backend (FastAPI) ──WebSocket──▶ Interface (React)
                                                          │
                                                     PostgreSQL
```

1. O `LeitorBLE` encontra o módulo pelo nome (`E36-DS2`), assina as notificações e reconecta sozinho se a conexão cair.
2. Cada linha JSON do firmware vira um dicionário e chega ao `Gravador`.
3. O `Gravador` manda a leitura para a tela pelo WebSocket `/ws`. Se houver gravação em curso, também grava a amostra e passa pelo `DetectorEventos`, que compara com os limites da sessão.
4. A interface (`TelemetriaProvider` → `useTelemetria()` → `AoVivo`) atualiza cards, gráficos e alertas.

O leitor roda o tempo todo: a tela ao vivo funciona mesmo sem sessão gravando.

---

## Funcionalidades

- **Conta:** cadastro e login com dois papéis, edição de perfil e senha, exportação dos próprios dados e exclusão da conta
- **Clientes** (Profissional): cadastrar, editar, arquivar e restaurar
- **Veículos:** marca e modelo pelo catálogo FIPE (com modelo customizado), validação de anos e placa, combustível, câmbio e perfil da ECU
- **Ao vivo:** parâmetros em tempo real, estado do módulo e indicação de quais campos a ECU não respondeu
- **Gravação:** sessão com seis limites de alerta (pré-preenchidos da última sessão do carro), km e notas
- **Eventos:** shift light, RPM alto, temperatura alta, bateria baixa, perda de conexão e leitura incompleta
- **Análise:** gráficos da sessão com eventos marcados, trechos sem leitura e métricas
- **Exportação:** CSV, JSON e PDF (com seções escolhidas)
- **Relatórios:** frota, evolução, eventos e comparação entre duas sessões

---

## Parâmetros lidos

| Campo | Parâmetro | Unidade |
|---|---|---|
| `rpm` | Rotação do motor | rpm |
| `vss` | Velocidade | km/h |
| `ect` | Temperatura do líquido de arrefecimento | °C |
| `iat` | Temperatura do ar de admissão | °C |
| `tps` | Posição da borboleta | % |
| `vbat` | Tensão da bateria | V |
| `vanos` | Posição do VANOS | °CRK |

Firmwares mais novos também enviam os extras da MS41: carga (`load`), MAF, sonda de detonação (`knock`), avanço de ignição (`ign`), tempo de injeção (`inj`), válvula de marcha lenta (`iacv`), integradores e sondas lambda dos dois bancos.

Cada leitura traz um bitmask `valid` que diz quais campos a ECU respondeu naquele ciclo. Campo sem resposta aparece apagado na tela e não entra nos cálculos.

---

## Tecnologias

| Camada | Stack |
|---|---|
| Módulo | ESP32-C3, protocolo DS2 (K-Line), Bluetooth LE (Nordic UART) |
| Backend | Python 3, FastAPI, Uvicorn, [`bleak`](https://github.com/hbldh/bleak), SQLModel |
| Banco | PostgreSQL 16 (Docker), migrações com Alembic |
| Frontend | React 18, Vite, Recharts |
| Relatórios | ReportLab e Matplotlib (PDF) |
| Segurança | Argon2 para senhas, token opaco em cookie com validade de 12 h |

---

## Estrutura do repositório

```
telemetria-desktop/
├── docker-compose.yml        # sobe o PostgreSQL
├── backend/
│   ├── executar.py           # ponto de entrada
│   ├── alembic.ini
│   ├── migracoes/            # migrações do banco (Alembic)
│   ├── semear.py             # gera um banco de demonstração
│   └── telemetria/
│       ├── api.py            # app FastAPI e linha de comando
│       ├── contexto.py       # liga leitor, gravador e hub
│       ├── modelos/          # tabelas (Usuario, Cliente, Veiculo, Sessao, Amostra, Evento...)
│       ├── repositorios/     # todo acesso ao banco
│       ├── servicos/         # leitor BLE, gravador, detector, métricas, exportação
│       └── rotas/            # rotas HTTP e WebSocket
└── frontend/
    └── src/
        ├── paginas/          # telas (AoVivo, Sessoes, Analise, Veiculos...)
        ├── componentes/
        └── hooks/            # TelemetriaProvider, useTelemetria, autenticação
Arquivos/                     # diagramas e documentos do TCC
```

---

## Como rodar

**Pré-requisitos:** Python 3.10+, Node 18+, Docker e um adaptador Bluetooth no PC.

**1. Banco de dados**

```bash
cd telemetria-desktop
docker compose up -d
```

**2. Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head             # passo manual: o app não migra o banco sozinho
                                 # (a migração já carrega o catálogo de marcas e modelos)
```

**3. Frontend**

```bash
cd ../frontend
npm install
npm run build                    # o backend serve o dist/
```

**4. Subir o app**

```bash
cd ../backend
python executar.py               # com o módulo ESP32
python executar.py --sim         # sem o carro, com dados simulados
```

Abra `http://127.0.0.1:8000`.

Para desenvolver o frontend com recarga automática, rode `npm run dev` na pasta `frontend` e abra `http://localhost:5173` (o Vite repassa as chamadas para o backend).

A conexão com o banco usa `DATABASE_URL`. O padrão é `postgresql+psycopg://telemetria:telemetria@localhost:5432/telemetria`, que bate com o `docker-compose.yml`.

---

## Opções de linha de comando

| Opção | O que faz |
|---|---|
| `--sim` | Usa a fonte simulada em vez do Bluetooth |
| `--replay [URL]` | Lê uma gravação tocada pelo `replay.py` do repositório do firmware |
| `--nome NOME` | Nome anunciado pelo ESP32 (padrão `E36-DS2`) |
| `--porta N` | Porta do servidor (padrão `8000`) |
| `--host H` | Endereço de escuta (padrão `127.0.0.1`; use `0.0.0.0` para abrir no celular pela rede local) |
| `--recalcular [pendentes\|tudo]` | Recalcula os resumos das sessões gravadas e sai |
| `--carregar-catalogo [ARQUIVO]` | Recarrega marcas e modelos do `catalogo_veiculos.json` (só insere o que falta) e sai |

---

## Documentação

Os diagramas do projeto estão em `Arquivos/`:

- Diagrama de classes
- Diagrama de casos de uso
- Fluxo de processos (BPMN)
- Fluxo do dado ao vivo
- Requisitos e histórias de usuário

---

## Limitações conhecidas

- Leitura e limpeza de códigos de erro (DTC) não são suportadas: o firmware só publica dados, não aceita comandos.
- O módulo lê apenas a Siemens MS41. Carro cadastrado com outro perfil de ECU não grava com o Bluetooth.
- A interface foi feita para desktop; no celular ela abre pelo navegador, mas não é otimizada para tela pequena.
- Não há estimativa de marcha: as métricas são calculadas a partir dos dados lidos.

---

## Equipe

- **Henrique Ricardo Akamoto**
- **João Victor de Oliveira Borges**
- **Leonardo Caloni Munduruca**

---

<sub>Centro Universitário do Instituto Mauá de Tecnologia (IMT) - Ciência da Computação · Trabalho de Conclusão de Curso</sub>
