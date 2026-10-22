"""Metadados e movimentações de processos na API pública do DataJud (CNJ), sem nada de MCP.

Não traz o texto das intimações e costuma ter semanas de atraso em relação ao tribunal:
serve de contexto e de alternativa quando o DJEN não está acessível.
A chave é pública e o CNJ pode trocá-la: a vigente fica em
https://datajud-wiki.cnj.jus.br/api-publica/acesso (sobrescreva com DATAJUD_API_KEY no keys.env).
"""
import os

import httpx

import cnj

URL = "https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"
CHAVE_PUBLICA = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
LIMITE_MOVIMENTOS = 30

# Movimentações que normalmente dão início a um prazo para as partes
PALAVRAS_PRAZO = ("disponibilização", "publicação", "intimação", "citação")


def alias(tribunal: str | None) -> str:
    """Sufixo do endpoint do DataJud para a sigla do tribunal (ex.: TJAM -> tjam)."""
    if not tribunal or tribunal == "STF":
        raise ValueError(f"O DataJud não tem endpoint para este tribunal ({tribunal or 'desconhecido'}).")
    if tribunal == "TRE-DF":
        return "tre-dft"
    return tribunal.lower()


def normalizar_movimento(m: dict) -> dict:
    complementos = [
        f"{c.get('descricao', '').replace('_', ' ')}: {c.get('nome', '')}".strip(": ")
        for c in m.get("complementosTabelados") or []
    ]
    nome = m.get("nome", "")
    return {
        "data": (m.get("dataHora") or "")[:10],
        "codigo": m.get("codigo"),
        "nome": nome,
        "complementos": complementos,
        "pode_abrir_prazo": any(p in nome.lower() for p in PALAVRAS_PRAZO),
    }


def normalizar(fonte: dict) -> dict:
    """Converte um `_source` cru do DataJud no formato enxuto que vai para o modelo."""
    movimentos = sorted(
        (normalizar_movimento(m) for m in fonte.get("movimentos") or []),
        key=lambda m: m["data"],
        reverse=True,
    )
    return {
        "grau": fonte.get("grau"),
        "classe": (fonte.get("classe") or {}).get("nome"),
        "orgao_julgador": (fonte.get("orgaoJulgador") or {}).get("nome"),
        "assuntos": [a.get("nome") for a in fonte.get("assuntos") or [] if isinstance(a, dict)],
        "data_ajuizamento": (fonte.get("dataAjuizamento") or "")[:10],
        "ultima_atualizacao_datajud": (fonte.get("dataHoraUltimaAtualizacao") or "")[:10],
        "movimentos": movimentos[:LIMITE_MOVIMENTOS],
    }


def consultar(numero: str, cliente: httpx.Client | None = None) -> dict:
    """Dados do processo em cada grau em que aparece no DataJud."""
    info = cnj.validar(numero)
    if not info["valido"]:
        raise ValueError(f"Número CNJ com dígito verificador inválido: '{numero}'. Confira com validar_numero_cnj.")
    url = URL.format(alias=alias(info["tribunal"]))
    chave = os.getenv("DATAJUD_API_KEY", CHAVE_PUBLICA)
    corpo = {"query": {"match": {"numeroProcesso": cnj.apenas_digitos(numero)}}}

    cliente = cliente or httpx.Client(timeout=60)
    try:
        resposta = cliente.post(url, json=corpo, headers={"Authorization": f"APIKey {chave}"})
    except httpx.HTTPError as e:
        raise RuntimeError(f"Falha de conexão com o DataJud: {e}") from e
    if resposta.status_code in (401, 403):
        raise RuntimeError(
            "O DataJud recusou a chave. Ela pode ter mudado: pegue a vigente em "
            "https://datajud-wiki.cnj.jus.br/api-publica/acesso e defina DATAJUD_API_KEY no keys.env."
        )
    if resposta.status_code == 429:
        raise RuntimeError("Limite de requisições do DataJud atingido. Aguarde um minuto e tente de novo.")
    if resposta.is_error:
        raise RuntimeError(f"O DataJud respondeu com erro HTTP {resposta.status_code}.")

    hits = resposta.json().get("hits", {}).get("hits", [])
    if not hits:
        raise ValueError(
            f"Processo {info['numero_formatado']} não encontrado no DataJud ({info['tribunal']}). "
            "Pode ser sigiloso, muito recente ou ainda não enviado pelo tribunal."
        )
    return {
        "numero": info["numero_formatado"],
        "tribunal": info["tribunal"],
        "registros": [normalizar(h["_source"]) for h in hits],
    }
