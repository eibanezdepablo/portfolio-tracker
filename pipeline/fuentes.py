"""Fuentes de precios. Cada función devuelve (serie, divisa, origen) o lanza una excepción."""
from __future__ import annotations
import datetime as dt
from pathlib import Path
import pandas as pd

MANUAL = Path(__file__).resolve().parent.parent / "data" / "manual"


def _limpia(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").dropna()
    s = s[s > 0]
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError("serie vacía")
    return s


def yahoo(symbol: str, inicio: str, ajustado: bool):
    import yfinance as yf
    t = yf.Ticker(symbol)
    h = t.history(start=inicio, auto_adjust=ajustado, actions=False)
    if h is None or h.empty:
        raise ValueError(f"Yahoo sin datos para {symbol}")
    divisa = (t.history_metadata or {}).get("currency") or "EUR"
    s = _limpia(h["Close"])
    if divisa in ("GBp", "GBX"):          # cotizaciones en peniques
        s, divisa = s / 100, "GBP"
    if len(s) < 30:                       # símbolos casi vacíos (p. ej. un solo cierre)
        raise ValueError(f"Yahoo solo tiene {len(s)} datos para {symbol}")
    return s, divisa, f"yahoo:{symbol}"


def yahoo_isin(isin: str, inicio: str, ajustado: bool):
    import yfinance as yf
    quotes = yf.Search(isin, max_results=5).quotes or []
    if not quotes:
        raise ValueError(f"Yahoo no encuentra {isin}")
    errores = []
    for q in quotes:
        try:
            return yahoo(q["symbol"], inicio, ajustado)
        except Exception as e:  # prueba el siguiente resultado
            errores.append(str(e))
    raise ValueError("; ".join(errores))


MS_API = "https://lt.morningstar.com/api/rest.svc"
MS_KEY = "klr5zyak8x"   # clave pública del buscador de fondos de Morningstar


def morningstar(isin: str, inicio: str, ajustado: bool):
    """Valor liquidativo en EUR desde la API pública de Morningstar (sin navegador ni token)."""
    import requests
    h = {"User-Agent": "Mozilla/5.0"}
    sec = None
    for universo in ("FOESP$$ALL", "FOALL$$ALL", "ETALL$$ALL"):
        r = requests.get(f"{MS_API}/{MS_KEY}/security/screener", headers=h, timeout=30, params={
            "page": 1, "pageSize": 1, "outputType": "json", "languageId": "es-ES", "currencyId": "EUR",
            "securityDataPoints": "SecId|ISIN", "term": isin, "universeIds": universo})
        filas = [f for f in r.json().get("rows", []) if f.get("ISIN") == isin] if r.ok else []
        if filas:
            sec = filas[0]["SecId"]
            break
    if not sec:
        raise ValueError(f"Morningstar no encuentra {isin}")
    r = requests.get(f"{MS_API}/timeseries_price/{MS_KEY}", headers=h, timeout=60, params={
        "id": sec, "currencyId": "EUR", "idtype": "Morningstar", "frequency": "daily",
        "startDate": inicio, "outputType": "COMPACTJSON"})
    r.raise_for_status()
    datos = r.json()
    if not datos:
        raise ValueError(f"Morningstar sin datos para {isin}")
    fechas = pd.to_datetime([t for t, _ in datos], unit="ms")
    s = _limpia(pd.Series([v for _, v in datos], index=fechas))
    return s, "EUR", f"morningstar:{isin} ({sec})"


def csv(nombre: str, inicio: str, ajustado: bool):
    """Histórico manual: data/manual/<nombre>, columnas fecha;precio (acepta coma decimal)."""
    ruta = MANUAL / nombre
    if not ruta.exists():
        raise FileNotFoundError(f"no existe data/manual/{nombre}")
    texto = ruta.read_text(encoding="utf-8", errors="ignore")
    europeo = ";" in texto[:2000]
    df = pd.read_csv(ruta, sep=";" if europeo else ",", decimal="," if europeo else ".")
    df.columns = [c.strip().lower() for c in df.columns]
    fecha = next(c for c in df.columns if c in ("fecha", "date"))
    precio = next(c for c in df.columns if c in ("precio", "valor", "nav", "close", "cierre"))
    fechas = pd.to_datetime(df[fecha], dayfirst=not df[fecha].astype(str).str.match(r"\d{4}-").all())
    s = _limpia(pd.Series(df[precio].values, index=fechas))
    return s, "EUR", f"csv:{nombre}"


FX_CACHE: dict[str, pd.Series] = {}


def a_euros(s: pd.Series, divisa: str, inicio: str) -> pd.Series:
    """Convierte a EUR con el cambio diario de Yahoo (EURUSD=X = dólares por euro)."""
    if divisa == "EUR":
        return s
    if divisa not in FX_CACHE:
        fx, _, _ = yahoo(f"EUR{divisa}=X", inicio, False)
        FX_CACHE[divisa] = fx
    fx = FX_CACHE[divisa]
    fx = fx.reindex(s.index.union(fx.index)).ffill().reindex(s.index)
    return (s / fx).dropna()


FUENTES = {"yahoo": yahoo, "yahoo_isin": yahoo_isin, "morningstar": morningstar, "csv": csv}
