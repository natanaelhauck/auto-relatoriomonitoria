# Automacao de Relatorios de Monitoria

Projeto Python para enviar relatorios de monitoria ao Google Forms a partir de
dados organizados em planilhas. A estrutura tambem reserva pontos de entrada
para integracao com Read IA.

## Objetivo

- Ler dados de planilhas de acompanhamento.
- Normalizar registros por tipo de relatorio.
- Enviar relatorios ao Google Forms.
- Receber payloads do Read IA para preparar envios de presenca.

## Estrutura

- `src/sheets_client.py`: leitura de planilhas Google Sheets.
- `src/forms_client.py`: validacao e envio HTTP ao Google Forms.
- `src/submission_runner.py`: execucao em lote, confirmacao e logs CSV.
- `src/inspect_form.py`: inspecao dos `entry.*` do formulario.
- `src/submit_*.py`: fluxos de envio por tipo de relatorio.
- `src/webhook_readia.py`: endpoint Flask para payloads do Read IA.
- `data/submission_logs/`: logs CSV locais de execucoes reais.

## Preparacao

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha `GOOGLE_SPREADSHEET_ID`. Para a
credencial da service account, use uma das opcoes:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: conteudo completo do JSON da service account.
- `GOOGLE_SERVICE_ACCOUNT_FILE`: caminho para o arquivo JSON local, por exemplo
  `credentials/google-service-account.json`.

Quando `GOOGLE_SERVICE_ACCOUNT_JSON` estiver preenchida, ela tem prioridade
sobre `GOOGLE_SERVICE_ACCOUNT_FILE`.

Exemplo de abas e agenda no `.env`:

```env
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo
SHEET_NAO_AGENDADOS=Em Análise
SHEET_FINALIZADOS=Finalizaram
SHEET_PRESENTES=Presentes
SHEET_ATIVOS=Ativo
```

## Inspecionar o formulario

Use o inspetor quando o Google Forms mudar e for necessario revisar os entry IDs:

```bash
python -m src.inspect_form
```

## Webhook Read IA

O webhook Flask recebe payloads do Read IA, salva os arquivos em
`data/read_payloads/` e tambem registra cada payload na aba configurada por
`SHEET_READIA_PAYLOADS` no Google Sheets. Os JSONs recebidos ficam ignorados
pelo Git; apenas o `.gitkeep` da pasta e versionado.

Para rodar localmente:

```bash
python -m src.webhook_readia
```

URLs locais:

```text
http://localhost:5000/read-webhook
http://localhost:5000/health
```

Para testar os payloads salvos:

```bash
python -m src.inspect_readia_payloads
```

Para conferir os ultimos payloads salvos no Google Sheets:

```bash
python -m src.inspect_readia_sheet
```

Para o Read IA enviar dados para sua maquina local, sera necessario expor essa
porta com ngrok ou hospedar o webhook em um servidor acessivel pela internet.

## Deploy Render

Crie um Web Service no Render e conecte o repositorio do GitHub.

Configure as variaveis de ambiente no Render. Para as credenciais do Google,
use:

```env
GOOGLE_SERVICE_ACCOUNT_JSON={...conteudo completo do JSON da service account...}
```

O valor deve ser o JSON completo baixado da service account, incluindo chaves
como `type`, `project_id`, `private_key`, `client_email` e `token_uri`. No
Render nao e necessario criar o arquivo `credentials/google-service-account.json`
quando `GOOGLE_SERVICE_ACCOUNT_JSON` estiver configurada.

Build:

```bash
pip install -r requirements.txt
```

Start:

```bash
gunicorn wsgi:app
```

Depois de publicado, valide o healthcheck:

```text
https://URL/health
```

## Teste do Read IA com ngrok

Execute:

```bash
scripts/start_readia_webhook.bat
```

Pegue a URL gerada pelo ngrok:

```text
https://xxxx.ngrok-free.app
```

Configure no Read IA:

```text
https://xxxx.ngrok-free.app/read-webhook
```

Depois verifique os payloads recebidos:

```bash
python -m src.inspect_readia_payloads
```

## Preview Diario Agenda + Read IA

O fluxo diario de presenca/falta usa o Google Agenda como base do dia, nao a
aba `Ativo`. Cada evento da agenda deve trazer nome e matricula no titulo, por
exemplo:

```text
Octavio Augusto de Araujo Americo PDBD163 and Natanael Hauck
```

Gere um CSV de revisao cruzando os eventos da agenda com os payloads Read IA
salvos em `data/read_payloads/`:

```bash
python -m src.preview_monitoria_agenda_do_dia --date 2026-05-21
```

O arquivo gerado fica em `data/previews/preview_agenda_monitoria_YYYY-MM-DD.csv`
e classifica os eventos em:

- `presentes_confirmados`: match com confianca 80 ou maior.
- `matches_fracos`: match entre 60 e 79, exige revisao manual.
- `faltas_candidatas`: evento agendado sem match confirmado no Read IA do dia.
- `eventos_nao_parseados`: evento sem matricula reconhecivel no titulo.

As regras mais fortes sao matricula encontrada no titulo/resumo/texto bruto do
Read IA e nome completo encontrado no titulo do Read IA. Horario proximo ajuda
na revisao, mas sozinho nao confirma presenca.

A aba `Ativo` pode ser usada como apoio para completar dados cadastrais, mas nao
e a base principal para gerar faltas do dia.

Se usar service account, compartilhe a agenda configurada em
`GOOGLE_CALENDAR_ID` com o e-mail dessa service account e habilite a Google
Calendar API no projeto.

## Preview Diario Ativos + Read IA

Este preview antigo cruza todos os alunos ativos com os payloads Read IA e serve
apenas como apoio cadastral/revisao, nao como base principal de faltas.

```bash
python -m src.preview_monitoria_do_dia --date 2026-05-21
```

## Dry-run

Antes de enviar dados reais, revise os payloads:

```bash
python -m src.submit_nao_agendados --dry-run
python -m src.submit_finalizados --dry-run
python -m src.submit_faltas_sem_resposta --dry-run
```

## Faltas

O fluxo principal de faltas usa o Google Agenda como fonte dos alunos
agendados e os payloads salvos do Read IA como confirmacao de presenca. Quando
um evento de monitoria do dia tem nome e matricula no titulo, mas nao tem match
confirmado no Read IA do mesmo dia, o aluno entra como `Falta` com motivo
`Sem resposta`.

Nao use `SHEET_FALTAS`: nao e necessario ter aba manual de faltas na planilha.
Eventos sem matricula reconhecivel no titulo nao sao enviados automaticamente;
revise antes com o preview de agenda.

Exemplos:

```bash
python -m src.submit_faltas_sem_resposta --dry-run
python -m src.submit_faltas_sem_resposta --date 2026-05-05 --dry-run
python -m src.submit_faltas_sem_resposta --limit 1 --dry-run
python -m src.submit_faltas_sem_resposta --only-matricula PDITA355 --dry-run
```

O fluxo de faltas consulta os CSVs em `data/submission_logs/` e pula registros
ja enviados com a mesma matricula, o mesmo status, a mesma semana ISO e o mesmo
ano ISO.

Envio da semana atual, usando a data de hoje em `America/Sao_Paulo`:

```bash
python -m src.submit_nao_agendados --dry-run
python -m src.submit_finalizados --dry-run
```

Envio retroativo, informando a data que deve ir para o Forms:

```bash
python -m src.submit_nao_agendados --date 2026-05-05 --dry-run
python -m src.submit_finalizados --date 2026-05-05 --dry-run
```

Teste seguro com apenas 1 aluno:

```bash
python -m src.submit_nao_agendados --date 2026-05-05 --limit 1 --dry-run
python -m src.submit_finalizados --date 2026-05-05 --limit 1 --dry-run
```

Teste por matrícula:

```bash
python -m src.submit_nao_agendados --date 2026-05-05 --only-matricula PDITA355 --dry-run
```

## Envio real

Execute sem `--dry-run` e confirme digitando exatamente `ENVIAR`:

```bash
python -m src.submit_nao_agendados
python -m src.submit_finalizados
python -m src.submit_faltas_sem_resposta
```

Os mesmos argumentos `--date`, `--limit` e `--only-matricula` podem ser usados no
envio real; a confirmação `ENVIAR` continua obrigatória.

Cada execucao real gera um CSV em `data/submission_logs/` com o resultado por
aluno. Esses logs sao usados pelo envio semanal e pelo fluxo de faltas para
evitar duplicidades por matricula, status e semana ISO.

## Envio Semanal

O envio semanal combina os alunos de `SHEET_NAO_AGENDADOS` e
`SHEET_FINALIZADOS`, usa a data atual em `America/Sao_Paulo` e evita
duplicidade automaticamente. Antes de enviar, ele consulta os CSVs em
`data/submission_logs/` e pula registros que ja tenham envio com a mesma
matricula, o mesmo status, a mesma semana ISO e o mesmo ano ISO.

```bash
python -m src.weekly_auto_submit --dry-run
python -m src.weekly_auto_submit --limit 1 --dry-run
python -m src.weekly_auto_submit --yes
```

Para envio retroativo semanal:

```bash
python -m src.weekly_auto_submit --date 2026-05-05 --dry-run
```

## Agendador do Windows

Para rodar automaticamente toda sexta-feira as 15:00:

1. Abra o Agendador de Tarefas do Windows.
2. Selecione `Criar Tarefa Basica`.
3. Escolha frequencia semanal.
4. Marque sexta-feira.
5. Defina o horario `15:00`.
6. Em acao, escolha `Iniciar um programa`.
7. Em programa, selecione o arquivo `scripts/run_weekly_auto_submit.bat`.

O computador precisa estar ligado, conectado a internet e com acesso as
credenciais configuradas no `.env`.
