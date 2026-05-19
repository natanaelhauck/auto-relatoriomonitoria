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

Copie `.env.example` para `.env`, preencha `GOOGLE_SPREADSHEET_ID` e coloque a
credencial da service account em `credentials/google-service-account.json`.

Exemplo de abas no `.env`:

```env
SHEET_NAO_AGENDADOS=Em Análise
SHEET_FINALIZADOS=Finalizaram
SHEET_FALTAS=Faltas
SHEET_PRESENTES=Presentes
```

## Inspecionar o formulario

Use o inspetor quando o Google Forms mudar e for necessario revisar os entry IDs:

```bash
python -m src.inspect_form
```

## Dry-run

Antes de enviar dados reais, revise os payloads:

```bash
python -m src.submit_nao_agendados --dry-run
python -m src.submit_finalizados --dry-run
python -m src.submit_faltas_sem_resposta --dry-run
```

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
aluno. Esses logs ajudam a identificar duplicidades, mas ainda nao bloqueiam
envios repetidos.

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
