"""Intimações publicadas no DJEN (Diário de Justiça Eletrônico Nacional), sem nada de MCP.

API pública do Comunica PJe (CNJ): não precisa de chave, mas tem limite de requisições
(~20 por janela) e pode bloquear acessos de fora do Brasil (HTTP 403 do CloudFront).
"""
import html
import re
from datetime import date, timedelta

import httpx

import cnj

URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
LIMITE_TEXTO = 4000  # caracteres por intimação, para não estourar o contexto do modelo


def limpar_texto(texto: str) -> str:
    """Tira tags HTML e espaços repetidos; trunca textos muito longos."""
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"<br\s*/?>|</p>", "\n", texto, flags=re.IGNORECASE)
    texto = html.unescape(re.sub(r"<[^>]+>", "", texto))
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n\n", texto).strip()
    if len(texto) > LIMITE_TEXTO:
        texto = texto[:LIMITE_TEXTO] + " [...texto truncado]"
    return texto


def normalizar(item: dict) -> dict:
    """Converte um item cru da API no formato enxuto que vai para o modelo."""
    advogados = []
    for a in item.get("destinatarioadvogados") or []:
        adv = a.get("advogado") or {}
        advogados.append(f"{adv.get('nome', '?')} (OAB {adv.get('numero_oab', '?')}/{adv.get('uf_oab', '?')})")
    polos = {"A": "ativo", "P": "passivo"}
    return {
        "data_disponibilizacao": item.get("data_disponibilizacao"),
        "tipo_comunicacao": item.get("tipoComunicacao"),
        "tipo_documento": item.get("tipoDocumento"),
        "orgao": item.get("nomeOrgao"),
        "classe": item.get("nomeClasse"),
        "destinatarios": [
            {"nome": d.get("nome"), "polo": polos.get(d.get("polo"), d.get("polo"))}
            for d in item.get("destinatarios") or []
        ],
        "advogados": advogados,
        "texto": limpar_texto(item.get("texto", "")),
        "link": item.get("link") or None,
    }


def buscar_intimacoes(
    numero: str, dias: int = 90, hoje: date | None = None, cliente: httpx.Client | None = None
) -> list[dict]:
    """Comunicações do processo disponibilizadas nos últimos `dias`, da mais recente para a mais antiga."""
    if not cnj.validar(numero)["valido"]:
        raise ValueError(f"Número CNJ com dígito verificador inválido: '{numero}'. Confira com validar_numero_cnj.")
    if dias <= 0:
        raise ValueError(f"O período em dias precisa ser positivo (recebi {dias}).")
    hoje = hoje or date.today()
    params = {
        "numeroProcesso": cnj.apenas_digitos(numero),
        "dataDisponibilizacaoInicio": (hoje - timedelta(days=dias)).isoformat(),
        "dataDisponibilizacaoFim": hoje.isoformat(),
        "itensPorPagina": 100,
        "pagina": 1,
    }
    cliente = cliente or httpx.Client(timeout=30)
    try:
        resposta = cliente.get(URL, params=params)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Falha de conexão com o DJEN: {e}") from e

    if resposta.status_code == 403:
        raise RuntimeError(
            "O DJEN recusou o acesso (403). A API costuma bloquear redes fora do Brasil "
            "(VPN/proxy). Use consultar_processo (DataJud) como alternativa."
        )
    if resposta.status_code == 429:
        raise RuntimeError("Limite de requisições do DJEN atingido. Aguarde um minuto e tente de novo.")
    if resposta.is_error:
        raise RuntimeError(f"O DJEN respondeu com erro HTTP {resposta.status_code}.")

    itens = [normalizar(i) for i in resposta.json().get("items", []) if i.get("ativo", True)]
    return sorted(itens, key=lambda i: i["data_disponibilizacao"] or "", reverse=True)
