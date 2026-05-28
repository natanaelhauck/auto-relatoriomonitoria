# Auto Relatório Monitoria

Automação em Python para registrar monitorias no Google Forms usando dados do
Google Workspace e relatórios gerados pelo Read IA.

O projeto foi desenhado para reduzir trabalho operacional recorrente: ele cruza
as monitorias previstas no Google Agenda com os relatórios do Read IA salvos no
Google Drive, identifica presença/falta, prepara o payload do Google Forms e
evita envios duplicados.

## Visão Geral

### Fluxo diário

Fonte principal:

- Google Agenda: monitorias previstas para a data.
- Google Docs do Read IA: relatórios salvos automaticamente na pasta
  `Read AI Meeting Notes`.
- Google Forms: destino final dos lançamentos.

Regra de decisão:

- Evento da Agenda com match em documento do Read IA: `Presente`.
- Evento da Agenda sem match em documento do Read IA: `Falta`, motivo
  `Sem resposta`.
- Evento sem matrícula reconhecível no título: fica fora do envio automático.

Para alunos presentes, o sistema envia:

- Summary extraído do Google Docs.
- Link real do relatório Read IA, extraído do hyperlink do campo `Meeting:`.
- Cursos consumidos, detectados de forma conservadora.

### Fluxo semanal

Fonte principal:

- Aba `Em Análise`: alunos não agendados.
- Aba `Finalizaram`: alunos que finalizaram o curso.
- Google Forms: destino final dos lançamentos.

O envio semanal aplica controle de duplicidade por matrícula, status, ano ISO e
semana ISO.

## Arquitetura

```text
Google Agenda ─┐
               ├─ preview diário ── submit diário ── Google Forms
Google Docs ───┘
   Read IA

Google Sheets ── submit semanal ─── Google Forms
```

Componentes principais:

- `src/readia_docs_client.py`: leitura dos Google Docs do Read IA via Drive API
  e Docs API.
- `src/readia_matcher.py`: matching por matrícula, nome completo, primeiro e
  segundo nome.
- `src/preview_monitoria_agenda_do_dia.py`: gera o CSV de conferência diário.
- `src/submit_monitoria_agenda_do_dia.py`: envia presentes e faltas a partir do
  preview.
- `src/daily_auto_submit.py`: comando único para preview + envio diário.
- `src/weekly_auto_submit.py`: envio semanal de não agendados e finalizados.
- `src/course_detection.py`: detecção conservadora de cursos consumidos.

## Matching Read IA

O matching prioriza sinais fortes:

- Matrícula no título/texto do documento.
- Nome completo.
- Primeiro e segundo nome.
- Primeiro nome com sobrenome relevante.

O relatório do Read IA é lido a partir do Google Docs. O link enviado ao Forms
vem do hyperlink aplicado pelo Read IA no campo `Meeting:`. Se esse hyperlink
não existir, o sistema usa o link do Google Docs como fallback.

## Detecção de Cursos

A detecção é intencionalmente conservadora:

- Não infere `Python I` ou `Python II` apenas por texto genérico como
  “curso de Python”.
- Só marca curso quando há expressão clara de consumo perto do nome do curso,
  como `consumiu`, `assistiu`, `concluiu`, `entregou`, `iniciou`, `avançou`,
  `fez` ou `estudou`.
- Contexto futuro ou de meta não conta como consumo, por exemplo
  `próxima semana`, `deve fazer`, `recomendado`, `orientação` ou
  `tarefa futura`.

Quando o texto é ambíguo, o sistema envia `Não consumiu`.

## Configuração

Crie o ambiente virtual e instale as dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e configure:

```env
GOOGLE_SERVICE_ACCOUNT_JSON=
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/google-service-account.json

GOOGLE_SPREADSHEET_ID=
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo

READIA_DOCS_FOLDER_NAME=Read AI Meeting Notes
READIA_DOCS_FOLDER_ID=

SHEET_NAO_AGENDADOS=Em Análise
SHEET_FINALIZADOS=Finalizaram
SHEET_ATIVOS=Ativo

DEFAULT_AGENTE=Natanael
FORM_URL=https://docs.google.com/forms/d/e/.../viewform
```

Observações:

- `GOOGLE_SERVICE_ACCOUNT_JSON` tem prioridade sobre
  `GOOGLE_SERVICE_ACCOUNT_FILE`.
- `READIA_DOCS_FOLDER_ID` é opcional, mas recomendado quando houver mais de uma
  pasta com o mesmo nome ou quando a busca por nome não localizar a pasta.
- A service account precisa ter acesso à planilha, à agenda e à pasta
  `Read AI Meeting Notes`.

APIs necessárias no Google Cloud:

- Google Calendar API
- Google Docs API
- Google Drive API
- Google Sheets API

Não versione `.env`, arquivos em `credentials/`, CSVs gerados ou exports locais.

## Uso Diário

Gerar apenas o preview:

```bash
python -m src.preview_monitoria_agenda_do_dia --date 2026-05-27
```

Inspecionar os documentos do Read IA:

```bash
python -m src.inspect_readia_docs --date 2026-05-27
```

Rodar preview + dry-run do envio:

```bash
python -m src.daily_auto_submit --date 2026-05-27 --dry-run
```

Enviar de fato:

```bash
python -m src.daily_auto_submit --date 2026-05-27
```

Execução automática sem confirmação:

```bash
python -m src.daily_auto_submit --yes
```

Filtros úteis:

```bash
python -m src.daily_auto_submit --presentes-only --dry-run
python -m src.daily_auto_submit --faltas-only --dry-run
python -m src.daily_auto_submit --limit 5 --dry-run
```

Arquivos gerados:

- `data/previews/preview_agenda_monitoria_YYYY-MM-DD.csv`
- `data/previews/debug_matches_YYYY-MM-DD.csv`
- `data/submission_logs/*.csv`

## Uso Semanal

Dry-run:

```bash
python -m src.weekly_auto_submit --dry-run
```

Enviar de fato:

```bash
python -m src.weekly_auto_submit
```

Execução automática sem confirmação:

```bash
python -m src.weekly_auto_submit --yes
```

## Agendamento no Windows

O fluxo real roda localmente pelo Agendador de Tarefas do Windows.

Tarefa semanal:

- Frequência: semanal
- Dia: sexta-feira
- Horário: 15:00
- Script: `scripts/run_weekly_auto_submit.bat`

Tarefa diária:

- Frequência: dias úteis
- Horário: 15:05
- Script: `scripts/run_daily_auto_submit.bat`

Os scripts ativam `.venv`, quando existir, e executam os comandos com `--yes`.

## Render Opcional

O Render não participa do fluxo real. Ele existe apenas como healthcheck público
para portfólio.

Endpoints:

```text
GET /        Auto Relatório Monitoria
GET /health  {"status":"ok","mode":"docs"}
```

Start command:

```bash
gunicorn wsgi:app
```

## Testes

```bash
python -m compileall src
python -m pytest
```

## Estrutura

```text
src/
  calendar_client.py
  readia_docs_client.py
  readia_matcher.py
  preview_monitoria_agenda_do_dia.py
  submit_monitoria_agenda_do_dia.py
  daily_auto_submit.py
  weekly_auto_submit.py
  course_detection.py
  forms_client.py
  sheets_client.py
  submission_runner.py
```

## Escopo

Este projeto não depende de webhook do Read IA. Se um documento do Read IA não
for salvo no Google Drive, a monitoria será tratada como `Falta` no fluxo
diário e poderá ser corrigida manualmente no Google Forms.
