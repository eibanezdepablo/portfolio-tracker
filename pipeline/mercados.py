"""
Datos de mercado para el mapa de calor y el análisis de acciones. Escribe en data/mercado/
(se guarda en la rama `mercado`, sin historial, para que el repositorio no crezca):

  mapa.json           componentes de los índices: nombre, sector, industria, capitalización y rentabilidades
  fundamentales.json  métricas de cada acción (valoración, rentabilidad, deuda, analistas)
  acciones/<T>.json   detalle: precio semanal a 5 años, cuentas anuales, estimaciones y recomendaciones

Las fichas (info de Yahoo) se refrescan si tienen más de CADUCA días, y el detalle por turnos
(LOTE por ejecución, las más antiguas primero), para no saturar Yahoo. Si algo falla se conserva
lo que ya había.
"""
from __future__ import annotations
import datetime as dt
import io
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "data" / "mercado"
UA = {"User-Agent": "Mozilla/5.0 (portfolio-tracker)"}
LOTE = int(os.environ.get("MERCADO_LOTE", "110"))        # detalles por ejecución
MAX_INFO = int(os.environ.get("MERCADO_MAX_INFO", "700"))  # fichas por ejecución
CADUCA = 6

INDICES = {
    "sp500": {"nombre": "S&P 500", "moneda": "USD"},
    "ndx": {"nombre": "Nasdaq 100", "moneda": "USD"},
    "sx5e": {"nombre": "Euro Stoxx 50", "moneda": "EUR"},
    "dax": {"nombre": "DAX 40", "moneda": "EUR"},
    "ibex": {"nombre": "IBEX 35", "moneda": "EUR"},
}


# ───────────────────────── utilidades ─────────────────────────
def num(x, nd=6):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return float(f"{x:.{nd}g}")


def leer(ruta: Path, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def hoy() -> str:
    return dt.date.today().isoformat()


# ───────────────────────── componentes ─────────────────────────
def _wiki(url: str, col_t: str, col_n: str, col_s: str | None, sufijo_us: bool = False):
    html = requests.get(url, headers=UA, timeout=30).text
    for df in pd.read_html(io.StringIO(html)):
        df.columns = [str(c[-1] if isinstance(c, tuple) else c).strip() for c in df.columns]
        if col_t in df.columns and col_n in df.columns and len(df) >= 30:
            out = []
            for _, r in df.iterrows():
                t = str(r[col_t]).strip().split()[0]
                if sufijo_us:
                    t = t.replace(".", "-")
                out.append({"t": t, "n": str(r[col_n]).strip(), "s": str(r[col_s]).strip() if col_s else None})
            return out
    raise ValueError(f"sin tabla de componentes en {url}")


def _nasdaq100():
    r = requests.get("https://api.nasdaq.com/api/quote/list-type/nasdaq100",
                     headers={**UA, "Accept": "application/json"}, timeout=30)
    filas = r.json()["data"]["data"]["rows"]
    limpia = lambda n: re.sub(r"\s+(Class [A-C] )?(Common Stock|Ordinary Shares|American Depositary Shares).*$", "", n).strip()
    return [{"t": f["symbol"].replace(".", "-").replace("/", "-"), "n": limpia(f["companyName"]), "s": None} for f in filas]


FUENTES_COMPONENTES = {
    "sp500": lambda: _wiki("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol", "Security", "GICS Sector", True),
    "ndx": _nasdaq100,
    "sx5e": lambda: _wiki("https://en.wikipedia.org/wiki/EURO_STOXX_50", "Ticker", "Name", "Sector"),
    "dax": lambda: _wiki("https://en.wikipedia.org/wiki/DAX", "Ticker", "Company", "Prime Standard Sector"),
    "ibex": lambda: _wiki("https://en.wikipedia.org/wiki/IBEX_35", "Ticker", "Company", "Sector"),
}


def componentes(previo: dict) -> tuple[dict, dict, list]:
    """Devuelve {índice: [tickers]}, {ticker: {n, s}} y avisos. Si una lista falla, usa la anterior."""
    listas, base, avisos = {}, {}, []
    for k, f in FUENTES_COMPONENTES.items():
        try:
            filas = f()
            if len(filas) < 30:
                raise ValueError(f"solo {len(filas)} componentes")
        except Exception as e:
            ant = (previo.get("indices") or {}).get(k, {}).get("t")
            avisos.append(f"{k}: {e}" + (" (se usa la lista anterior)" if ant else ""))
            filas = [{"t": t, "n": (previo.get("s") or {}).get(t, {}).get("n", t), "s": None} for t in (ant or [])]
        listas[k] = [r["t"] for r in filas]
        for r in filas:
            b = base.setdefault(r["t"], {"n": r["n"], "s": r["s"]})
            b["s"] = b["s"] or r["s"]
    return listas, base, avisos


# ───────────────────────── precios ─────────────────────────
def _cierres(tickers: list[str], **kw) -> pd.DataFrame:
    partes = []
    for i in range(0, len(tickers), 200):
        df = yf.download(tickers[i:i + 200], auto_adjust=True, progress=False, threads=True, group_by="column", **kw)
        if df is None or df.empty:
            continue
        c = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(columns={"Close": tickers[i]})
        partes.append(c)
    if not partes:
        return pd.DataFrame()
    c = pd.concat(partes, axis=1)
    c.index = pd.to_datetime(c.index).tz_localize(None) if getattr(c.index, "tz", None) else pd.to_datetime(c.index)
    return c


def rentabilidades(s: pd.Series) -> tuple[float | None, list]:
    s = s.dropna()
    s = s[s > 0]
    if len(s) < 2:
        return None, [None] * 6
    ult, f = float(s.iloc[-1]), s.index[-1]

    def desde(fecha):
        a = s[s.index <= fecha]
        return num(ult / float(a.iloc[-1]) - 1, 5) if len(a) else None

    return num(ult), [
        num(ult / float(s.iloc[-2]) - 1, 5),
        desde(f - pd.Timedelta(days=7)),
        desde(f - pd.DateOffset(months=1)),
        desde(f - pd.DateOffset(months=3)),
        desde(pd.Timestamp(f.year - 1, 12, 31)),
        desde(f - pd.DateOffset(years=1)),
    ]


# ───────────────────────── fichas (info) ─────────────────────────
CAMPOS_INFO = {
    "n": "shortName", "nl": "longName", "sec": "sector", "ind": "industry", "pais": "country", "ccy": "currency",
    "fccy": "financialCurrency", "cap": "marketCap", "acc": "sharesOutstanding", "pref": "currentPrice",
    "per": "trailingPE", "perf": "forwardPE", "pvc": "priceToBook", "pv": "priceToSalesTrailing12Months",
    "evebitda": "enterpriseToEbitda", "ev": "enterpriseValue", "ebitda": "ebitda", "deuda": "totalDebt",
    "caja": "totalCash", "ingresos": "totalRevenue", "fcf": "freeCashflow", "mb": "grossMargins",
    "mo": "operatingMargins", "mn": "profitMargins", "roe": "returnOnEquity", "roa": "returnOnAssets",
    "cing": "revenueGrowth", "cben": "earningsGrowth", "liq": "currentRatio", "acida": "quickRatio",
    "dpat": "debtToEquity", "divt": "dividendRate", "payout": "payoutRatio", "beta": "beta",
    "max52": "fiftyTwoWeekHigh", "min52": "fiftyTwoWeekLow", "objm": "targetMeanPrice", "obja": "targetHighPrice",
    "objb": "targetLowPrice", "rec": "recommendationMean", "reck": "recommendationKey",
    "nan": "numberOfAnalystOpinions", "peg": "trailingPegRatio", "bpa": "trailingEps", "bpaf": "forwardEps",
}
TEXTO = {"n", "nl", "sec", "ind", "pais", "ccy", "fccy", "reck"}


def ficha(t: str) -> dict:
    info = yf.Ticker(t).info or {}
    if not info.get("quoteType"):
        raise ValueError("sin datos")
    f = {}
    for k, campo in CAMPOS_INFO.items():
        v = info.get(campo)
        f[k] = (str(v) if v not in (None, "") else None) if k in TEXTO else num(v)
    if f["pref"] is None:
        f["pref"] = num(info.get("regularMarketPrice") or info.get("previousClose"))
    f["upd"] = hoy()
    return f


# ───────────────────────── detalle ─────────────────────────
def _filas(df: pd.DataFrame, nombres: dict[str, list[str]]) -> dict:
    if df is None or df.empty:
        return {}
    cols = sorted(df.columns)[-4:]
    out = {"y": [str(pd.Timestamp(c).year) for c in cols]}
    for k, alias in nombres.items():
        fila = next((a for a in alias if a in df.index), None)
        out[k] = [num(df.at[fila, c]) for c in cols] if fila else [None] * len(cols)
    return out


def _estimacion(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    out = {}
    for per in ("0y", "+1y"):
        if per in df.index:
            r = df.loc[per]
            out[per] = {"m": num(r.get("avg")), "b": num(r.get("low")), "a": num(r.get("high")),
                        "n": num(r.get("numberOfAnalysts")), "c": num(r.get("growth")),
                        "ant": num(r.get("yearAgoEps", r.get("yearAgoRevenue")))}
    return out


def detalle(t: str) -> dict:
    tk = yf.Ticker(t)
    d = {"upd": hoy()}
    try:
        info = tk.info or {}
        d["resumen"] = (info.get("longBusinessSummary") or "")[:1400] or None
        d["web"] = info.get("website")
        d["empleados"] = num(info.get("fullTimeEmployees"))
    except Exception:
        pass
    for clave, fn in {
        "pyg": lambda: _filas(tk.income_stmt, {"ingresos": ["Total Revenue"], "ebitda": ["EBITDA", "Normalized EBITDA"],
                                               "ebit": ["Operating Income", "EBIT"], "beneficio": ["Net Income", "Net Income Common Stockholders"],
                                               "bpa": ["Diluted EPS", "Basic EPS"]}),
        "caja": lambda: _filas(tk.cashflow, {"fcf": ["Free Cash Flow"], "fco": ["Operating Cash Flow"], "capex": ["Capital Expenditure"]}),
        "balance": lambda: _filas(tk.balance_sheet, {"deuda": ["Total Debt"], "caja": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
                                                     "patrimonio": ["Stockholders Equity", "Common Stock Equity"]}),
        "est_bpa": lambda: _estimacion(tk.earnings_estimate),
        "est_ing": lambda: _estimacion(tk.revenue_estimate),
        "recs": lambda: [{"p": str(r.get("period")), "sb": num(r.get("strongBuy")), "b": num(r.get("buy")), "h": num(r.get("hold")),
                          "s": num(r.get("sell")), "ss": num(r.get("strongSell"))} for _, r in tk.recommendations.iterrows()][:4],
        "obj": lambda: {k: num(v) for k, v in (tk.analyst_price_targets or {}).items()},
    }.items():
        try:
            d[clave] = fn()
        except Exception:
            d[clave] = None
    return d


# ───────────────────────── principal ─────────────────────────
def main() -> int:
    t0 = time.time()
    previo_mapa = leer(OUT / "mapa.json", {})
    fund = leer(OUT / "fundamentales.json", {}).get("s", {})
    avisos = []

    listas, base, av = componentes(previo_mapa)
    avisos += av
    tickers = sorted(base)
    print(f"{len(tickers)} acciones en {len(listas)} índices")

    # Fichas caducadas o que faltan (las más antiguas primero)
    lim = (dt.date.today() - dt.timedelta(days=CADUCA)).isoformat()
    pend = sorted((t for t in tickers if fund.get(t, {}).get("upd", "") < lim), key=lambda t: fund.get(t, {}).get("upd", ""))
    hechas, fallos = 0, []
    for t in pend[:MAX_INFO]:
        try:
            fund[t] = ficha(t)
            hechas += 1
        except Exception as e:
            fallos.append(t)
            if "Rate" in type(e).__name__ or "Too Many" in str(e):
                avisos.append("Yahoo limita las peticiones: se sigue en la próxima ejecución")
                break
        time.sleep(0.15)
    print(f"fichas: {hechas} nuevas, {len(fallos)} fallos, {time.time() - t0:.0f}s")

    # Precios diarios (rentabilidades) y semanales (gráfico a 5 años)
    diario = _cierres(tickers, period="13mo", interval="1d")
    semanal = _cierres(tickers, period="5y", interval="1wk")
    print(f"precios: {diario.shape} diarios, {semanal.shape} semanales, {time.time() - t0:.0f}s")

    mapa, ultimo = {}, None
    for t in tickers:
        f = fund.get(t, {})
        p, r = rentabilidades(diario[t]) if t in diario else (None, [None] * 6)
        if p is not None:
            ultimo = max(ultimo or "", str(diario[t].dropna().index[-1].date()))
        cap = (f.get("acc") or 0) * p if p and f.get("acc") else f.get("cap")
        mapa[t] = {"n": f.get("n") or base[t]["n"], "sec": f.get("sec") or base[t]["s"], "ind": f.get("ind"),
                   "cap": num(cap, 4), "p": p, "ccy": f.get("ccy"), "r": r}
        if f and p and f.get("pref"):          # ratios de precio al último cierre
            k = p / f["pref"]
            for c in ("per", "perf", "pvc", "pv"):
                if f.get(c) is not None:
                    f[c + "_h"] = num(f[c] * k, 4)
            f["p"] = p
            f["capn"] = num(cap, 4)
            if f.get("ev") and f.get("cap") and f.get("evebitda"):
                ev_n = f["ev"] - f["cap"] + (cap or f["cap"])
                f["evebitda_h"] = num(f["evebitda"] * ev_n / f["ev"], 4)

    escribir(OUT / "mapa.json", {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                                 "asof": ultimo, "indices": {k: {**INDICES[k], "t": v} for k, v in listas.items()},
                                 "s": mapa})
    escribir(OUT / "fundamentales.json", {"generated": hoy(), "s": {t: fund[t] for t in tickers if t in fund}})

    # Detalle por turnos y gráfico semanal para todas
    carpeta = OUT / "acciones"
    previos = {t: leer(carpeta / f"{t}.json", {}) for t in tickers}
    turno = sorted(tickers, key=lambda t: (previos[t].get("upd") or ""))[:LOTE]
    hechos = 0
    for t in tickers:
        d = previos[t]
        if t in turno and time.time() - t0 < 25 * 60:
            try:
                d = {**d, **detalle(t)}
                hechos += 1
            except Exception as e:
                print(f"detalle {t}: {e}")
            time.sleep(0.1)
        if t in semanal:
            s = semanal[t].dropna()
            d["hist"] = {"d": [x.date().isoformat() for x in s.index], "p": [num(x, 5) for x in s.values]}
        if d:
            escribir(carpeta / f"{t}.json", d)
    print(f"detalles: {hechos} nuevos, {time.time() - t0:.0f}s")

    con_ficha = sum(1 for t in tickers if t in fund)
    con_det = sum(1 for t in tickers if (carpeta / f"{t}.json").exists() and leer(carpeta / f"{t}.json", {}).get("upd"))
    texto = (f"\n## Mercado\n\n{len(tickers)} acciones · fichas {con_ficha} · detalles {con_det} · "
             f"último precio {ultimo} · {time.time() - t0:.0f} s\n" + "".join(f"\n- {a}" for a in avisos) + "\n")
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
