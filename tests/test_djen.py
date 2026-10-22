from datetime import date

import httpx
import pytest

import djen

NUMERO = "0001234-21.2026.8.04.0001"  # válido, TJAM


def item(data, texto="Intime-se.", ativo=True):
    return {
        "data_disponibilizacao": data,
        "tipoComunicacao": "Intimação",
        "tipoDocumento": "DECISÃO",
        "nomeOrgao": "1ª Vara Cível da Comarca de Manaus",
        "nomeClasse": "PROCEDIMENTO COMUM CÍVEL",
        "texto": texto,
        "link": "",
        "ativo": ativo,
        "destinatarios": [{"nome": "FULANO DE TAL", "polo": "P"}],
        "destinatarioadvogados": [{"advogado": {"nome": "ADVOGADA EXEMPLO", "numero_oab": "1234", "uf_oab": "AM"}}],
    }


def cliente_falso(status=200, itens=(), capturar=None):
    def responder(request):
        if capturar is not None:
            capturar.append(request)
        return httpx.Response(status, json={"status": "success", "count": len(itens), "items": list(itens)})

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_normaliza_e_ordena_do_mais_recente():
    itens = [item("2026-09-01"), item("2026-10-20"), item("2026-10-01", ativo=False)]
    r = djen.buscar_intimacoes(NUMERO, hoje=date(2026, 10, 22), cliente=cliente_falso(itens=itens))
    assert [i["data_disponibilizacao"] for i in r] == ["2026-10-20", "2026-09-01"]
    assert r[0]["destinatarios"] == [{"nome": "FULANO DE TAL", "polo": "passivo"}]
    assert r[0]["advogados"] == ["ADVOGADA EXEMPLO (OAB 1234/AM)"]
    assert r[0]["link"] is None


def test_parametros_da_consulta():
    requisicoes = []
    djen.buscar_intimacoes(NUMERO, dias=30, hoje=date(2026, 10, 22), cliente=cliente_falso(capturar=requisicoes))
    params = requisicoes[0].url.params
    assert params["numeroProcesso"] == "00012342120268040001"
    assert params["dataDisponibilizacaoInicio"] == "2026-09-22"
    assert params["dataDisponibilizacaoFim"] == "2026-10-22"


def test_limpa_html_e_trunca():
    assert djen.limpar_texto("<p>Intime-se&nbsp;a parte.</p><br>Prazo: 15 dias.") == "Intime-se\xa0a parte.\n\nPrazo: 15 dias."
    assert djen.limpar_texto("DECISÃO\r\n\r\nDefiro.") == "DECISÃO\n\nDefiro."
    assert djen.limpar_texto("x" * 5000).endswith("[...texto truncado]")


@pytest.mark.parametrize("status, trecho", [(403, "403"), (429, "Limite"), (500, "HTTP 500")])
def test_erros_da_api(status, trecho):
    with pytest.raises(RuntimeError, match=trecho):
        djen.buscar_intimacoes(NUMERO, cliente=cliente_falso(status=status))


def test_numero_invalido_nem_chama_a_api():
    with pytest.raises(ValueError, match="dígito"):
        djen.buscar_intimacoes("0001234-00.2026.8.04.0001", cliente=cliente_falso(status=500))
