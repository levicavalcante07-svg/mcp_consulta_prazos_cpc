# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projeto

Servidor MCP em Python (FastMCP 3.x) que levanta prazos processuais do CPC brasileiro a partir do número CNJ. O código, os comentários, as docstrings e as mensagens de erro estão em português. Mantenha assim.

Este repositório tem só o servidor. A versão completa, com um agente LangChain conversacional que o consome, fica no repositório do curso (`ax_academy_ai_module`, em `exercicios/m3a01_mcp/02_mcp_prazos_processuais_cpc/`). Mudanças no servidor e nos módulos de domínio devem ser espelhadas lá. A única diferença intencional é como o `keys.env` é carregado: aqui pelo caminho do próprio arquivo; lá com `find_dotenv` a partir da raiz do curso.

## Comandos (Windows/PowerShell, venv em `.venv`)

```powershell
.venv\Scripts\activate
pip install -r requirements-dev.txt               # requirements.txt (servidor) + pytest
python -m pytest tests -q                         # todos os testes
python -m pytest tests -q -k recesso              # um teste
python teste_cliente.py                           # servidor ponta a ponta via fastmcp.Client, sem LLM
fastmcp call servidor_prazos.py calcular_prazo data_inicio=2026-12-18 dias=15
python servidor_prazos.py --http                  # servidor em http://127.0.0.1:8000/mcp
uvicorn app:app --port 8000                       # como roda na Vercel (stateless)
```

Use `python -m pytest` em vez de `pytest`: o `-m` coloca a raiz no `sys.path`, e os testes importam `prazos`.

## Arquitetura

- `prazos.py` concentra toda a regra de datas (feriados, Páscoa, recesso, contagem). É puro, sem MCP, trabalha com `datetime.date` e é o que os testes cobrem. Regra nova entra aqui primeiro, com teste.
- `cnj.py` segue o mesmo padrão para o número único de processo (Resolução CNJ 65/2008): decompõe o número, calcula o dígito por módulo 97 e mapeia J/TR para o tribunal. Formato errado gera `ValueError`, mas dígito errado não: o resultado vem com `valido: False` e o dígito esperado.
- `djen.py` (intimações com texto, fonte principal) e `datajud.py` (metadados e movimentações, com semanas de atraso) falam com as APIs públicas do CNJ via `httpx`. As duas funções recebem `cliente: httpx.Client | None`; os testes passam um `httpx.MockTransport`, então nenhum teste usa rede. Falhas de API viram `RuntimeError` com mensagem orientando o modelo (403 do DJEN = rede fora do Brasil; 429 = limite de requisições).
- `servidor_prazos.py` é uma camada fina: recebe datas como strings (`AAAA-MM-DD` ou `DD/MM/AAAA`), converte com `prazos.parse_data` e delega para os módulos. As docstrings das tools são o que o LLM lê para decidir quando e como chamá-las, então trate-as como interface.
- Erros de entrada são `ValueError` com uma mensagem que ajuda o modelo a se corrigir. O FastMCP repassa essa mensagem ao cliente.
- Na contagem só dias úteis são contados. Por isso o vencimento sempre cai em dia útil, e a prorrogação do art. 224, §1º, não precisa de código próprio.
- O raciocínio jurídico (qual ato, quem pratica, se há dobro, se o prazo corre da publicação ou de uma citação futura) fica num lugar só: `INSTRUCOES` em `servidor_prazos.py`. Ela chega aos clientes de três formas: como `instructions` do `FastMCP` (o Claude Code recebe ao conectar), pelo resource `prazos://instrucoes` (instruções + tabela, usado como prompt de sistema por agentes) e embutida nos dois prompts. Ao corrigir uma análise jurídica errada do LLM, o ajuste costuma ser ali, não no código.

- Hospedagem: `app.py` expõe `mcp.http_app(stateless_http=True)` para a Vercel, que detecta o `app` sozinha. O `vercel.json` fixa a região `gru1` (São Paulo) e tira os testes do pacote. A Vercel instala só o `requirements.txt`, por isso dependências de desenvolvimento ficam no `requirements-dev.txt`. Em serverless não há sessão entre requisições, então nada pode depender de estado em memória.

## Armadilhas

- O servidor roda em stdio, e stdout é o canal do protocolo. Nunca use `print()` em `servidor_prazos.py`; use `logging`.
- Mantenha `fastmcp>=3,<4`. A versão 4.x não foi testada, e no repositório do curso ela puxa `mcp` 2.x, que quebra o `langchain-mcp-adapters`.
- Argumentos de prompts MCP são sempre strings.
- Clientes stdio não repassam o ambiente deles ao servidor. Por isso `servidor_prazos.py` carrega o `keys.env` por conta própria (opcional, só para `DATAJUD_API_KEY`).
- O DJEN recusa IPs de fora do Brasil. Por isso a região da Vercel não pode voltar ao padrão (`iad1`, EUA).
- O DJEN e o DataJud têm limite de requisições. Evite testes ao vivo em laço; espere cerca de 1 minuto após um 429.
- O feriado de 20/11 é nacional desde a Lei 14.759/2023. Feriados locais não são embutidos: entram por `feriados_extras`.
- `.mcp.json`, `keys.env`, `exercicio - aulos/` e o PDF da aula são arquivos locais, fora do git. O material da aula fica no repositório do curso.
