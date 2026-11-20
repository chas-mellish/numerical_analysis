# Vendored front-end libraries

Served locally from `/static/vendor/` so the web UI works offline (no CDN at runtime).
Downloaded once from jsDelivr (npm dist files) and committed unchanged.

| File | Package | Version | License | Source |
|---|---|---|---|---|
| `htmx.min.js` | htmx.org | 2.0.11 | Zero-Clause BSD (`htmx.LICENSE.txt`) | https://cdn.jsdelivr.net/npm/htmx.org@2.0.11/dist/htmx.min.js |
| `plotly-cartesian.min.js` | plotly.js-cartesian-dist-min | 3.7.0 | MIT (`plotly.LICENSE.txt`) | https://cdn.jsdelivr.net/npm/plotly.js-cartesian-dist-min@3.7.0/plotly-cartesian.min.js |

SHA-256:

```
d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717  htmx.min.js
7c593b9eda0e74a1d07335cf89cbf7a55ffc114909980c3729af835453bdb02a  plotly-cartesian.min.js
```

The cartesian partial bundle of Plotly.js contains the scatter and heatmap traces the charts use
and is about a third of the full bundle. To upgrade, download the new dist files, update this
table and the `?v=` query strings in `templates/base.html` and `templates/program.html`.
