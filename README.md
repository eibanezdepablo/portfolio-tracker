# portfolio-tracker

Small personal project: a static page that tracks a few investments and compares them with
market indices. Prices are refreshed by a scheduled GitHub Action.

```
index.html     the page (HTML, CSS and JS in one file)
config.yaml    instruments and indices to download
pipeline/      Python scripts that fetch prices
data/          generated data
```

To run it locally, serve the folder with any static server, e.g. `python -m http.server`.
