OBD2 + MS41 Telemetry
Sistema embarcado de baixo custo para leitura e monitoramento de parâmetros automotivos em tempo real, desenvolvido como Trabalho de Conclusão de Curso (TCC) do curso de Ciência da Computação do Centro Universitário do Instituto Mauá de Tecnologia (IMT).
Visão Geral
Este projeto realiza a comunicação com a unidade de controle eletrônico (ECU) de um veículo por meio de um adaptador ELM327 conectado ao conector OBD-II. Uma placa Raspberry Pi Zero W atua como unidade de processamento embarcada: ela se conecta ao adaptador via Bluetooth Low Energy (BLE), requisita os parâmetros do motor utilizando os PIDs do padrão OBD-II (norma SAE J1979), converte os dados recebidos em unidades de engenharia e os disponibiliza para visualização em tempo real.
A etapa atual do trabalho concentra-se na validação da comunicação por meio do padrão OBD-II. A comunicação com a ECU Siemens MS41 de veículos BMW, utilizando o protocolo proprietário DS2, é a evolução planejada para a fase seguinte do projeto.
Objetivos

Estabelecer comunicação com a ECU de um veículo utilizando hardware de baixo custo.
Realizar a leitura e a interpretação de parâmetros do motor em tempo real.
Disponibilizar os dados lidos em uma interface de visualização acessível em rede.
Estruturar a base técnica para a futura comunicação com a ECU Siemens MS41 via protocolo DS2.

Funcionalidades Principais

Conexão automática com o adaptador ELM327 via Bluetooth Low Energy.
Inicialização automática do adaptador e detecção do protocolo de comunicação.
Leitura cíclica dos parâmetros do motor em tempo real.
Conversão dos dados brutos da ECU em unidades de engenharia.
Mecanismo adaptativo de controle do intervalo entre requisições, aumentando a estabilidade da comunicação.

Parâmetros Monitorados
ParâmetroPIDFórmula de conversãoRotação do motor (RPM)010C((A x 256) + B) / 4Velocidade do veículo (km/h)010DATemperatura do líquido de arrefecimento (°C)0105A - 40Temperatura do ar de admissão (°C)010FA - 40Pressão no coletor de admissão (kPa)010BAPosição da borboleta (%)0111A x 100 / 255Razão lambda e AFR0144lambda = ((A x 256) + B) / 32768; AFR = lambda x 14.7
Os parâmetros acima são lidos diretamente da ECU por meio dos PIDs do padrão OBD-II. A interface de visualização exibe ainda campos adicionais (como pressão de óleo, pressão de combustível, avanço de ignição e tensão da bateria) que, nesta etapa do projeto, são apresentados de forma estimada ou parcial, estando prevista sua leitura completa nas fases seguintes do trabalho.
Tecnologias Utilizadas

Linguagem de Programação: Python 3 (back-end) e JavaScript (front-end)
Comunicação Bluetooth Low Energy: bleak
Servidor HTTP e WebSocket: aiohttp
Programação assíncrona: asyncio (biblioteca padrão)
Interface web: HTML, CSS e JavaScript (sem framework), com gauge desenhado em SVG
Hardware: Raspberry Pi Zero W e adaptador ELM327 Bluetooth

Hardware Necessário

Raspberry Pi Zero W (ou outra placa com suporte a Bluetooth Low Energy)
Adaptador ELM327 com comunicação Bluetooth
Veículo com conector OBD-II

Estrutura do Projeto
.
├── Arquivos                  # Diagramas em PDF
├── elm_pid_request.py        # Script de leitura dos parâmetros via terminal (uso isolado)
├── server/
│   ├── main.py               # Servidor: leitura BLE + HTTP + WebSocket
│   └── requirements.txt      # Dependências do servidor
└── web/
    └── dist/                 # Interface web (dashboard)
        ├── index.html
        ├── css/
        └── js/
O projeto possui dois modos de uso. O script elm_pid_request.py realiza a leitura dos parâmetros e os exibe diretamente no terminal, sendo útil para testes isolados da comunicação. O servidor server/main.py integra a leitura ao servidor web e ao streaming de dados em tempo real para a interface de visualização.
Como rodar
Leitura via terminal (uso isolado)
Para testar apenas a comunicação e a leitura dos parâmetros, instale a biblioteca necessária:
pip install bleak
Conecte o adaptador ELM327 ao conector OBD-II do veículo, ligue a ignição e execute:
python elm_pid_request.py
Os valores lidos serão exibidos diretamente no terminal.
Aplicação completa (servidor + dashboard)
Para executar o sistema completo, com a interface de visualização em tempo real, instale as dependências do servidor. O seguinte comando deve instalar todas elas:
pip install -r server/requirements.txt
Caso prefira instalar manualmente, as dependências são:
pip install aiohttp bleak
Conecte o adaptador ELM327 ao conector OBD-II do veículo e ligue a ignição. Por padrão, o sistema procura automaticamente um dispositivo Bluetooth com o nome "OBDII". Caso o seu adaptador utilize outro nome, ou caso você queira informar diretamente o endereço MAC do adaptador (evitando a etapa de busca), defina as variáveis de ambiente antes de executar:
export ELM_NAME="OBDII"
export ELM_MAC="00:00:00:00:00:00"
Em seguida, inicie o servidor:
python server/main.py
Ao ser iniciado, o servidor localiza o adaptador, estabelece a conexão Bluetooth, realiza a inicialização do ELM327 e começa a transmitir os dados. A interface web fica disponível na porta 3000 (configurável pela variável HTTP_PORT).
Para visualizar o dashboard, conecte o dispositivo cliente (computador, tablet ou celular) à mesma rede da Raspberry Pi e acesse, pelo navegador, o endereço:
http://<IP-DA-RASPBERRY>:3000
A interface conecta-se automaticamente ao servidor por WebSocket e passa a exibir os parâmetros do motor em tempo real. Caso a conexão com o servidor seja interrompida, a interface entra em um modo de demonstração com dados simulados e tenta reconectar automaticamente.
Variáveis de Ambiente
O comportamento da comunicação pode ser ajustado por meio das seguintes variáveis de ambiente (todas opcionais, com valores padrão definidos no código):
VariávelPadrãoDescriçãoELM_NAMEOBDIINome do dispositivo Bluetooth a ser procuradoELM_MAC(vazio)Endereço MAC do adaptador (evita a busca por nome)SEND_DELAY_MS8Atraso após o envio de um comandoCMD_TIMEOUT_MS700Tempo máximo de espera por uma respostaIDLE_DETECT_MS90Tempo de inatividade para considerar a resposta concluídaMIN_CMD_GAP_MS30Intervalo mínimo entre comandosMAX_CMD_GAP_MS90Intervalo máximo entre comandosMIN_RX_BEFORE_IDLE18Quantidade mínima de dados antes da detecção de inatividadeHTTP_HOST0.0.0.0Endereço de escuta do servidor webHTTP_PORT3000Porta do servidor web e do WebSocket
Interface de Visualização (Front-end)
A interface de visualização é uma aplicação web composta por HTML, CSS e JavaScript, sem dependência de frameworks, localizada em web/dist. Ela é servida pelo próprio servidor (server/main.py) e acessada por um navegador em um dispositivo conectado à mesma rede da Raspberry Pi.
A comunicação entre a interface e o servidor ocorre por meio de um WebSocket, pelo qual os dados de telemetria são transmitidos continuamente. A tela apresenta um indicador principal de rotação do motor, desenhado em SVG, e um conjunto de campos com os demais parâmetros monitorados. Caso a conexão com o servidor seja perdida, a interface passa a exibir dados simulados e tenta restabelecer a conexão automaticamente.
Por se tratar de uma aplicação estática, não é necessária nenhuma etapa de compilação: basta que o servidor esteja em execução e que o dispositivo cliente acesse o endereço indicado na seção "Como rodar".
Funcionamento
O sistema opera em duas etapas principais. Na inicialização, uma sequência de comandos AT é enviada ao adaptador ELM327 para configurá-lo e selecionar automaticamente o protocolo de comunicação do veículo. A comunicação é validada pela resposta ao comando 0100, que indica os PIDs suportados pela central.
Após a inicialização, o sistema entra em um laço de leitura contínua, no qual cada parâmetro é requisitado por meio do seu respectivo PID. A resposta hexadecimal retornada pela ECU é interpretada, os bytes de dados úteis são extraídos e as fórmulas de conversão são aplicadas, resultando nos valores em unidades de engenharia.
Para aumentar a robustez da comunicação, o sistema implementa um mecanismo de intervalo adaptativo entre comandos: quando uma resposta inválida é detectada, o intervalo entre as requisições é ampliado; quando as respostas são consistentes, o intervalo é progressivamente reduzido, equilibrando a estabilidade da comunicação com a taxa de atualização dos dados.
Estado do Projeto
O projeto encontra-se em desenvolvimento. A leitura dos parâmetros via padrão OBD-II já está funcional. As etapas planejadas para a continuidade incluem:

Implementação da comunicação com a ECU Siemens MS41 por meio do protocolo proprietário DS2.
Refatoração do sistema para o paradigma de programação orientada a objetos, conforme o diagrama de classes do projeto.
Desenvolvimento de uma aplicação com banco de dados, autenticação de usuários e funcionalidades de cadastro, consulta e manutenção de registros (CRUD), permitindo o armazenamento e a consulta do histórico de dados do veículo.
Integração de uma interface gráfica dedicada à placa embarcada.

Equipe

-Henrique Ricardo Akamoto
-João Victor de Oliveira Borges
-Leonardo Caloni Munduruca