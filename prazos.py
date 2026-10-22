"""Lógica de prazos processuais do CPC, sem nada de MCP (testável direto com pytest).

Regras implementadas:
- Contagem só em dias úteis (art. 219), excluindo o dia do começo e incluindo o do vencimento (art. 224).
- Feriados nacionais fixos + móveis (Carnaval, Sexta-feira Santa, Corpus Christi, a partir da Páscoa).
- Recesso forense de 20/12 a 20/01: prazos suspensos (art. 220).
- Publicação no DJe = primeiro dia útil após a disponibilização (Lei 11.419/2006, art. 4º, §3º).
- Prazo em dobro (arts. 183, 186 e 229) é decidido por quem chama; aqui só multiplicamos por 2.
Feriados estaduais/municipais variam por comarca: entram como `feriados_extras`.
"""
from datetime import date, datetime, timedelta

FERIADOS_FIXOS = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 25): "Natal",
}

NOMES_DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def parse_data(texto: str) -> date:
    """Aceita 'AAAA-MM-DD' ou 'DD/MM/AAAA'."""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            pass
    raise ValueError(f"Data inválida: '{texto}'. Use AAAA-MM-DD ou DD/MM/AAAA.")


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados(ano: int) -> dict[date, str]:
    """Feriados nacionais e dias sem expediente forense do ano (data -> nome)."""
    resultado = {date(ano, m, d): nome for (m, d), nome in FERIADOS_FIXOS.items()}
    p = pascoa(ano)
    resultado[p - timedelta(days=48)] = "Carnaval (segunda-feira)"
    resultado[p - timedelta(days=47)] = "Carnaval (terça-feira)"
    resultado[p - timedelta(days=2)] = "Sexta-feira Santa"
    resultado[p + timedelta(days=60)] = "Corpus Christi"
    return dict(sorted(resultado.items()))


def em_recesso(d: date) -> bool:
    """Recesso forense: 20/12 a 20/01, inclusive (art. 220 do CPC)."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


def motivo_nao_util(d: date, extras: set[date] = frozenset()) -> str | None:
    """Por que `d` não conta no prazo, ou None se for dia útil."""
    if d.weekday() >= 5:
        return NOMES_DIAS[d.weekday()]
    nome = feriados(d.year).get(d)
    if nome:
        return f"feriado: {nome}"
    if d in extras:
        return "feriado local (informado)"
    if em_recesso(d):
        return "recesso forense (art. 220 CPC)"
    return None


def proximo_dia_util(d: date, extras: set[date] = frozenset()) -> date:
    """Primeiro dia útil estritamente depois de `d`."""
    d += timedelta(days=1)
    while motivo_nao_util(d, extras):
        d += timedelta(days=1)
    return d


def calcular_prazo(
    data_inicio: date,
    dias: int,
    em_dobro: bool = False,
    data_e_disponibilizacao: bool = False,
    feriados_extras: list[date] = (),
) -> dict:
    """Conta `dias` úteis a partir de `data_inicio` (intimação ou disponibilização no DJe).

    Como só dias úteis são contados, o vencimento já cai sempre num dia útil
    (a prorrogação do art. 224, §1º, sai de graça).
    """
    if dias <= 0:
        raise ValueError(f"O prazo precisa ser positivo (recebi {dias}).")
    extras = set(feriados_extras)
    total = dias * 2 if em_dobro else dias

    passos = []
    termo = data_inicio
    if data_e_disponibilizacao:
        termo = proximo_dia_util(data_inicio, extras)
        passos.append(
            f"Disponibilizado em {data_inicio:%d/%m/%Y}; considera-se publicado em {termo:%d/%m/%Y}."
        )
    passos.append(f"Dia do começo ({termo:%d/%m/%Y}) excluído; contagem de {total} dias úteis.")

    pulados = []
    contados = 0
    d = termo
    while contados < total:
        d += timedelta(days=1)
        motivo = motivo_nao_util(d, extras)
        if motivo:
            pulados.append({"data": d.isoformat(), "motivo": motivo})
        else:
            contados += 1

    passos.append(f"Vencimento: {d:%d/%m/%Y} ({NOMES_DIAS[d.weekday()]}).")
    return {
        "vencimento": d.isoformat(),
        "dias_uteis_contados": total,
        "dias_pulados": pulados,
        "passos": passos,
    }


def dias_uteis_entre(inicio: date, fim: date, feriados_extras: list[date] = ()) -> int:
    """Quantos dias úteis há no intervalo (inicio, fim] — exclui o início, inclui o fim."""
    if fim < inicio:
        raise ValueError("A data final precisa ser igual ou posterior à inicial.")
    extras = set(feriados_extras)
    total = 0
    d = inicio
    while d < fim:
        d += timedelta(days=1)
        if not motivo_nao_util(d, extras):
            total += 1
    return total
