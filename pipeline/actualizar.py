"""
Descarga los precios de todo lo definido en config.yaml y genera:
  data/prices.json  → fechas hábiles comunes y series en EUR (con relleno hacia delante)
  data/meta.json    → nombres, tipos, códigos y distribuciones para la web
  data/informe.md   → qué fuente se usó para cada serie y qué ha fallado

Si una fuente falla, se conserva el histórico que ya había en data/prices.json.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fuentes as F  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"


def cargar_config() -> dict:
    return yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))


def cargar_previo() -> dict[str, pd.Series]:
    ruta = DATA / "prices.json"
    if not ruta.exists():
        return {}
    px = json.loads(ruta.read_text(encoding="utf-8"))
    idx = pd.to_datetime(px["dates"])
    last = px.get("last", {})
    out = {}
    for k, vals in px["series"].items():
        s = pd.Series(vals, index=idx, dtype="float64").dropna()
        if k in last:                       # quita el relleno posterior al último dato real
            s = s[s.index <= pd.Timestamp(last[k])]
        if not s.empty:
            out[k] = s
    return out


def obtener(defn: dict, inicio: str, ajustado: bool, isin: str | None):
    errores = []
    for fuente in defn.get("fuentes", []):
        (tipo, arg), = fuente.items()
        try:
            if tipo in ("yahoo_isin", "morningstar"):
                if not isin:
                    raise ValueError("falta el ISIN")
                arg = isin
            s, divisa, origen = F.FUENTES[tipo](str(arg), inicio, ajustado)
            s = F.a_euros(s, divisa, inicio)
            return s, origen + ("" if divisa == "EUR" else f" ({divisa}→EUR)"), errores
        except Exception as e:  # sigue con la siguiente fuente
            errores.append(f"{tipo}: {e}")
    return None, "", errores


def main() -> int:
    cfg = cargar_config()
    inicio = str(cfg.get("inicio", "2019-01-01"))
    previo = cargar_previo()
    grupos = [("i", cfg.get("instrumentos") or {}, False),
              ("b", cfg.get("indices") or {}, True),
              ("s", cfg.get("sectores") or {}, True)]

    series: dict[str, pd.Series] = {}
    informe = []
    for pref, defs, ajustado in grupos:
        for clave, d in defs.items():
            k = f"{pref}:{clave}"
            s, origen, errores = obtener(d, inicio, ajustado, d.get("isin"))
            if s is not None and k in previo and previo[k].index.min() < s.index.min():
                s = s.combine_first(previo[k])     # conserva histórico antiguo si la fuente da menos
            if s is None and k in previo:
                s, origen = previo[k], "conservado de la ejecución anterior"
            if s is None:
                informe.append((k, "SIN DATOS", "", 0, " | ".join(errores)))
                continue
            series[k] = s
            informe.append((k, origen, s.index.max().date().isoformat(), len(s), " | ".join(errores)))

    if not series:
        print("No se ha podido descargar ninguna serie.")
        escribir_informe(informe)
        return 1

    hoy = pd.Timestamp(dt.date.today())
    fin = min(max(s.index.max() for s in series.values()), hoy)
    fechas = pd.bdate_range(pd.Timestamp(inicio), fin)
    salida = {}
    for k, s in series.items():
        r = s.reindex(fechas.union(s.index)).ffill().reindex(fechas)
        salida[k] = [None if pd.isna(x) else float(f"{x:.6g}") for x in r.values]

    DATA.mkdir(exist_ok=True)
    (DATA / "prices.json").write_text(json.dumps({
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dates": [d.date().isoformat() for d in fechas],
        "last": {k: series[k].index.max().date().isoformat() for k in series},
        "series": salida,
    }, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    instrumentos = cfg.get("instrumentos") or {}
    meta = {
        "instruments": {k: {"name": d.get("nombre", k), "id": d.get("isin") or d.get("ticker") or k,
                            "type": d.get("tipo", "Fondo")} for k, d in instrumentos.items()},
        "benchmarks": {k: {"code": d.get("codigo", k.upper()), "name": d.get("nombre", k)}
                       for k, d in (cfg.get("indices") or {}).items()},
        "sectors": {k: {"name": d.get("nombre", k)} for k, d in (cfg.get("sectores") or {}).items()},
        "alloc": {dim: {k: (d.get(campo) or {}) for k, d in instrumentos.items()}
                  for dim, campo in (("region", "region"), ("sector", "sector"), ("asset", "activo"))},
    }
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    escribir_informe(informe)
    return 0


def escribir_informe(filas) -> None:
    lineas = ["| Serie | Fuente | Último dato | Puntos | Errores |", "|---|---|---|---|---|"]
    lineas += [f"| {k} | {o} | {u} | {n} | {e[:180]} |" for k, o, u, n, e in filas]
    texto = "# Informe de datos\n\n" + "\n".join(lineas) + "\n"
    DATA.mkdir(exist_ok=True)
    (DATA / "informe.md").write_text(texto, encoding="utf-8")
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto)


if __name__ == "__main__":
    sys.exit(main())
