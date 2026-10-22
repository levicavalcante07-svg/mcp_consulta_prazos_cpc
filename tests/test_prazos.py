from datetime import date

import pytest

from prazos import calcular_prazo, dias_uteis_entre, feriados, motivo_nao_util, parse_data, pascoa


def venc(*args, **kwargs):
    return calcular_prazo(*args, **kwargs)["vencimento"]


@pytest.mark.parametrize(
    "ano, esperado",
    [(2024, date(2024, 3, 31)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))],
)
def test_pascoa(ano, esperado):
    assert pascoa(ano) == esperado


def test_feriados_moveis_2026():
    f = feriados(2026)
    assert f[date(2026, 2, 16)].startswith("Carnaval")
    assert f[date(2026, 2, 17)].startswith("Carnaval")
    assert f[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert f[date(2026, 6, 4)] == "Corpus Christi"


def test_intimacao_sexta_sem_feriados():
    assert venc(date(2026, 3, 6), 15) == "2026-03-27"


def test_atravessa_carnaval():
    assert venc(date(2026, 2, 13), 15) == "2026-03-10"


def test_atravessa_recesso_e_carnaval():
    # 19/12 é sábado; 20/12 a 20/01 recesso; Carnaval 2027 em 08 e 09/02
    assert venc(date(2026, 12, 18), 15) == "2027-02-12"


def test_prazo_em_dobro():
    # 30 dias úteis pulando a Sexta-feira Santa (03/04)
    assert venc(date(2026, 3, 6), 15, em_dobro=True) == "2026-04-20"


def test_feriado_no_meio_e_pulado():
    r = calcular_prazo(date(2026, 4, 15), 5)
    assert r["vencimento"] == "2026-04-23"
    assert {"data": "2026-04-21", "motivo": "feriado: Tiradentes"} in r["dias_pulados"]


def test_disponibilizacao_dje():
    # Disponibilizado qui 02/04; sexta é feriado -> publicado seg 06/04; conta de 07/04
    assert venc(date(2026, 4, 2), 5, data_e_disponibilizacao=True) == "2026-04-13"


def test_feriado_local():
    assert venc(date(2026, 3, 6), 1) == "2026-03-09"
    assert venc(date(2026, 3, 6), 1, feriados_extras=[date(2026, 3, 9)]) == "2026-03-10"


def test_recesso_nao_e_dia_util():
    assert motivo_nao_util(date(2027, 1, 7)).startswith("recesso")
    assert motivo_nao_util(date(2027, 1, 21)) is None


def test_dias_uteis_entre():
    assert dias_uteis_entre(date(2026, 3, 6), date(2026, 3, 27)) == 15


def test_erros():
    with pytest.raises(ValueError):
        calcular_prazo(date(2026, 3, 6), 0)
    with pytest.raises(ValueError):
        parse_data("31/02/2026")


def test_parse_data_formatos():
    assert parse_data("2026-04-21") == parse_data("21/04/2026") == date(2026, 4, 21)
