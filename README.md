# Automacao de Relatorios de Monitoria

Projeto Python para enviar relatorios de monitoria ao Google Forms a partir de
dados organizados em planilhas. A estrutura tambem reserva os pontos de entrada
para uma integracao futura com Read IA.

## Objetivo

- Ler dados de planilhas de acompanhamento.
- Normalizar os registros por tipo de relatorio.
- Enviar os relatorios ao Google Forms.
- Receber e processar dados do Read IA em uma etapa futura.

## Estrutura

- `src/config.py`: configuracoes e carregamento de ambiente.
- `src/sheets_client.py`: leitura de planilhas.
- `src/forms_client.py`: envio ao Google Forms.
- `src/models.py`: modelos compartilhados.
- `src/normalizers.py`: normalizacao dos dados de entrada.
- `src/submit_*.py`: fluxos de envio por tipo de relatorio.
- `src/webhook_readia.py`: entrada futura para webhooks do Read IA.
- `data/`: arquivos locais de trabalho nao versionados.

## Como preparar

1. Criar e ativar um ambiente virtual.
2. Instalar dependencias com `pip install -r requirements.txt`.
3. Configurar credenciais e variaveis locais em arquivos nao versionados.

## Uso

Antes de enviar dados reais, rode o modo dry-run para revisar os payloads:

```bash
python -m src.submit_nao_agendados --dry-run
python -m src.submit_finalizados --dry-run
python -m src.submit_faltas_sem_resposta --dry-run
```

Para enviar ao Google Forms, execute sem `--dry-run` e confirme digitando
`ENVIAR` quando solicitado:

```bash
python -m src.submit_nao_agendados
python -m src.submit_finalizados
python -m src.submit_faltas_sem_resposta
```

O fluxo de faltas sem resposta envia os alunos da aba `SHEET_FALTAS` com
`status = "Falta"` e `motivo_falta = "Sem resposta"`, permitindo ajuste manual
posterior no Forms ou na planilha caso o aluno responda pelo WhatsApp.
