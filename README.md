# Automacao de Relatorios de Monitoria

Projeto Python para enviar relatorios de monitoria ao Google Forms usando dois
fluxos principais:

- Semanal: alunos nao agendados e alunos que finalizaram o curso.
- Diario: Google Agenda do dia cruzado com payloads do Read IA.

## Preparacao

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e configure as variaveis principais:

```env
GOOGLE_SERVICE_ACCOUNT_JSON={...json completo da service account...}
GOOGLE_SPREADSHEET_ID=...
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo
SHEET_NAO_AGENDADOS=Em Análise
SHEET_FINALIZADOS=Finalizaram
SHEET_READIA_PAYLOADS=ReadIA Payloads
DEFAULT_AGENTE=Natanael
```

Tambem e possivel usar `GOOGLE_SERVICE_ACCOUNT_FILE` apontando para um arquivo
JSON local. Quando `GOOGLE_SERVICE_ACCOUNT_JSON` estiver preenchida, ela tem
prioridade.

Compartilhe a planilha e a agenda com o e-mail da service account, e habilite
as APIs Google Sheets e Google Calendar no projeto Google Cloud.

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
- Aba `ReadIA Payloads` => presencas confirmadas pelo Read IA.

Regra:

- Se houver match Read IA com score 50 ou maior: envia `Presente`.
- Se nao houver match Read IA: envia `Falta` com motivo `Sem resposta`.
- Matches fracos ficam como `Falta` e tambem usam motivo `Sem resposta`.
- Eventos sem matricula reconhecivel no titulo ficam em `eventos_nao_parseados`
  e nao sao enviados automaticamente.

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
`data/previews/preview_agenda_monitoria_YYYY-MM-DD.csv` e em seguida usa esse
arquivo para enviar o Forms.

Para gerar apenas o preview:

```bash
python -m src.preview_monitoria_agenda_do_dia --date 2026-05-26
```

Categorias do preview diario:

- `presentes_confirmados`
- `matches_fracos`
- `faltas_candidatas`
- `eventos_nao_parseados`

Se o webhook do Read IA falhar ou o Read IA nao enviar payload de uma monitoria,
ela sera lancada como `Falta` e pode ser corrigida manualmente no Google Forms.
O fluxo padrao nao usa aba de correcoes manuais.

## Webhook Read IA

O webhook recebe payloads do Read IA, salva uma copia local em
`data/read_payloads/` e registra os dados na aba `ReadIA Payloads`.

Rodar localmente:

```bash
python -m src.webhook_readia
```

Endpoints:

```text
GET  /health
GET  /webhook-status
POST /read-webhook
```

Blindagens mantidas:

- Payload grande e truncado antes de ir para a celula do Google Sheets.
- `payload_json_size` guarda o tamanho original.
- Deduplicacao por `meeting_id` ou `report_url`.
- Sucesso ao salvar na planilha retorna HTTP 200.
- Falha ao salvar na planilha retorna HTTP 500 com `status: "sheet_error"`.
- A aba registra `sheet_status` e `sheet_error`.

Inspecao:

```bash
python -m src.inspect_readia_payloads
python -m src.inspect_readia_sheet --date 2026-05-26
```

Para receber webhooks fora da maquina local, hospede o app ou exponha a porta
com ngrok e configure a URL publica no Read IA:

```text
https://URL_PUBLICA/read-webhook
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
