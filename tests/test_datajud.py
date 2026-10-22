import httpx
import pytest

import datajud

NUMERO = "0001234-21.2026.8.04.0001"  # válido, TJAM

FONTE = {
    "grau": "G1",
    "classe": {"nome": "Procedimento Comum Cível"},
    "orgaoJulgador": {"nome": "1ª VARA CÍVEL"},
    "assuntos": [{"nome": "Indenização por Dano Moral"}],
    "dataAjuizamento": "2026-06-03T11:52:48.000Z",
    "dataHoraUltimaAtualizacao": "2026-09-13T23:25:45.576Z",
    "movimentos": [
        {"codigo": 26, "nome": "Distribuição", "dataHora": "2026-06-03T11:52:50.000Z",
         "complementosTabelados": [{"nome": "sorteio", "descricao": "tipo_de_distribuicao_redistribuicao"}]},
        {"codigo": 1061, "nome": "Disponibilização no Diário da Justiça Eletrônico", "dataHora": "2026-08-25T15:10:07.000Z"},
        {"codigo": 11010, "nome": "Mero expediente", "dataHora": "2026-08-21T10:56:31.000Z"},
    ],
}


def cliente_falso(status=200, hits=(FONTE,), capturar=None):
    def responder(request):
        if capturar is not None:
            capturar.append(request)
        return httpx.Response(status, json={"hits": {"hits": [{"_source": h} for h in hits]}})

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_consulta_normaliza():
    requisicoes = []
    r = datajud.consultar(NUMERO, cliente=cliente_falso(capturar=requisicoes))
    assert str(requisicoes[0].url).endswith("/api_publica_tjam/_search")
    assert requisicoes[0].headers["Authorization"].startswith("APIKey ")
    assert r["tribunal"] == "TJAM"
    reg = r["registros"][0]
    assert reg["classe"] == "Procedimento Comum Cível"
    assert reg["ultima_atualizacao_datajud"] == "2026-09-13"
    movs = reg["movimentos"]
    assert [m["data"] for m in movs] == ["2026-08-25", "2026-08-21", "2026-06-03"]
    assert movs[0]["pode_abrir_prazo"] is True
    assert movs[1]["pode_abrir_prazo"] is False
    assert movs[2]["complementos"] == ["tipo de distribuicao redistribuicao: sorteio"]


def test_chave_do_ambiente(monkeypatch):
    monkeypatch.setenv("DATAJUD_API_KEY", "nova-chave")
    requisicoes = []
    datajud.consultar(NUMERO, cliente=cliente_falso(capturar=requisicoes))
    assert requisicoes[0].headers["Authorization"] == "APIKey nova-chave"


def test_nao_encontrado():
    with pytest.raises(ValueError, match="não encontrado"):
        datajud.consultar(NUMERO, cliente=cliente_falso(hits=()))


@pytest.mark.parametrize("status, trecho", [(401, "DATAJUD_API_KEY"), (429, "Limite"), (500, "HTTP 500")])
def test_erros_da_api(status, trecho):
    with pytest.raises(RuntimeError, match=trecho):
        datajud.consultar(NUMERO, cliente=cliente_falso(status=status))


@pytest.mark.parametrize("tribunal, esperado", [("TJAM", "tjam"), ("TRE-DF", "tre-dft"), ("TJDFT", "tjdft"), ("TRT11", "trt11")])
def test_alias(tribunal, esperado):
    assert datajud.alias(tribunal) == esperado


@pytest.mark.parametrize("tribunal", [None, "STF"])
def test_alias_sem_endpoint(tribunal):
    with pytest.raises(ValueError):
        datajud.alias(tribunal)
