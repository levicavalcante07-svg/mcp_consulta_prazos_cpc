import pytest

from cnj import calcular_digito, validar


def numero_valido(seq="0001234", ano="2026", j="8", tr="04", origem="0001"):
    dv = calcular_digito(seq, ano, j, tr, origem)
    return f"{seq}-{dv}.{ano}.{j}.{tr}.{origem}"


def test_digito_satisfaz_modulo_97():
    # Forma canônica da Resolução 65: N A J TR O D concatenados, resto 1
    numero = numero_valido()
    seq, resto = numero.split("-")
    dv, ano, j, tr, origem = resto.split(".")
    assert int(seq + ano + j + tr + origem + dv) % 97 == 1


def test_numero_valido_tjam():
    r = validar(numero_valido())
    assert r["valido"] is True
    assert r["segmento"] == "Justiça Estadual"
    assert r["tribunal"] == "TJAM"
    assert r["ano_ajuizamento"] == 2026


def test_aceita_so_digitos():
    numero = numero_valido()
    assert validar(numero.replace("-", "").replace(".", ""))["valido"] is True


def test_digito_errado():
    numero = numero_valido()
    dv = numero[8:10]
    errado = f"{(int(dv) + 1) % 100:02d}"
    r = validar(numero[:8] + errado + numero[10:])
    assert r["valido"] is False
    assert r["digito_esperado"] == dv


@pytest.mark.parametrize(
    "j, tr, tribunal",
    [("4", "01", "TRF1"), ("5", "11", "TRT11"), ("6", "26", "TRE-SP"), ("8", "26", "TJSP"), ("8", "07", "TJDFT"),
     ("3", "00", "STJ"), ("5", "00", "TST"), ("6", "00", "TSE"), ("9", "01", None)],
)
def test_nome_tribunal(j, tr, tribunal):
    assert validar(numero_valido(j=j, tr=tr))["tribunal"] == tribunal


@pytest.mark.parametrize("numero", ["123", "0001234-00.2026.8.04", "abcdefg-12.2026.8.04.0001", "0001234-00.2026.0.04.0001"])
def test_mal_formado(numero):
    with pytest.raises(ValueError):
        validar(numero)
