# Automação de Relatórios de Monitoria

Sistema Python para automatizar lançamentos de monitorias no Google Forms a
partir de fontes do Google Workspace. O projeto cruza agenda, relatórios do
Read IA salvos como Google Docs e planilhas de controle para reduzir trabalho
manual e manter duplicidade sob controle.

## Arquitetura

Fontes e destinos:

- Google Agenda: lista as monitorias previstas no dia.
- Google Docs do Read IA: confirma presença e fornece Summary/link do relatório.
- Google Forms: recebe os lançamentos finais de `Presente`, `Falta`, `Aluno não
  agendado(Fantasma)` e `Aluno finalizou o curso`.
- Google Sheets: fornece as abas semanais `Em Análise` e `Finalizaram`.

A fonte diária de presença é a pasta do Drive `Read AI Meeting Notes`, onde o
Read IA salva os documentos automaticamente.

## Render Opcional

O Render não executa o fluxo real de envio. Ele pode ser usado apenas como
healthcheck público para portfólio.

Endpoints:

```text
GET /       => Auto Relatório Monitoria
GET /health => {"status":"ok","mode":"docs"}
```

Start command sugerido:

```bash
gunicorn wsgi:app
```

O fluxo real continua rodando localmente pelo Agendador de Tarefas do Windows.

## Fluxo Semanal

Roda sexta-feira às 15:00.

Entradas:

- Aba `Em Análise` => `Aluno não agendado(Fantasma)`.
- Aba `Finalizaram` => `Aluno finalizou o curso`.

O envio aplica duplicidade semanal por matrícula, status, ano ISO e semana ISO,
usando os CSVs em `data/submission_logs/`.

Comandos:

```bash
python -m src.weekly_auto_submit --dry-run
python -m src.weekly_auto_submit --date 2026-05-26 --dry-run
python -m src.weekly_auto_submit
python -m src.weekly_auto_submit --yes
```

Sem `--yes`, o modo real pede confirmação digitando exatamente `ENVIAR`.

## Fluxo Diário

Roda em dias úteis por volta de 15:05.

Entradas:

- Google Agenda do dia => monitorias previstas.
- Google Docs na pasta `Read AI Meeting Notes` => presenças confirmadas pelo
  Read IA.

Regra:

- Match com documento Read IA, score 50 ou maior: envia `Presente`.
- Sem match com documento Read IA: envia `Falta` com motivo `Sem resposta`.
- Match fraco: envia `Falta` com motivo `Sem resposta`.
- Evento sem matrícula reconhecível: fica em `eventos_nao_parseados` e não é
  enviado automaticamente.

Para `Presente`, o Forms recebe:

- `relatorio_readia`: Summary extraído do Google Docs.
- `link_readia`: link do documento no Google Drive.
- `cursos_consumidos`: curso detectado de forma conservadora ou `Não consumiu`.

Se o Read IA não gerar/salvar o documento de uma monitoria, ela será lançada
como `Falta` e deve ser corrigida manualmente no Google Forms.

O envio aplica duplicidade diária por matrícula, status e data.

Comandos:

```bash
python -m src.daily_auto_submit --dry-run
python -m src.daily_auto_submit --date 2026-05-26 --dry-run
python -m src.daily_auto_submit --date 2026-05-26
python -m src.daily_auto_submit --yes
```

Filtros:

```bash
python -m src.daily_auto_submit --presentes-only --dry-run
python -m src.daily_auto_submit --faltas-only --dry-run
python -m src.daily_auto_submit --limit 1 --dry-run
```

O comando diário gera:

- `data/previews/preview_agenda_monitoria_YYYY-MM-DD.csv`
- `data/previews/debug_matches_YYYY-MM-DD.csv`

Para gerar apenas o preview:

```bash
python -m src.preview_monitoria_agenda_do_dia --date 2026-05-26
```

Para inspecionar os documentos do Read IA:

```bash
python -m src.inspect_readia_docs --date 2026-05-27
```

## Configuração

Crie um ambiente virtual e instale as dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e configure:

```env
GOOGLE_SERVICE_ACCOUNT_JSON={...json completo da service account...}
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google-service-account.json
GOOGLE_SPREADSHEET_ID=
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo
READIA_DOCS_FOLDER_NAME=Read AI Meeting Notes
READIA_DOCS_FOLDER_ID=
SHEET_NAO_AGENDADOS=Em Análise
SHEET_FINALIZADOS=Finalizaram
SHEET_PRESENTES=Presentes
SHEET_ATIVOS=Ativo
DEFAULT_AGENTE=Natanael
FORM_URL=https://docs.google.com/forms/d/e/.../viewform
```

`GOOGLE_SERVICE_ACCOUNT_JSON` tem prioridade sobre
`GOOGLE_SERVICE_ACCOUNT_FILE`. Use `READIA_DOCS_FOLDER_ID` quando a busca por
nome não encontrar a pasta do Read IA.

Compartilhe com o e-mail da service account:

- a planilha semanal;
- a agenda das monitorias;
- a pasta do Drive `Read AI Meeting Notes`.

No Google Cloud, habilite:

- Google Sheets API
- Google Calendar API
- Google Drive API
- Google Docs API

Não versione `.env`, arquivos em `credentials/`, exports locais ou CSVs gerados.

## Agendador Windows

Crie duas tarefas no Agendador de Tarefas.

Semanal:

- Frequência: semanal
- Dia: sexta-feira
- Horário: 15:00
- Programa: `scripts/run_weekly_auto_submit.bat`

Diário:

- Frequência: dias úteis
- Horário: 15:05
- Programa: `scripts/run_daily_auto_submit.bat`

Os scripts ativam `.venv`, quando existir, e rodam:

```bash
python -m src.weekly_auto_submit --yes
python -m src.daily_auto_submit --yes
```

## Qualidade

Detecção de curso é conservadora:

- não infere Python I/II só por “curso de Python”;
- só marca curso perto de expressão clara de consumo;
- contexto de meta, orientação ou tarefa futura não conta como consumo.

Rodar validação local:

```bash
python -m compileall src
python -m pytest
```

Para revisar os campos do Google Forms quando o formulário mudar:

```bash
python -m src.inspect_form
```
