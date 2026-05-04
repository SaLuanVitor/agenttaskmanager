# Agent Task Manager

Agente de gerenciamento de tarefas integrado ao Trello, desenvolvido com **Google ADK** e **py-trello**.

O projeto permite criar e organizar tarefas em um quadro do Trello usando linguagem natural.

## Estrutura do projeto

```text
agenttaskmanager/
├── __init__.py
├── agent.py
├── .env.example
├── .gitignore
└── README.md

O arquivo .env deve existir localmente, mas não deve ser enviado para o GitHub.

Requisitos
Python 3.10+
Conta no Trello
API Key do Google Gemini
API Key e Token do Trello
Ambiente virtual Python configurado
Dependências

Instale as dependências no ambiente virtual:

pip install google-adk py-trello python-dotenv

datetime não precisa ser instalado, pois já faz parte da biblioteca padrão do Python.

Arquivo .env

Crie um arquivo .env na raiz do projeto, com base no .env.example:

GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=
TRELLO_API_KEY=
TRELLO_API_SECRET=
TRELLO_TOKEN=
Variáveis de ambiente
Variável	Descrição
GOOGLE_GENAI_USE_VERTEXAI	Define se o ADK usará Vertex AI. Para uso com API Key, mantenha 0.
GOOGLE_API_KEY	Chave da API do Google Gemini usada pelo ADK.
TRELLO_API_KEY	Chave da API do Trello.
TRELLO_API_SECRET	Segredo da API do Trello.
TRELLO_TOKEN	Token de acesso do Trello com permissão de leitura e escrita.
Como executar

No ambiente local, o pacote do agente deve estar dentro de uma pasta pai, por exemplo:

agent04/
├── .lab-dio/
└── agenttaskmanager/
    ├── __init__.py
    ├── agent.py
    └── .env

Ative o ambiente virtual:

.\.lab-dio\Scripts\Activate.ps1

Depois execute o ADK a partir da pasta que contém agenttaskmanager:

adk web

Exemplo:

(.lab-dio) PS .\agent04> adk web

O comando adk web deve ser executado na pasta acima de agenttaskmanager, pois o ADK carrega o agente a partir do pacote Python.

Funcionalidades
Criar tarefas no Trello;
Listar tarefas;
Filtrar tarefas por status;
Mover tarefas entre listas;
Marcar tarefas como concluídas;
Alterar nome, descrição e vencimento;
Arquivar tarefas com confirmação.
Listas esperadas no Trello

O agente espera encontrar um quadro chamado:

Minhas Atividades

E as seguintes listas:

A FAZER
EM ANDAMENTO
CONCLUÍDAS
Exemplos de uso
Criar uma tarefa para comprar ração para Ellie hoje.
Liste minhas tarefas de hoje.
Mova a tarefa "Comprar ração para Ellie" para em andamento.
Marque a tarefa "Lavar roupas" como concluída.
Altere o vencimento da tarefa "Estudar Python" para 05/05/2026.
Arquive a tarefa "Tirar o lixo".
Observações importantes
O .env não deve ser versionado.
O .env.example deve ser mantido como modelo.
O ambiente .lab-dio não deve ser enviado para o GitHub.
O agente depende dos nomes corretos do quadro e das listas no Trello.
Para criar cards, o token do Trello precisa ter permissão de leitura e escrita.
