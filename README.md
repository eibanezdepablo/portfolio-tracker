# Cartera

Seguimiento de cartera frente a índices: TTWROR, TIR, comparación con 13 índices,
sectores del MSCI World, rentabilidad mensual y desglose por región y sector.
Web instalable en Android, con datos que se actualizan solos cada día laborable.

```
index.html               la app (un solo archivo)
config.yaml              tus fondos, ETFs, acciones e índices  ← lo que editas
pipeline/                script que descarga los precios
data/                    precios generados (no se tocan a mano)
data/manual/             históricos manuales en CSV si algún fondo no aparece
.github/workflows/       acción diaria que descarga datos y publica la web
```

## Puesta en marcha (10 minutos)

1. **Crea el repositorio** en GitHub: *New repository*, nombre `portfolio-tracker`, **público**
   (GitHub Pages gratis requiere repositorio público; ver *Privacidad* abajo).
2. **Sube los archivos.** Con git:
   ```bash
   cd portfolio-tracker
   git init -b main && git add . && git commit -m "Primera versión"
   git remote add origin https://github.com/TU_USUARIO/portfolio-tracker.git
   git push -u origin main
   ```
   O desde la web con *Add file → Upload files*, arrastrando todo el contenido
   (incluida la carpeta oculta `.github`; en macOS se muestra con Cmd+Mayús+punto).
3. **Activa la web:** *Settings → Pages → Build and deployment → Source: GitHub Actions*.
4. **Primera descarga de datos:** *Actions → Actualizar datos y publicar → Run workflow*.
   Al terminar, el resumen de la ejecución muestra un informe con la fuente de cada serie
   y lo que haya fallado.
5. **Abre la app** en `https://TU_USUARIO.github.io/cartera/`.
   En Android: Chrome → menú ⋮ → *Instalar aplicación* (o *Añadir a pantalla de inicio*).

## Sincronizar móvil y ordenador

Los movimientos se guardan en un **gist secreto** de tu cuenta.

1. Crea un token: *Settings → Developer settings → Personal access tokens → Fine-grained tokens*,
   con **Account permissions → Gists: Read and write** y nada más.
2. En la app: *Movimientos → Sincronizar*, pega el token y pulsa *Conectar*.
3. Repite en el otro dispositivo con el mismo token: encuentra el gist automáticamente.

También puedes exportar e importar una copia en JSON desde la misma pantalla.

## Añadir un fondo, ETF o acción

Edita `config.yaml` (se puede hacer desde la web de GitHub) y guarda. La acción se
ejecuta sola con cada cambio. Para un fondo basta con el ISIN:

```yaml
  vanguard_global:
    nombre: Vanguard Global Stock Index
    isin: IE00B03HD191
    tipo: Fondo
    fuentes: [ { yahoo_isin: true }, { morningstar: true } ]
```

Para un ETF o una acción, mejor indicar el ticker de Yahoo: `fuentes: [ { yahoo: SXR8.DE } ]`.

## Cómo se calcula la rentabilidad

- **TTWROR**: rentabilidad diaria descontando aportaciones y retiradas
  (`r = (V_t − flujo_t) / V_{t−1} − 1`), encadenada. Las comisiones restan; ventas y
  dividendos son salidas de dinero. No la distorsiona cuándo aportas.
- **TIR**: rentabilidad ponderada por dinero (lo que has ganado tú con tus fechas de
  aportación). Se muestra anualizada en periodos de un año o más.
- Índices: ETFs de acumulación en euros, es decir, rentabilidad total con dividendos
  para un inversor en EUR.

## Privacidad

- El repositorio es público: se ven los nombres de los fondos de `config.yaml` y los
  precios, pero **no tus importes ni movimientos**.
- Los movimientos viven en el navegador y en tu gist secreto (no aparece listado, pero
  quien tenga su enlace puede leerlo). El token se guarda solo en tus dispositivos.
