# Cartera — contexto para Claude Code

App personal de seguimiento de cartera (fondos sobre todo; también ETFs y acciones), inspirada
en Getquin Premium. Uso principal: **rentabilidad de la cartera frente a índices** y **desgloses**
(región, sector, activo). Usuario: Enrique, inversor en España (MyInvestor), sabe Python.
Idioma de la interfaz y de los commits: español. El README está en inglés.

## Arquitectura
- `index.html`: toda la app en un archivo (HTML + CSS + JS, sin build). Chart.js 4.4.1 por CDN.
  Fuentes de Google: Doto (cifras grandes y títulos), Geist (texto), Geist Mono (etiquetas y datos).
- `config.yaml`: instrumentos, índices y sectores con sus fuentes de precio.
- `pipeline/actualizar.py` + `pipeline/fuentes.py`: descargan precios (Yahoo por ticker, Yahoo por
  ISIN, Morningstar por su API pública `lt.morningstar.com` (mstarpy ya exige Chrome), CSV manual en `data/manual/`), convierten a EUR, rellenan hacia
  delante sobre días hábiles y escriben `data/prices.json`, `data/meta.json`, `data/informe.md`.
  Si una fuente falla se conserva el histórico previo.
- `.github/workflows/datos.yml`: ejecuta el pipeline (días laborables 20:30 y 07:00 UTC, en cada
  push y a mano), hace commit de `data/` y publica en GitHub Pages (fuente: GitHub Actions).
- PWA: `manifest.webmanifest`, `sw.js` (red primero, caché si no hay conexión), `icons/`.
- Movimientos: `localStorage` + sincronización opcional con un **gist secreto** del usuario
  (token fine-grained solo con permiso de Gists). Exportar/importar copia en JSON.
- Claves de series en `prices.json`: `i:<instrumento>`, `b:<índice>`, `s:<sector>`.

## Cálculos (no romper)
- **TTWROR** diario con flujos al cierre: `r_t = (V_t − CF_t) / V_{t−1} − 1`; si la cartera estaba
  vacía, `r_t = V_t / CF_t − 1`. Compra: CF = uds × precio + comisión. Venta: CF = −(uds × precio −
  comisión). Dividendo: CF = −importe. Encadenado; anualizado solo si el periodo ≥ 1 año.
- **TIR** (XIRR por bisección), mostrada solo en periodos ≥ 1 año.
- Un periodo que empieza el primer día invertido arranca *antes* de ese día (incluye su efecto).
- Desglose por transparencia: peso de la posición × distribución del fondo (`region`, `sector`,
  `activo` en `config.yaml`).
- Índices = ETFs de acumulación en EUR (rentabilidad total para inversor en euros).
- Antes de tocar el motor (`Engine` en index.html), verificar con casos: aportación grande antes de
  una caída (TTWROR no cambia), comisión del primer día, venta total y recompra.

## Lenguaje de diseño (decidido con el usuario)
- Estética Nothing / Teenage Engineering / tipografía modular. Minimalismo tipo Robinhood,
  Trade Republic y Getquin, con un toque de diseño. Nada de estética genérica de IA.
- Base monocroma: negro puro en oscuro, gris papel en claro. Sin sombras ni degradados.
- **Solo colores de la paleta**: positivo = fósforo `#C4EF2C` (en claro, texto `#4A7400` y relleno
  `#A3D21E` para que se lea); negativo = rojo Nothing (`#E5202B` / `#FF3A44` en oscuro);
  acento elegible Señal `#FF4F12` (por defecto) o Cobalto `#3157FF`, para la cartera y la interfaz.
  No introducir otros verdes ni rojos.
- **Gráficas solo de línea, sin rellenos.** Cartera en acento; índices en grises con distintos trazos.
- Preferir **barras de rentabilidad** a mapas de calor (índices, sectores, posiciones). El calendario
  mensual sí usa celdas coloreadas.
- Títulos de sección en Doto y en minúscula; etiquetas pequeñas en mono y mayúsculas.

## Estado y pendientes
- Hecho: app completa (Resumen, Mercado, Desglose, Movimientos), 13 índices, 11 sectores del
  MSCI World con periodo «Hoy», calendario mensual, volatilidad y máxima caída, PWA, sync por gist.
- Repo público `eibanezdepablo/portfolio-tracker`; app en https://eibanezdepablo.github.io/portfolio-tracker/.
  Primera ejecución real (2026-10-20): los 13 índices, los 11 sectores y Horos (Yahoo `0P0001DFE8.F`,
  desde 2019) descargan sin errores. `^IBEX` y `^N225` son índices de precio (sin dividendos).
- Hecho: importador del export de órdenes de fondos de MyInvestor (`salida.xls`, HTML): suscripción →
  compra, reembolso → venta, traspasos como venta + compra con `via: 'traspaso'`; casa por ISIN, fecha =
  día cuyo valor liquidativo coincide con el precio neto, deduplica por nº de orden (`ref: myi:<n>`), omite
  reembolsos sin participaciones previas. No subir nunca el export al repo.
- Los 12 fondos del usuario están en `config.yaml` (9 por Yahoo `0P…`, 3 por Morningstar). El reembolso
  de DNB Technology (18-02-2026) necesita la compra original, anterior al export: la añade el usuario.
- Pendiente: distribuciones por región y sector de cada fondo; importador de ETFs y acciones de MyInvestor.
- Ideas aceptadas para más adelante: ajustes finos de diseño según el uso.
