"""Número único de processo do CNJ (Resolução CNJ 65/2008), sem nada de MCP.

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
    N = sequencial, D = dígito verificador, A = ano de ajuizamento,
    J = segmento do Judiciário, TR = tribunal, O = unidade de origem.
O dígito verificador é calculado por módulo 97 (ISO 7064): o número completo,
com DD no fim, deixa resto 1 na divisão por 97.
"""
import re

SEGMENTOS = {
    "1": "Supremo Tribunal Federal",
    "2": "Conselho Nacional de Justiça",
    "3": "Superior Tribunal de Justiça",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

# Código TR da Justiça Estadual e Eleitoral (ordem alfabética das UFs)
UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SE", "SP", "TO",
]

# Tribunais superiores dos ramos especializados usam TR = 00
SUPERIORES = {"5": "TST", "6": "TSE", "7": "STM"}

PADRAO = re.compile(r"^(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})$")


def calcular_digito(sequencial: str, ano: str, segmento: str, tribunal: str, origem: str) -> str:
    """Dígito verificador (2 dígitos) para os demais campos do número."""
    resto = int(f"{sequencial}{ano}{segmento}{tribunal}{origem}00") % 97
    return f"{98 - resto:02d}"


def nome_tribunal(segmento: str, tribunal: str) -> str | None:
    """Nome do tribunal a partir de J e TR, quando dá para saber só pelo número."""
    tr = int(tribunal)
    if segmento == "1":
        return "STF"
    if segmento == "3":
        return "STJ"
    if tr == 0 and segmento in SUPERIORES:
        return SUPERIORES[segmento]
    if segmento == "8" and tribunal == "07":
        return "TJDFT"
    if segmento in ("8", "6") and 1 <= tr <= len(UFS):
        return ("TJ" if segmento == "8" else "TRE-") + UFS[tr - 1]
    if segmento == "4" and 1 <= tr <= 6:
        return f"TRF{tr}"
    if segmento == "5" and 1 <= tr <= 24:
        return f"TRT{tr}"
    if segmento == "9" and tribunal in ("13", "21", "26"):
        return "TJM" + UFS[tr - 1]
    return None


def apenas_digitos(numero: str) -> str:
    """Os 20 dígitos do número, sem máscara (formato usado pelas APIs do CNJ)."""
    return re.sub(r"\D", "", numero)


def validar(numero: str) -> dict:
    """Valida o número CNJ e devolve os campos decompostos.

    Aceita o número formatado ou só os 20 dígitos. Formato errado gera ValueError;
    dígito verificador errado não: o resultado diz `valido: False` e qual seria o dígito certo.
    """
    m = PADRAO.match(numero.strip())
    if not m:
        raise ValueError(
            f"Número CNJ mal formado: '{numero}'. Esperado NNNNNNN-DD.AAAA.J.TR.OOOO (20 dígitos)."
        )
    sequencial, digito, ano, segmento, tribunal, origem = m.groups()
    if segmento == "0":
        raise ValueError(f"Segmento do Judiciário inválido: '{segmento}' (deve ser de 1 a 9).")

    esperado = calcular_digito(sequencial, ano, segmento, tribunal, origem)
    return {
        "numero_formatado": f"{sequencial}-{digito}.{ano}.{segmento}.{tribunal}.{origem}",
        "valido": digito == esperado,
        "digito_informado": digito,
        "digito_esperado": esperado,
        "ano_ajuizamento": int(ano),
        "segmento": SEGMENTOS[segmento],
        "tribunal": nome_tribunal(segmento, tribunal),
        "codigo_tribunal": tribunal,
        "unidade_origem": origem,
    }
