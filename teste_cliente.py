"""Testa o servidor de prazos SEM LLM, usando o cliente do FastMCP."""
import asyncio

from fastmcp import Client

ARQUIVO = "servidor_prazos.py"


async def main():
    async with Client(ARQUIVO) as client:
        print("TOOLS:", [t.name for t in await client.list_tools()])
        print("RESOURCES:", [str(r.uri) for r in await client.list_resources()])
        print("PROMPTS:", [p.name for p in await client.list_prompts()])

        r = await client.call_tool("calcular_prazo", {"data_inicio": "2026-12-18", "dias": 15})
        print("calcular_prazo ->", r.data["vencimento"], r.data["passos"])

        r = await client.call_tool("eh_dia_util", {"data": "21/04/2026"})
        print("eh_dia_util ->", r.data)

        r = await client.call_tool("dias_uteis_entre", {"inicio": "2026-03-06", "fim": "2026-03-27"})
        print("dias_uteis_entre ->", r.data)

        r = await client.call_tool("listar_feriados", {"ano": 2027})
        print("listar_feriados ->", r.data)

        r = await client.call_tool("validar_numero_cnj", {"numero": "0001234-00.2026.8.04.0001"})
        print("validar_numero_cnj ->", r.data)

        print("tabela ->", (await client.read_resource("prazos://tabela"))[0].text[:120], "...")

        # Erro de propósito: é esta mensagem que o modelo veria
        r = await client.call_tool("calcular_prazo", {"data_inicio": "31/02/2026", "dias": 5}, raise_on_error=False)
        print("erro ->", r.content[0].text)


asyncio.run(main())
