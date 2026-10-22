"""Servidor MCP de prazos processuais (CPC).

    python servidor_prazos.py           # stdio (padrão): o cliente inicia o servidor (Claude Code, Claude Desktop...)
    python servidor_prazos.py --http    # HTTP em http://127.0.0.1:8000/mcp, para clientes que se conectam por URL

Testar sem LLM (ambiente virtual ativado):
    python teste_cliente.py
    fastmcp list servidor_prazos.py
    fastmcp call servidor_prazos.py calcular_prazo data_inicio=2026-12-18 dias=15
Em stdio, NUNCA use print() aqui: stdout é o canal do protocolo. Use logging (vai para stderr).
"""
import json
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

import cnj
import datajud
import djen
import prazos

# Clientes stdio não repassam as variáveis de ambiente deles: o servidor lê o keys.env sozinho
load_dotenv(Path(__file__).parent / "keys.env")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prazos")

TABELA_PRAZOS = {
    "contestação": {"dias": 15, "base": "CPC art. 335"},
    "réplica": {"dias": 15, "base": "CPC arts. 350 e 351"},
    "apelação": {"dias": 15, "base": "CPC art. 1.003, §5º"},
    "contrarrazões de apelação": {"dias": 15, "base": "CPC art. 1.010, §1º"},
    "agravo de instrumento": {"dias": 15, "base": "CPC art. 1.003, §5º"},
    "agravo interno": {"dias": 15, "base": "CPC art. 1.003, §5º"},
    "embargos de declaração": {"dias": 5, "base": "CPC art. 1.023"},
    "recurso especial": {"dias": 15, "base": "CPC art. 1.003, §5º"},
    "recurso extraordinário": {"dias": 15, "base": "CPC art. 1.003, §5º"},
    "impugnação ao cumprimento de sentença": {"dias": 15, "base": "CPC art. 525"},
    "pagamento voluntário (cumprimento de sentença)": {"dias": 15, "base": "CPC art. 523"},
    "embargos à execução": {"dias": 15, "base": "CPC art. 915"},
    "embargos à execução fiscal": {"dias": 30, "base": "Lei 6.830/1980, art. 16"},
    "manifestação genérica sem prazo fixado pelo juiz": {"dias": 5, "base": "CPC art. 218, §3º"},
}

# Enviadas a todo cliente MCP ao conectar (Claude Code, agentes...): é o "manual" do servidor
INSTRUCOES = """\
Servidor de prazos processuais do CPC brasileiro (Justiça Estadual e Federal comum).
Regras para levantar prazos:
- Nunca conte datas de cabeça: use calcular_prazo, que considera dias úteis, feriados nacionais e o recesso de 20/12 a 20/01.
- Para prazos de um processo, valide o número (validar_numero_cnj) e busque as intimações no DJEN (buscar_intimacoes). Leia o texto de cada uma e identifique destinatário e polo, ato exigido e prazo. Prazo fixado pelo juiz no texto prevalece sobre o prazo legal (tabela em prazos://tabela).
- A publicação no DJEN intima os ADVOGADOS cadastrados. Se o texto manda citar ou intimar alguém pessoalmente (carta, mandado, oficial de justiça, edital, Domicílio Judicial Eletrônico), o prazo corre da futura citação/intimação, não da publicação: situação "aguarda citação/intimação", sem cálculo.
- Comunicações sem ato a praticar (lista de distribuição, mero expediente) não geram prazo.
- Prazo em dobro é decidido por parte: só para quem pratica o ato e é Fazenda Pública (União, Estados, Municípios, autarquias), Defensoria, ou litisconsorte com procurador diferente em autos físicos.
- Prazo que corre da publicação: calcular_prazo com data_inicio = data_disponibilizacao e data_e_disponibilizacao=True.
- Se o DJEN falhar ou vier vazio, use consultar_processo (DataJud) e deixe claro que o ato e o prazo foram DEDUZIDOS das movimentações.
- Ao apresentar prazos, informe vencimento e situação (vencido / vence hoje / em curso / aguarda citação) e as ressalvas: feriados locais e suspensões do tribunal não considerados; conferir no sistema do tribunal.
"""

mcp = FastMCP("prazos", instructions=INSTRUCOES)


def _tabela_texto() -> str:
    return "\n".join(f"- {ato}: {p['dias']} dias ({p['base']})" for ato, p in TABELA_PRAZOS.items())


def _datas_extras(feriados_extras: list[str]):
    return [prazos.parse_data(d) for d in feriados_extras]


@mcp.tool
def calcular_prazo(
    data_inicio: str,
    dias: int,
    em_dobro: bool = False,
    data_e_disponibilizacao: bool = False,
    feriados_extras: list[str] | None = None,
) -> dict:
    """Calcula o vencimento de um prazo processual do CPC contado em dias úteis.

    Use SEMPRE esta tool em vez de contar datas de cabeça: ela considera fins de semana,
    feriados nacionais (inclusive Carnaval, Sexta-feira Santa e Corpus Christi) e o
    recesso forense de 20/12 a 20/01.

    Args:
        data_inicio: data da intimação (ou da disponibilização no DJe), AAAA-MM-DD ou DD/MM/AAAA.
        dias: prazo em dias, como previsto na lei (ex.: 15 para contestação).
        em_dobro: True para Fazenda Pública (art. 183), Defensoria (art. 186) ou
            litisconsortes com procuradores diferentes em autos físicos (art. 229).
        data_e_disponibilizacao: True se data_inicio é a disponibilização no DJe; a
            publicação passa a ser o primeiro dia útil seguinte.
        feriados_extras: feriados estaduais/municipais da comarca, em AAAA-MM-DD.
    """
    resultado = prazos.calcular_prazo(
        prazos.parse_data(data_inicio),
        dias,
        em_dobro=em_dobro,
        data_e_disponibilizacao=data_e_disponibilizacao,
        feriados_extras=_datas_extras(feriados_extras or []),
    )
    log.info("calcular_prazo(%s, %s) -> %s", data_inicio, dias, resultado["vencimento"])
    return resultado


@mcp.tool
def eh_dia_util(data: str, feriados_extras: list[str] | None = None) -> dict:
    """Diz se uma data é dia útil forense e, se não for, o motivo.

    Args:
        data: AAAA-MM-DD ou DD/MM/AAAA.
        feriados_extras: feriados locais da comarca, em AAAA-MM-DD.
    """
    d = prazos.parse_data(data)
    motivo = prazos.motivo_nao_util(d, set(_datas_extras(feriados_extras or [])))
    return {"data": d.isoformat(), "dia_util": motivo is None, "motivo": motivo}


@mcp.tool
def dias_uteis_entre(inicio: str, fim: str, feriados_extras: list[str] | None = None) -> int:
    """Conta os dias úteis forenses no intervalo, excluindo o dia inicial e incluindo o final.

    Útil para saber quantos dias de um prazo já correram.
    """
    return prazos.dias_uteis_entre(
        prazos.parse_data(inicio), prazos.parse_data(fim), _datas_extras(feriados_extras or [])
    )


@mcp.tool
def listar_feriados(ano: int) -> dict[str, str]:
    """Lista os feriados nacionais e dias sem expediente forense de um ano (data -> nome).

    Não inclui o recesso forense (20/12 a 20/01) nem feriados estaduais/municipais.
    """
    return {d.isoformat(): nome for d, nome in prazos.feriados(ano).items()}


@mcp.tool
def validar_numero_cnj(numero: str) -> dict:
    """Valida um número único de processo do CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO) pelo dígito verificador.

    Também informa o ano de ajuizamento, o segmento do Judiciário e o tribunal.
    Use antes de citar ou registrar um número de processo, para pegar erros de digitação.

    Args:
        numero: formatado ou só os 20 dígitos.
    """
    return cnj.validar(numero)


@mcp.tool
def buscar_intimacoes(numero: str, dias: int = 90) -> list[dict]:
    """Busca no DJEN (Diário de Justiça Eletrônico Nacional) as intimações de um processo.

    Fonte principal para prazos: traz o TEXTO de cada intimação, a data de disponibilização,
    os destinatários (com o polo) e os advogados. A lista vem da mais recente para a mais antiga.
    Para calcular o prazo, use a data_disponibilizacao em calcular_prazo com
    data_e_disponibilizacao=True.

    Args:
        numero: número CNJ do processo, formatado ou só os 20 dígitos.
        dias: quantos dias para trás procurar (padrão 90).
    """
    itens = djen.buscar_intimacoes(numero, dias)
    log.info("buscar_intimacoes(%s, %s) -> %d itens", numero, dias, len(itens))
    return itens


@mcp.tool
def consultar_processo(numero: str) -> dict:
    """Consulta classe, órgão julgador, assuntos e movimentações de um processo no DataJud (CNJ).

    Não traz o texto das intimações e pode estar semanas atrasado em relação ao tribunal.
    Use para contexto (fase do processo, o que motivou a intimação) ou quando
    buscar_intimacoes falhar. Movimentações com pode_abrir_prazo=True são candidatas a
    início de prazo, mas o ato exigido precisa ser deduzido e isso deve ser dito na resposta.

    Args:
        numero: número CNJ do processo, formatado ou só os 20 dígitos.
    """
    resultado = datajud.consultar(numero)
    log.info("consultar_processo(%s) -> %d registros", numero, len(resultado["registros"]))
    return resultado


@mcp.resource("prazos://tabela")
def tabela_prazos() -> str:
    """Prazos processuais mais comuns do CPC (em dias úteis) e a base legal."""
    return json.dumps(TABELA_PRAZOS, ensure_ascii=False, indent=2)


@mcp.resource("prazos://instrucoes")
def instrucoes() -> str:
    """Instruções do servidor + tabela de prazos, prontas para usar como prompt de sistema."""
    return f"{INSTRUCOES}\nPrazos usuais:\n{_tabela_texto()}"


@mcp.prompt
def analisar_intimacao(texto: str) -> str:
    """Analisa o texto de uma intimação e calcula o prazo para responder."""
    return (
        "Você é um assistente de controladoria jurídica. Hoje é "
        f"{date.today():%d/%m/%Y}. Analise a intimação abaixo seguindo as regras e responda com: "
        "processo (e tribunal), ato, destinatário, prazo, base legal, vencimento e ressalvas.\n\n"
        f"{instrucoes()}\n\nIntimação:\n{texto}"
    )


@mcp.prompt
def prazos_do_processo(numero: str, dias: str = "90") -> str:
    """Levanta os prazos em aberto de um processo a partir do número CNJ."""
    return (
        "Você é um assistente de controladoria jurídica. Levante os prazos do processo "
        f"{numero} (intimações dos últimos {dias} dias). Hoje é {date.today():%d/%m/%Y}.\n"
        "Responda com um resumo do processo (tribunal, classe, órgão) e uma tabela: data de "
        "disponibilização, destinatário, ato, prazo, base legal, vencimento e situação.\n\n"
        f"{instrucoes()}"
    )


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="127.0.0.1", port=8000)
    else:
        mcp.run()  # stdio
