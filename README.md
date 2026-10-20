# Portfolio Tracker

A personal portfolio tracker for a Spanish investor, focused on mutual funds (plus ETFs and
stocks), inspired by Getquin Premium. It answers two questions: **how is my portfolio doing
against the indices** and **what am I really exposed to** (by region, sector and asset class).

**Live app:** https://eibanezdepablo.github.io/portfolio-tracker/

It is a single-page web app with no build step and no backend. Prices are downloaded every
weekday by a GitHub Action and published to GitHub Pages; your transactions never leave your
browser and your own private gist. The app can be installed on a phone as a PWA and works offline.

The user interface is in Spanish.

## Features

- **Summary** — total value, gain, time-weighted return (TTWROR) and money-weighted return
  (IRR) for 1M, 3M, YTD, 1Y, 3Y and Max, a performance chart against any of the indices,
  open positions, a monthly returns calendar, volatility and maximum drawdown.
- **Market** — returns of 13 benchmark indices and the 11 MSCI World sectors, from today to 3 years.
- **Breakdown** — look-through exposure by region, sector, asset class, type and position
  (position weight × each fund's allocation), and return bars per position.
- **Transactions** — buys, sells and dividends; **import from MyInvestor's order export**,
  including fund-to-fund transfers (*traspasos*); JSON backup export and import.
- **Sync** — transactions are stored in `localStorage` and, optionally, in a secret gist of your
  GitHub account, so phone and computer show the same portfolio.
- Light and dark themes, two accent colours (Signal orange and Cobalt blue).

## Repository layout

```
index.html               the whole app: HTML, CSS and JS in one file (Chart.js 4.4.1 via CDN)
config.yaml              your funds, ETFs, stocks, indices and sectors   ← what you edit
pipeline/actualizar.py   downloads prices and writes data/
pipeline/fuentes.py      price sources: Yahoo by ticker, Yahoo by ISIN, Morningstar, manual CSV
data/prices.json         daily prices in EUR on common business days (generated)
data/meta.json           names, types, codes and allocations for the app (generated)
data/informe.md          data report: source used for each series and any errors (generated)
data/manual/             manual price histories as CSV for funds no source covers
.github/workflows/       daily action that downloads prices and publishes the site
manifest.webmanifest, sw.js, icons/   PWA (network first, cache when offline)
```

## How the data pipeline works

`.github/workflows/datos.yml` (“Actualizar datos y publicar”) runs on weekdays at 20:30 UTC
(after the European close) and 07:00 UTC (fund NAVs published the next morning), on every push
to `main`, and on demand. It:

1. Reads `config.yaml` and, for every instrument, index and sector, tries its sources in order
   until one works: `yahoo` (ticker), `yahoo_isin` (search by ISIN), `morningstar` (by ISIN, via
   `mstarpy`) or `csv` (a file in `data/manual/`). Yahoo symbols with fewer than 30 prices are
   rejected so the next source is tried.
2. Converts everything to EUR with Yahoo's daily FX rates and forward-fills over business days.
3. Keeps the previous history if a source fails, so one bad day never wipes data.
4. Commits `data/` and deploys the site to GitHub Pages.

Series keys in `prices.json` are `i:<instrument>`, `b:<index>` and `s:<sector>`.

## How returns are calculated

- **TTWROR** (true time-weighted rate of return), daily with cash flows at the close:
  `r_t = (V_t − CF_t) / V_{t−1} − 1`; if the portfolio was empty, `r_t = V_t / CF_t − 1`.
  Buy: CF = units × price + fee. Sell: CF = −(units × price − fee). Dividend: CF = −amount.
  Daily returns are chained; the figure is annualised only for periods of one year or more.
  When you add money doesn't distort it.
- **IRR** (XIRR, solved by bisection): the money-weighted return, i.e. what *you* earned given
  your timing. Shown only for periods of one year or more.
- A period starting on the first invested day starts *before* that day, so its effect counts.
- **Benchmarks** are EUR-denominated accumulating ETFs, i.e. total return with dividends for a
  euro investor. Exceptions: IBEX 35 (`^IBEX`) and Nikkei 225 (`^N225`, converted from JPY) are
  price indices without dividends.
- **Look-through breakdown**: each position's weight × the fund's `region`, `sector` and
  `activo` allocation from `config.yaml`. Anything not covered shows as “Otros”.

### Benchmarks

| Index | Proxy |
|---|---|
| MSCI World | EUNL.DE |
| MSCI ACWI | IUSQ.DE |
| S&P 500 | SXR8.DE |
| Nasdaq 100 | SXRV.DE |
| STOXX Europe 600 | EXSA.DE |
| Euro Stoxx 50 | SXRT.DE |
| IBEX 35 | ^IBEX |
| MSCI Emerging Markets | IS3N.DE |
| Nikkei 225 | ^N225 |
| MSCI World Small Cap | IUSN.DE |
| MSCI World Value | IS3S.DE |
| Gold in EUR | 4GLD.DE |
| Global aggregate bonds | EUNA.DE |

Sectors use Xtrackers MSCI World sector ETFs on Xetra (XDWT, XDWF, XDWH, XDWC, XDWI, XWTS,
XDWS, XDW0, XDWM, XDWU) and IQQ6 for real estate.

## Setup (10 minutes)

1. **Create the repository** on GitHub, public (free GitHub Pages requires a public repo; see
   *Privacy* below), and push these files:
   ```bash
   git init -b main && git add . && git commit -m "Primera versión"
   git remote add origin https://github.com/YOUR_USER/portfolio-tracker.git
   git push -u origin main
   ```
2. **Enable the site:** *Settings → Pages → Build and deployment → Source: GitHub Actions*.
3. **First data download:** *Actions → Actualizar datos y publicar → Run workflow*. The run
   summary shows the data report with the source of each series and anything that failed.
4. **Open the app** at `https://YOUR_USER.github.io/portfolio-tracker/`. On Android: Chrome →
   menu ⋮ → *Install app* (or *Add to home screen*).

## Adding a fund, ETF or stock

Edit `config.yaml` (the GitHub web editor works) and commit; the action runs on every change.
The key (e.g. `horos`) is internal: don't rename it once you have transactions on it.

```yaml
  vanguard_global:
    nombre: Vanguard Global Stock Index
    isin: IE00B03HD191
    tipo: Fondo
    fuentes: [ { yahoo_isin: true }, { morningstar: true } ]
    region: { Norteamérica: 70, Europa: 16, Japón: 6, Otros: 8 }
    sector: {}
    activo: { Renta variable: 100 }
```

For an ETF or a stock, give the Yahoo ticker: `fuentes: [ { yahoo: SXR8.DE } ]`. If no source
has a fund, put its NAV history in `data/manual/<ISIN>.csv` (`fecha;precio`, Spanish Excel
format works) and add `{ csv: <ISIN>.csv }` to its sources.

## Importing from MyInvestor

In MyInvestor, export your fund orders (the file is called `salida.xls`; it is really an HTML
table). In the app: *Movimientos → Importar de MyInvestor* and pick the file.

- Subscriptions become buys and redemptions become sells; transfers (*suscripción / reembolso
  por traspaso*) are imported as a sell of the old fund and a buy of the new one, labelled
  “por traspaso”.
- Funds are matched by ISIN with `config.yaml`; missing ones are listed so you can add them.
- The order's net price is the fund's NAV of a day that is neither always the trade date nor the
  settlement date, so the importer looks up that NAV in the price history to date the order.
- The fee is the difference between the net amount and units × price; differences under 0.1 %
  are treated as rounding of the units (MyInvestor charges no fees on funds).
- Orders are deduplicated by order number, so you can import newer exports over older ones.
- A redemption of units bought before the export period is skipped and reported: add that
  purchase by hand and import again.

## Syncing phone and computer

1. Create a token: *Settings → Developer settings → Personal access tokens → Fine-grained
   tokens*, with **Account permissions → Gists: Read and write** and nothing else.
2. In the app: *Movimientos → Sincronizar*, paste the token and press *Conectar*.
3. Do the same on the other device with the same token; it finds the gist automatically.

## Privacy

- The repository is public: anyone can see the fund names in `config.yaml` and market prices,
  but **not your amounts or transactions**.
- Transactions live in your browser and in your secret gist (unlisted, but readable by anyone
  with its link). The token is stored only on your devices.
- Don't commit broker exports such as `salida.xls` to the repository.

## Design

Nothing / Teenage Engineering aesthetic with modular typography: Doto for big figures and
titles, Geist for text, Geist Mono for labels and data. Monochrome base (pure black in dark mode,
paper grey in light mode), no shadows or gradients. Gains in phosphor green `#C4EF2C`, losses in
Nothing red, line charts only, and return bars rather than heatmaps.

## Roadmap

- Fill in each fund's region and sector allocation in `config.yaml`.
- Importer for MyInvestor's ETF and stock trades.
- Design refinements based on daily use.
