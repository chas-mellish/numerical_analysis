"""Plotly figure specs for the results panel, chosen by the catalog's ``[chart] kind``.

Every builder is a pure function of a :class:`ChartInput`: the step rows (dicts keyed by the
catalog ``step_columns``), the result's plain fields (``result_to_dict``; ``None`` after an
error, when only the partial steps exist), the validated inputs, the catalog ``[chart] options``
and, for programs that take a function, the compiled function F(x). The output is a list of
:class:`Figure` dicts (``id``, ``title``, ``data``, ``layout``) that ``static/app.js`` hands to
``Plotly.newPlot``. Values are JSON-safe (NaN and infinities become ``null``).

What each kind reads (option defaults in brackets; see ``docs/architecture.md``):

* ``bracket`` -- steps ``lower_key`` [x1], ``upper_key`` [x2], ``point_key`` [x] against
  ``index_key`` [k]; with ``residual_key`` (e.g. fx) it adds the ``abs_residual`` figure
  (``log_residual`` [true]).
* ``abs_residual`` -- |steps[``residual_key`` [fx]]| against ``index_key`` [k], log scale unless
  ``log_residual = false``.
* ``romberg_heatmap`` -- result field ``table_field`` [table]: a ragged list of rows as printed
  (row i, column j; axis titles ``row_label`` / ``column_label``). Colour = log10 |cell - result
  value| (``color = "value"`` colours by the cell itself); the text of each cell is its value.
* ``integrand_panels`` -- F sampled on a fine grid over [``a`` (number, or input ``lower_input``)
  [0], input ``upper_input`` [b]] plus the ordinates of the steps ``x_key`` [x], ``y_key`` [fx]
  (``weight_key`` [weight] shown in the hover when present).
* ``factors`` -- steps grouped by ``group_key`` [factor] with ``index_key`` [k], ``r_key`` [r],
  ``s_key`` [s]: one figure for r and one for s per iteration; a third figure puts the roots on
  the complex plane. Roots come from result ``roots_field`` [roots] (complex numbers, [re, im]
  pairs or {re, im} dicts) or else from result ``factors_field`` [factors], a list of dicts or
  dataclasses with ``kind`` = quadratic (``r``, ``s``; ``quadratic_form`` ["x^2 - r x - s"] or
  "x^2 + r x + s"), final_quadratic (``a2``, ``a1``, ``a0``) or linear (``a1``, ``a0``); the
  coefficients may also come as one ``coefficients`` list in that order (``BairstowFactor``).
  With ``poly_input`` (a real_list input, highest power first) the polynomial's own roots are
  added as a reference. With ``delta_keys`` (e.g. ["delr", "dels"]) a ``factors_delta`` figure
  shows the sum of their absolute values per iteration (log scale unless ``log_delta = false``);
  with ``poly_input`` and ``show_polynomial = true`` a ``factors_polynomial`` figure draws P(x)
  with the real roots from the factors marked.
* ``interpolant`` -- the nodes of input ``points_input`` [points] (only the first
  ``count_input`` [n] when that input exists), the Lagrange polynomial through them, and the
  evaluated point (input ``x_input`` [xin], result ``value``); ``samples`` [400] curve points,
  axis titles ``x_label`` [x] and ``y_label`` [y].
"""

import cmath
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any

__all__ = [
    "CHART_BUILDERS",
    "ChartInput",
    "Figure",
    "build_figures",
    "json_safe",
    "polynomial_roots",
]

type Figure = dict[str, Any]

# Reference palette (dataviz skill): categorical slots 1-3 validate all-pairs in light mode.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
SEQUENTIAL = (
    (0.0, "#cde2fb"),
    (0.25, "#86b6ef"),
    (0.5, "#3987e5"),
    (0.75, "#1c5cab"),
    (1.0, "#0d366b"),
)
GRID_POINTS = 400
"""Samples used to draw a function curve."""


@dataclass(frozen=True)
class ChartInput:
    """Everything a chart builder may read."""

    kind: str
    options: Mapping[str, Any] = field(default_factory=dict)
    steps: Sequence[Mapping[str, Any]] = ()
    result: Mapping[str, Any] | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    function: Callable[[float], float] | None = None
    labels: Mapping[str, str] = field(default_factory=dict)

    def option(self, key: str, default: Any) -> Any:
        """A ``[chart] options`` value, or ``default``."""
        return self.options.get(key, default)

    def label(self, key: str) -> str:
        """The catalog column label of step key ``key`` (falls back to the key)."""
        return self.labels.get(key, key)


# ---------------------------------------------------------------- helpers


def json_safe(value: object) -> Any:
    """Convert to JSON-ready data: NaN/inf -> None, complex -> {re, im}, dataclasses -> dicts."""
    if isinstance(value, bool) or value is None or isinstance(value, str | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, complex):
        return {"re": json_safe(value.real), "im": json_safe(value.imag)}
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: json_safe(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [json_safe(item) for item in value]
    return str(value)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _column(steps: Sequence[Mapping[str, Any]], key: str) -> list[float | None]:
    return [_number(step.get(key)) for step in steps]


def _index(data: ChartInput) -> list[float | None]:
    key = str(data.option("index_key", "k"))
    values = _column(data.steps, key)
    if data.steps and all(value is None for value in values):
        return [float(i) for i in range(1, len(data.steps) + 1)]
    return values


def _layout(title: str, x_title: str, y_title: str, **extra: Any) -> dict[str, Any]:
    axis = {
        "gridcolor": GRID,
        "zerolinecolor": GRID,
        "linecolor": INK_SECONDARY,
        "tickfont": {"color": INK_SECONDARY},
        "automargin": True,
    }
    layout: dict[str, Any] = {
        "title": {"text": title, "font": {"size": 15, "color": INK}, "x": 0, "xanchor": "left"},
        "paper_bgcolor": SURFACE,
        "plot_bgcolor": SURFACE,
        "font": {"family": "system-ui, sans-serif", "color": INK, "size": 12},
        "margin": {"l": 60, "r": 20, "t": 48, "b": 80},
        "xaxis": {**axis, "title": {"text": x_title}},
        "yaxis": {**axis, "title": {"text": y_title}},
        "legend": {
            "orientation": "h",
            "x": 0,
            "y": -0.32,
            "yanchor": "top",
            "traceorder": "normal",
            "font": {"color": INK_SECONDARY},
        },
        "hovermode": "closest",
        "height": 360,
    }
    layout.update(extra)
    return layout


def _line(
    name: str, xs: Sequence[float | None], ys: Sequence[float | None], slot: int, **extra: Any
) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "type": "scatter",
        "mode": "lines+markers",
        "name": name,
        "x": list(xs),
        "y": list(ys),
        "line": {"color": SERIES[slot % len(SERIES)], "width": 2},
        "marker": {"color": SERIES[slot % len(SERIES)], "size": 8},
    }
    trace.update(extra)
    return trace


def _figure(fig_id: str, title: str, data: list[dict[str, Any]], layout: dict[str, Any]) -> Figure:
    return {"id": fig_id, "title": title, "data": json_safe(data), "layout": json_safe(layout)}


def _sample(
    function: Callable[[float], float], lo: float, hi: float, count: int = GRID_POINTS
) -> tuple[list[float], list[float | None]]:
    """``count`` samples of ``function`` on [lo, hi]; failing or non-finite points are gaps."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi == lo:
        return [], []
    xs = [lo + (hi - lo) * i / (count - 1) for i in range(count)]
    ys: list[float | None] = []
    for x in xs:
        try:
            ys.append(_number(function(x)))
        except Exception:  # a learner function may fail anywhere (domain errors, overflow)
            ys.append(None)
    return xs, ys


# ---------------------------------------------------------------- kinds


def _abs_residual_figure(data: ChartInput) -> Figure:
    key = str(data.option("residual_key", "fx"))
    log = bool(data.option("log_residual", data.option("log", True)))
    values = [None if v is None else abs(v) for v in _column(data.steps, key)]
    if log:  # log scale cannot show an exact zero
        values = [None if v is None or v == 0.0 else v for v in values]
    label = data.label(key)
    trace = _line(
        f"|{label}|",
        _index(data),
        values,
        0,
        hovertemplate=f"iteration %{{x}}<br>|{label}| = %{{y:.3e}}<extra></extra>",
    )
    title = f"|{label}| per iteration" + (" (log scale)" if log else "")
    layout = _layout(title, "iteration", f"|{label}|", showlegend=False)
    if log:
        layout["yaxis"]["type"] = "log"
        layout["yaxis"]["exponentformat"] = "power"
    return _figure("abs_residual", title, [trace], layout)


def bracket_figures(data: ChartInput) -> list[Figure]:
    """Bracket [lower, upper] per iteration with the midpoint; plus |residual| if configured."""
    lower = str(data.option("lower_key", "x1"))
    upper = str(data.option("upper_key", "x2"))
    point = str(data.option("point_key", "x"))
    xs = _index(data)
    hover = "iteration %{x}<br>%{fullData.name} = %{y:.10g}<extra></extra>"
    traces = [
        _line(data.label(lower), xs, _column(data.steps, lower), 0, hovertemplate=hover),
        _line(
            data.label(upper),
            xs,
            _column(data.steps, upper),
            1,
            hovertemplate=hover,
            fill="tonexty",
            fillcolor="rgba(42,120,214,0.08)",
        ),
        _line(
            f"midpoint {data.label(point)}",
            xs,
            _column(data.steps, point),
            2,
            mode="markers",
            hovertemplate=hover,
            marker={"color": SERIES[2], "size": 9, "symbol": "diamond"},
        ),
    ]
    title = "Bracket shrinkage per iteration"
    figures = [_figure("bracket", title, traces, _layout(title, "iteration", data.label(point)))]
    if data.option("residual_key", None) is not None:
        figures.append(_abs_residual_figure(data))
    return figures


def abs_residual_figures(data: ChartInput) -> list[Figure]:
    """|F(x)| (or another residual column) per iteration on a log scale."""
    return [_abs_residual_figure(data)]


def romberg_heatmap_figures(data: ChartInput) -> list[Figure]:
    """Heat-map of the triangular Romberg table (rows as printed)."""
    table_field = str(data.option("table_field", "table"))
    raw = (data.result or {}).get(table_field) or []
    rows: list[list[float | None]] = []
    for row in raw if isinstance(raw, Sequence) else []:
        if isinstance(row, Sequence) and not isinstance(row, str):
            rows.append([_number(cell) for cell in row])
    width = max((len(row) for row in rows), default=0)
    best = _number((data.result or {}).get("value"))
    by_value = data.option("color", "error") == "value" or best is None
    z: list[list[float | None]] = []
    text: list[list[str]] = []
    for row in rows:
        z_row: list[float | None] = []
        text_row: list[str] = []
        for j in range(width):
            cell = row[j] if j < len(row) else None
            text_row.append("" if cell is None else f"{cell:.9g}")
            if cell is None:
                z_row.append(None)
            elif by_value or best is None:
                z_row.append(cell)
            else:
                z_row.append(math.log10(max(abs(cell - best), 1e-17)))
        z.append(z_row)
        text.append(text_row)
    colorbar_title = "value" if by_value else "log10 |T - result|"
    trace = {
        "type": "heatmap",
        "z": z,
        "text": text,
        "texttemplate": "%{text}",
        "x": [j + 1 for j in range(width)],
        "y": [i + 1 for i in range(len(rows))],
        "colorscale": [list(stop) for stop in SEQUENTIAL],
        "colorbar": {"title": {"text": colorbar_title}},
        "hoverongaps": False,
        "xgap": 2,
        "ygap": 2,
        "hovertemplate": "row %{y}, column %{x}<br>T = %{text}<br>"
        + ("%{z:.9g}" if by_value else "log10 error %{z:.2f}")
        + "<extra></extra>",
    }
    title = "Romberg table" + ("" if by_value else " (colour: distance from the result)")
    layout = _layout(
        title,
        str(data.option("column_label", "column j")),
        str(data.option("row_label", "row i")),
    )
    layout["yaxis"]["autorange"] = "reversed"
    layout["xaxis"]["dtick"] = 1
    layout["yaxis"]["dtick"] = 1
    layout["xaxis"]["showgrid"] = False
    layout["yaxis"]["showgrid"] = False
    return [_figure("romberg_heatmap", title, [trace], layout)]


def _bound(data: ChartInput, number_key: str, input_key: str, default_input: str | None) -> Any:
    value = data.option(number_key, None)
    if _number(value) is not None:
        return _number(value)
    name = data.option(input_key, default_input)
    return _number(data.inputs.get(str(name))) if name is not None else None


def integrand_panels_figures(data: ChartInput) -> list[Figure]:
    """The integrand on a fine grid with the panel ordinates of the rule."""
    x_key = str(data.option("x_key", "x"))
    y_key = str(data.option("y_key", "fx"))
    weight_key = str(data.option("weight_key", "weight"))
    xs = _column(data.steps, x_key)
    ys = _column(data.steps, y_key)
    known = [x for x in xs if x is not None]
    lo = _bound(data, "a", "lower_input", None)
    hi = _bound(data, "b", "upper_input", "b")
    lo = lo if lo is not None else (min(known) if known else 0.0)
    hi = hi if hi is not None else (max(known) if known else 1.0)
    if known:
        lo, hi = min(lo, min(known)), max(hi, max(known))
    traces: list[dict[str, Any]] = []
    if data.function is not None:
        grid_x, grid_y = _sample(data.function, lo, hi)
        traces.append(
            _line(
                "F(x)",
                grid_x,
                grid_y,
                0,
                mode="lines",
                hovertemplate="x = %{x:.6g}<br>F(x) = %{y:.8g}<extra></extra>",
            )
        )
    stem_x: list[float | None] = []
    stem_y: list[float | None] = []
    for x, y in zip(xs, ys, strict=True):
        if x is None or y is None:
            continue
        stem_x += [x, x, None]
        stem_y += [0.0, y, None]
    traces.append(
        {
            "type": "scatter",
            "mode": "lines",
            "name": "panel ordinates",
            "x": stem_x,
            "y": stem_y,
            "line": {"color": SERIES[1], "width": 1},
            "hoverinfo": "skip",
            "showlegend": False,
        }
    )
    weights = _column(data.steps, weight_key)
    has_weights = any(w is not None for w in weights)
    traces.append(
        {
            "type": "scatter",
            "mode": "markers",
            "name": f"ordinates {data.label(y_key)}",
            "x": xs,
            "y": ys,
            "customdata": weights if has_weights else None,
            "marker": {"color": SERIES[1], "size": 8, "line": {"color": SURFACE, "width": 2}},
            "hovertemplate": "x = %{x:.6g}<br>F = %{y:.8g}"
            + ("<br>weight %{customdata}" if has_weights else "")
            + "<extra></extra>",
        }
    )
    title = "Integrand and panel ordinates"
    return [_figure("integrand_panels", title, traces, _layout(title, "x", "F(x)"))]


def _as_mapping(item: object) -> Mapping[str, Any] | None:
    if isinstance(item, Mapping):
        return item
    if is_dataclass(item) and not isinstance(item, type):
        return {f.name: getattr(item, f.name) for f in fields(item)}
    return None


def _quadratic_roots(a: float, b: float, c: float) -> list[complex]:
    if a == 0.0:
        return [complex(-c / b)] if b != 0.0 else []
    disc = cmath.sqrt(b * b - 4.0 * a * c)
    return [(-b + disc) / (2.0 * a), (-b - disc) / (2.0 * a)]


def _root(item: object) -> complex | None:
    if isinstance(item, complex):
        return item
    number = _number(item)
    if number is not None:
        return complex(number)
    if isinstance(item, Sequence) and not isinstance(item, str) and len(item) == 2:
        re_part, im_part = _number(item[0]), _number(item[1])
        if re_part is not None and im_part is not None:
            return complex(re_part, im_part)
    mapping = _as_mapping(item)
    if mapping is not None:
        re_part = _number(mapping.get("re", mapping.get("real")))
        im_part = _number(mapping.get("im", mapping.get("imag")))
        if re_part is not None and im_part is not None:
            return complex(re_part, im_part)
    return None


_COEFFICIENT_NAMES: Mapping[str, tuple[str, ...]] = {
    "quadratic": ("r", "s"),
    "final_quadratic": ("a2", "a1", "a0"),
    "linear": ("a1", "a0"),
}


def _with_named_coefficients(mapping: Mapping[str, Any]) -> Mapping[str, Any]:
    """Expand ``{kind, coefficients: [...]}`` (``BairstowFactor``) into named keys."""
    names = _COEFFICIENT_NAMES.get(str(mapping.get("kind", "")))
    values = mapping.get("coefficients")
    if names is None or not isinstance(values, Sequence) or isinstance(values, str):
        return mapping
    if len(values) != len(names):
        return mapping
    return {**mapping, **dict(zip(names, values, strict=True))}


def factor_roots(factors: Sequence[object], quadratic_form: str) -> list[complex]:
    """Roots of Bairstow factor records (see the module docstring for the accepted shapes)."""
    roots: list[complex] = []
    minus = quadratic_form.replace(" ", "") != "x^2+rx+s"
    for item in factors:
        mapping = _as_mapping(item)
        if mapping is None:
            continue
        mapping = _with_named_coefficients(mapping)
        r, s = _number(mapping.get("r")), _number(mapping.get("s"))
        a2, a1, a0 = (_number(mapping.get(k)) for k in ("a2", "a1", "a0"))
        kind = str(mapping.get("kind", ""))
        if r is not None and s is not None and kind in ("", "quadratic"):
            roots += _quadratic_roots(1.0, -r, -s) if minus else _quadratic_roots(1.0, r, s)
        elif a2 is not None and a1 is not None and a0 is not None:
            roots += _quadratic_roots(a2, a1, a0)
        elif a1 is not None and a0 is not None and a1 != 0.0:
            roots.append(complex(-a0 / a1))
    return roots


def polynomial_roots(coefficients: Sequence[float], iterations: int = 500) -> list[complex]:
    """Roots of a polynomial (highest power first) by the Durand-Kerner iteration."""
    coeffs = [float(c) for c in coefficients]
    while coeffs and coeffs[0] == 0.0:
        coeffs.pop(0)
    degree = len(coeffs) - 1
    if degree < 1:
        return []
    monic = [c / coeffs[0] for c in coeffs]

    def value(z: complex) -> complex:
        total = 0j
        for c in monic:
            total = total * z + c
        return total

    roots = [complex(0.4, 0.9) ** k for k in range(degree)]
    for _ in range(iterations):
        delta = 0.0
        updated: list[complex] = []
        for i, z in enumerate(roots):
            denominator = 1 + 0j
            for j, other in enumerate(roots):
                if i != j:
                    denominator *= z - other
            step = value(z) / denominator if denominator != 0 else 0j
            updated.append(z - step)
            delta = max(delta, abs(step))
        roots = updated
        if delta < 1e-14:
            break
    return roots


def _delta_figure(
    data: ChartInput,
    groups: Mapping[object, Sequence[Mapping[str, Any]]],
    keys: Sequence[str],
    index_key: str,
) -> Figure:
    """Sum of |corrections| (e.g. |DELR| + |DELS|) per iteration, by factor."""
    log = bool(data.option("log_delta", True))
    label = " + ".join(f"|{data.label(key)}|" for key in keys)
    traces = []
    for slot, (group, rows) in enumerate(groups.items()):
        sizes: list[float | None] = []
        for row in rows:
            parts = [_number(row.get(key)) for key in keys]
            total = None if any(p is None for p in parts) else sum(abs(p or 0.0) for p in parts)
            sizes.append(None if total is None or (log and total == 0.0) else total)
        traces.append(
            _line(
                f"factor {group}",
                _column(rows, index_key),
                sizes,
                slot,
                hovertemplate=f"factor {group}, iteration %{{x}}<br>{label} = %{{y:.3e}}"
                "<extra></extra>",
            )
        )
    title = f"{label} per iteration, by factor" + (" (log scale)" if log else "")
    layout = _layout(title, "iteration within factor", label)
    if log:
        layout["yaxis"]["type"] = "log"
        layout["yaxis"]["exponentformat"] = "power"
    return _figure("factors_delta", title, traces, layout)


def factors_figures(data: ChartInput) -> list[Figure]:
    """r and s per iteration for each factor, and the roots on the complex plane."""
    group_key = str(data.option("group_key", "factor"))
    index_key = str(data.option("index_key", "k"))
    groups: dict[object, list[Mapping[str, Any]]] = {}
    for step in data.steps:
        groups.setdefault(step.get(group_key, 1), []).append(step)
    figures: list[Figure] = []
    for coefficient in (str(data.option("r_key", "r")), str(data.option("s_key", "s"))):
        traces = [
            _line(
                f"factor {group}",
                _column(rows, index_key),
                _column(rows, coefficient),
                slot,
                hovertemplate=f"factor {group}, iteration %{{x}}<br>{data.label(coefficient)}"
                " = %{y:.10g}<extra></extra>",
            )
            for slot, (group, rows) in enumerate(groups.items())
        ]
        title = f"{data.label(coefficient)} per iteration, by factor"
        figures.append(
            _figure(
                f"factors_{coefficient}",
                title,
                traces,
                _layout(title, "iteration within factor", data.label(coefficient)),
            )
        )
    delta_keys = data.option("delta_keys", None)
    if isinstance(delta_keys, Sequence) and not isinstance(delta_keys, str) and delta_keys:
        figures.append(_delta_figure(data, groups, [str(key) for key in delta_keys], index_key))
    result = data.result or {}
    roots: list[complex] = []
    raw_roots = result.get(str(data.option("roots_field", "roots")))
    if isinstance(raw_roots, Sequence) and not isinstance(raw_roots, str):
        roots = [root for root in (_root(item) for item in raw_roots) if root is not None]
    if not roots:
        raw_factors = result.get(str(data.option("factors_field", "factors")))
        if isinstance(raw_factors, Sequence) and not isinstance(raw_factors, str):
            roots = factor_roots(raw_factors, str(data.option("quadratic_form", "x^2 - r x - s")))
    root_traces: list[dict[str, Any]] = [
        {
            "type": "scatter",
            "mode": "markers",
            "name": "roots from the factors",
            "x": [root.real for root in roots],
            "y": [root.imag for root in roots],
            "marker": {"color": SERIES[0], "size": 10, "line": {"color": SURFACE, "width": 2}},
            "hovertemplate": "%{x:.8g} %{y:+.8g}i<extra></extra>",
        }
    ]
    poly_input = data.option("poly_input", None)
    numbers: list[float] = []
    if poly_input is not None:
        coefficients = data.inputs.get(str(poly_input))
        if isinstance(coefficients, Sequence) and not isinstance(coefficients, str):
            numbers = [n for n in (_number(c) for c in coefficients) if n is not None]
            reference = polynomial_roots(numbers)
            root_traces.append(
                {
                    "type": "scatter",
                    "mode": "markers",
                    "name": "polynomial roots (reference)",
                    "x": [root.real for root in reference],
                    "y": [root.imag for root in reference],
                    "marker": {
                        "color": SERIES[1],
                        "size": 14,
                        "symbol": "circle-open",
                        "line": {"width": 2},
                    },
                    "hovertemplate": "%{x:.8g} %{y:+.8g}i<extra></extra>",
                }
            )
    title = "Roots on the complex plane"
    layout = _layout(title, "real part", "imaginary part")
    layout["yaxis"]["zeroline"] = True
    layout["xaxis"]["zeroline"] = True
    figures.append(_figure("factors_roots", title, root_traces, layout))
    if numbers and bool(data.option("show_polynomial", False)):
        figures.append(_polynomial_figure(numbers, roots))
    return figures


def _polynomial_figure(coefficients: Sequence[float], roots: Sequence[complex]) -> Figure:
    """P(x) (coefficients highest power first) over its real roots, which are marked."""
    real_roots = [root.real for root in roots if abs(root.imag) <= 1e-9 * max(1.0, abs(root))]
    span = [root.real for root in roots] or [-1.0, 1.0]
    lo, hi = min(span), max(span)
    pad = max(0.1 * (hi - lo), 0.5)

    def value(x: float) -> float:
        total = 0.0
        for c in coefficients:
            total = total * x + c
        return total

    grid_x, grid_y = _sample(value, lo - pad, hi + pad)
    traces = [
        _line(
            "P(x)",
            grid_x,
            grid_y,
            0,
            mode="lines",
            hovertemplate="x = %{x:.6g}<br>P(x) = %{y:.8g}<extra></extra>",
        ),
        {
            "type": "scatter",
            "mode": "markers",
            "name": "real roots from the factors",
            "x": real_roots,
            "y": [0.0 for _ in real_roots],
            "marker": {"color": SERIES[1], "size": 10, "line": {"color": SURFACE, "width": 2}},
            "hovertemplate": "root %{x:.8g}<extra></extra>",
        },
    ]
    title = "The polynomial and its real roots"
    layout = _layout(title, "x", "P(x)")
    layout["yaxis"]["zeroline"] = True
    return _figure("factors_polynomial", title, traces, layout)


def _lagrange(nodes: Sequence[tuple[float, float]], x: float) -> float:
    total = 0.0
    for i, (xi, yi) in enumerate(nodes):
        term = yi
        for j, (xj, _) in enumerate(nodes):
            if i != j:
                term *= (x - xj) / (xi - xj)
        total += term
    return total


def interpolant_figures(data: ChartInput) -> list[Figure]:
    """Data nodes, the Lagrange polynomial through them, and the evaluated point."""
    raw = data.inputs.get(str(data.option("points_input", "points"))) or []
    nodes: list[tuple[float, float]] = []
    for item in raw if isinstance(raw, Sequence) else []:
        if isinstance(item, Sequence) and len(item) == 2:
            x, y = _number(item[0]), _number(item[1])
            if x is not None and y is not None:
                nodes.append((x, y))
    count = _number(data.inputs.get(str(data.option("count_input", "n"))))
    if count is not None and 0 < count < len(nodes):
        nodes = nodes[: int(count)]
    x_in = _number(data.inputs.get(str(data.option("x_input", "xin"))))
    value = _number((data.result or {}).get("value"))
    traces: list[dict[str, Any]] = []
    distinct = len({x for x, _ in nodes}) == len(nodes)
    if len(nodes) >= 2 and distinct:
        xs = [x for x, _ in nodes] + ([x_in] if x_in is not None else [])
        lo, hi = min(xs), max(xs)
        pad = 0.05 * (hi - lo)
        samples = _number(data.option("samples", GRID_POINTS))
        n_samples = int(samples) if samples is not None and 2 <= samples <= 10 * GRID_POINTS else 0
        grid_x, grid_y = _sample(
            lambda t: _lagrange(nodes, t), lo - pad, hi + pad, n_samples or GRID_POINTS
        )
        traces.append(
            _line(
                "Lagrange polynomial",
                grid_x,
                grid_y,
                0,
                mode="lines",
                hovertemplate="x = %{x:.6g}<br>P(x) = %{y:.8g}<extra></extra>",
            )
        )
    traces.append(
        {
            "type": "scatter",
            "mode": "markers",
            "name": "data nodes",
            "x": [x for x, _ in nodes],
            "y": [y for _, y in nodes],
            "marker": {"color": SERIES[1], "size": 10, "line": {"color": SURFACE, "width": 2}},
            "hovertemplate": "node (%{x:.6g}, %{y:.8g})<extra></extra>",
        }
    )
    if x_in is not None and value is not None:
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": "interpolated value",
                "x": [x_in],
                "y": [value],
                "marker": {"color": SERIES[2], "size": 13, "symbol": "diamond"},
                "hovertemplate": "P(%{x:.6g}) = %{y:.8g}<extra></extra>",
            }
        )
    title = "Interpolating polynomial"
    layout = _layout(title, str(data.option("x_label", "x")), str(data.option("y_label", "y")))
    return [_figure("interpolant", title, traces, layout)]


CHART_BUILDERS: Mapping[str, Callable[[ChartInput], list[Figure]]] = {
    "bracket": bracket_figures,
    "abs_residual": abs_residual_figures,
    "romberg_heatmap": romberg_heatmap_figures,
    "integrand_panels": integrand_panels_figures,
    "factors": factors_figures,
    "interpolant": interpolant_figures,
}
"""Builder per catalog ``[chart] kind``."""


def build_figures(data: ChartInput) -> list[Figure]:
    """The figures for ``data.kind`` (an unknown kind gives no figures)."""
    builder = CHART_BUILDERS.get(data.kind)
    return builder(data) if builder is not None else []
