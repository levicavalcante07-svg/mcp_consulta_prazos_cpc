# MCP de prazos processuais (CPC)

Servidor [MCP](https://modelcontextprotocol.io) que levanta os prazos de um processo judicial brasileiro a partir do número CNJ. Ele busca as intimações publicadas no DJEN (Diário de Justiça Eletrônico Nacional) e calcula os vencimentos em dias úteis, considerando fins de semana, os feriados nacionais (inclusive os móveis) e o recesso forense.

LLMs costumam errar contas com datas, então o cálculo fica numa tool determinística. O modelo só lê a intimação e decide qual é o ato e quem deve praticá-lo.

Funciona com qualquer cliente MCP: Claude Code, Claude Desktop ou um agente próprio (LangChain, por exemplo).

## Instalação

```powershell
git clone https://github.com/levicavalcante07-svg/mcp_consulta_prazos_cpc.git
cd mcp_consulta_prazos_cpc
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Nenhuma chave é obrigatória. Se o CNJ trocar a chave pública do DataJud, pegue a nova em [datajud-wiki.cnj.jus.br/api-publica/acesso](https://datajud-wiki.cnj.jus.br/api-publica/acesso) e coloque num `keys.env` na raiz:

```
DATAJUD_API_KEY=...
```

## Conectar a um cliente

**Claude Code**, rodando na pasta do projeto, com caminhos absolutos:

```powershell
claude mcp add prazos -- C:\caminho\mcp_consulta_prazos_cpc\.venv\Scripts\python.exe C:\caminho\mcp_consulta_prazos_cpc\servidor_prazos.py
```

Depois, é só perguntar: *"quais os prazos do processo 0001234-21.2026.8.04.0001?"*. Os prompts do servidor aparecem como `/mcp__prazos__prazos_do_processo` e `/mcp__prazos__analisar_intimacao`.

**Claude Desktop e outros clientes por stdio**, no arquivo de configuração do cliente:

```json
{
  "mcpServers": {
    "prazos": {
      "command": "C:/caminho/mcp_consulta_prazos_cpc/.venv/Scripts/python.exe",
      "args": ["C:/caminho/mcp_consulta_prazos_cpc/servidor_prazos.py"]
    }
  }
}
```

**Clientes que se conectam por URL:** suba o servidor com `python servidor_prazos.py --http`; ele fica em `http://127.0.0.1:8000/mcp`. Ele escuta só nesta máquina e não tem autenticação.

## O que o servidor expõe

- **Tools:**
  - `calcular_prazo`: devolve o vencimento, os dias pulados com o motivo e o passo a passo;
  - `eh_dia_util`, `dias_uteis_entre` e `listar_feriados`;
  - `validar_numero_cnj`: confere o dígito verificador do número único (Resolução CNJ 65/2008, módulo 97) e informa ano, segmento e tribunal;
  - `buscar_intimacoes`: intimações do processo no DJEN (API Comunica PJe), com texto, data de disponibilização, destinatários e advogados;
  - `consultar_processo`: classe, órgão, assuntos e movimentações no DataJud, sem o texto das intimações.
- **Instruções do servidor:** as regras jurídicas (quando o prazo corre da publicação, prazo em dobro por parte etc.), enviadas a todo cliente ao conectar.
- **Resources:**
  - `prazos://tabela`: os prazos comuns do CPC, com a base legal;
  - `prazos://instrucoes`: as regras e a tabela juntas, prontas para servir de prompt de sistema de um agente.
- **Prompts:** `analisar_intimacao(texto)` e `prazos_do_processo(numero, dias)`.

## Fontes de dados

| Fonte | O que traz | Limites |
|---|---|---|
| **DJEN** (`comunicaapi.pje.jus.br`) | O texto integral das intimações, com a data de disponibilização. É a fonte principal. | Cerca de 20 requisições por janela. Bloqueia redes fora do Brasil (HTTP 403), por exemplo uma VPN corporativa. Só traz o que foi publicado no DJEN; citações por carta, mandado ou Domicílio Eletrônico não aparecem. |
| **DataJud** (`api-publica.datajud.cnj.jus.br`) | Metadados e movimentações do processo. | Não traz o texto. Tem semanas de atraso: processos recentes podem não existir ainda. Processos sigilosos não aparecem. Também tem limite de requisições. |

## Regras implementadas

- **Contagem:** só dias úteis contam (art. 219 do CPC). Exclui-se o dia do começo e inclui-se o do vencimento (art. 224).
- **Feriados fixos:** 1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 20/11 e 25/12.
- **Feriados móveis:** Carnaval (segunda e terça), Sexta-feira Santa e Corpus Christi, calculados a partir da Páscoa.
- **Recesso forense:** de 20/12 a 20/01 (art. 220).
- **DJe:** considera-se publicado no primeiro dia útil após a disponibilização (Lei 11.419/2006, art. 4º, §3º).
- **Prazo em dobro:** é um parâmetro (arts. 183, 186 e 229). Quem decide se ele se aplica é o modelo ou o usuário.

**Fora do escopo:**
- feriados estaduais e municipais: passe-os em `feriados_extras`;
- suspensões por portaria do tribunal e indisponibilidade do sistema;
- prazos materiais (contados em dias corridos);
- Justiça Eleitoral, do Trabalho e Militar, e os Juizados, que têm regras de prazo próprias.

É uma ferramenta de apoio e não substitui a conferência pelo advogado. A identificação do ato e do prazo a partir do texto é feita pelo LLM e pode variar entre execuções. Só o cálculo das datas é determinístico.

## Desenvolvimento

| Comando | O que faz |
|---|---|
| `python -m pytest tests -q` | Testa a lógica (sem MCP, sem LLM, sem rede: as APIs são simuladas) |
| `python teste_cliente.py` | Chama tools, resources e prompts do servidor via `fastmcp.Client` (sem LLM) |
| `fastmcp list servidor_prazos.py` | Lista as tools |
| `fastmcp call servidor_prazos.py calcular_prazo data_inicio=2026-12-18 dias=15` | Chama uma tool pela linha de comando |

**Problemas comuns:**
- **`Connection closed` no cliente:** o servidor morreu ao iniciar. Rode `python servidor_prazos.py` direto e leia o erro.
- **Logs no servidor:** em stdio, nunca use `print()` no servidor, porque o stdout é o canal do protocolo. Use `logging`.
