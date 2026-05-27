# Automacao de Relatorios de Monitoria

Projeto Python para enviar relatorios de monitoria ao Google Forms.

Fluxos principais:

- Semanal: alunos nao agendados e alunos que finalizaram o curso.
- Diario: Google Agenda do dia cruzado com Google Docs gerados pelo Read IA.

## Preparacao

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e configure:

```env
GOOGLE_SERVICE_ACCOUNT_JSON={...json completo da service account...}
GOOGLE_SPREADSHEET_ID=...
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo
READIA_DOCS_FOLDER_NAME=Read AI Meeting Notes
READIA_DOCS_FOLDER_ID=
SHEET_NAO_AGENDADOS=Em Análise
SHEET_FINALIZADOS=Finalizaram
DEFAULT_AGENTE=Natanael
```

Tambem e possivel usar `GOOGLE_SERVICE_ACCOUNT_FILE` apontando para um JSON
local. Quando `GOOGLE_SERVICE_ACCOUNT_JSON` estiver preenchida, ela tem
prioridade.

Compartilhe com o e-mail da service account:

- a planilha usada no fluxo semanal;
- a agenda usada no fluxo diario;
- a pasta do Drive `Read AI Meeting Notes`.

No Google Cloud, habilite as APIs Google Sheets, Google Calendar, Google Drive
e Google Docs.

`READIA_DOCS_FOLDER_ID` e opcional. Use quando a busca por nome nao encontrar a
pasta do Read IA, principalmente em Drive compartilhado ou quando houver pastas
com nomes repetidos.

## Fluxo Semanal

Roda sexta-feira as 15:00.

Origem:

- Aba `Em Análise` (`SHEET_NAO_AGENDADOS`) => `Aluno não agendado(Fantasma)`.
- Aba `Finalizaram` (`SHEET_FINALIZADOS`) => `Aluno finalizou o curso`.

O envio aplica duplicidade semanal por matricula, status, ano ISO e semana ISO,
usando os CSVs em `data/submission_logs/`.

Comandos:

```bash
python -m src.weekly_auto_submit --dry-run
python -m src.weekly_auto_submit --date 2026-05-26 --dry-run
python -m src.weekly_auto_submit
python -m src.weekly_auto_submit --yes
```

Sem `--yes`, o modo real pede confirmacao digitando exatamente `ENVIAR`.

## Fluxo Diario

Roda em dias uteis por volta de 15:05.

Origem:

- Google Agenda do dia => monitorias previstas.
- Google Docs na pasta `Read AI Meeting Notes` => presencas confirmadas pelo
  Read IA.

Regra:

- Se houver match com documento do Read IA com score 50 ou maior: envia
  `Presente`.
- Se nao houver match com documento do Read IA: envia `Falta` com motivo
  `Sem resposta`.
- Matches fracos ficam como `Falta` e tambem usam motivo `Sem resposta`.
- Eventos sem matricula reconhecivel no titulo ficam em `eventos_nao_parseados`
  e nao sao enviados automaticamente.

Para `Presente`, o formulario recebe:

- `relatorio_readia`: Summary extraido do Google Docs.
- `link_readia`: link do documento no Google Drive.
- `cursos_consumidos`: curso detectado de forma conservadora ou `Não consumiu`.

Se o Read IA nao gerar ou nao salvar o Google Docs de uma monitoria, ela sera
lancada como `Falta` e deve ser corrigida manualmente no Google Forms.

O envio aplica duplicidade diaria por matricula, status e data.

Comandos:

```bash
python -m src.daily_auto_submit --dry-run
python -m src.daily_auto_submit --date 2026-05-26 --dry-run
python -m src.daily_auto_submit --date 2026-05-26
python -m src.daily_auto_submit --yes
```

Filtros uteis:

```bash
python -m src.daily_auto_submit --presentes-only --dry-run
python -m src.daily_auto_submit --faltas-only --dry-run
python -m src.daily_auto_submit --limit 1 --dry-run
```

O comando diario gera o preview em
`data/previews/preview_agenda_monitoria_YYYY-MM-DD.csv`, gera tambem
`data/previews/debug_matches_YYYY-MM-DD.csv` e em seguida usa o preview para
enviar o Forms.

Para gerar apenas o preview:

```bash
python -m src.preview_monitoria_agenda_do_dia --date 2026-05-26
```

Para inspecionar os documentos do Read IA:

```bash
python -m src.inspect_readia_docs --date 2026-05-27
```

Categorias do preview diario:

- `presentes_confirmados`
- `matches_fracos`
- `faltas_candidatas`
- `eventos_nao_parseados`

O fluxo padrao nao usa aba de correcoes manuais.

## Webhook Read IA Legado

O webhook antigo fica como legado. Ele nao e mais a fonte principal do fluxo
diario, porque o projeto agora usa os Google Docs salvos pelo Read IA no Drive.

Endpoints legados:

```text
GET  /health
GET  /webhook-status
POST /read-webhook
```

## Agendador Windows

Crie duas tarefas no Agendador de Tarefas do Windows.

Semanal:

- Frequencia: semanal
- Dia: sexta-feira
- Horario: 15:00
- Programa: `scripts/run_weekly_auto_submit.bat`

Diario:

- Frequencia: dias uteis
- Horario: 15:05
- Programa: `scripts/run_daily_auto_submit.bat`

Os scripts ativam `.venv`, quando existir, e rodam:

```bash
python -m src.weekly_auto_submit --yes
python -m src.daily_auto_submit --yes
```

O computador precisa estar ligado, conectado a internet e com acesso ao `.env`
e as credenciais configuradas.

## Inspecionar o Google Forms

Use quando o formulario mudar e for necessario revisar os `entry.*`:

```bash
python -m src.inspect_form
```

## Testes

```bash
python -m compileall src
python -m pytest
```
