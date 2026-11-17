"""HTML form handling: catalog-generated field names, parsing and re-rendering values.

Field names of the run form (``templates/partials/run_form.html``):

* ``in_<name>`` for ``real`` and ``int`` inputs (one text field);
* ``in_<name>`` repeated once per element for ``real_list`` inputs (editable rows);
* ``in_<name>.x`` and ``in_<name>.y`` repeated once per point for ``point_list`` inputs;
* ``engine`` (``python``, ``fortran`` or ``compare``), ``function`` (a preset id or ``custom``)
  and ``expression`` (the custom function, used only when ``function`` is ``custom``).

Numbers are typed the way the book's data cards are: ``0.``, ``.5``, ``1.E-5`` and ``1.D-3`` are
accepted, as are ordinary Python spellings; ``nan``, ``inf`` and anything else are rejected with
a message naming the field.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from gerald_na.registry import CatalogEntry, CatalogInput
from gerald_na.registry.models import parse_data_card_token
from gerald_na.web.services import MAX_LIST_ITEMS

__all__ = [
    "CUSTOM_FUNCTION",
    "FormLike",
    "FormValues",
    "ParsedRunForm",
    "default_form_values",
    "format_number",
    "parse_number",
    "parse_run_form",
]

CUSTOM_FUNCTION = "custom"
"""Value of the ``function`` select that means "use the custom expression"."""

MAX_FIELD_LENGTH = 64


class FormLike(Protocol):
    """What the parser needs from Starlette's ``FormData`` (or a plain multi-dict)."""

    def getlist(self, key: Any) -> Sequence[object]: ...


def parse_number(text: str, *, integer: bool) -> int | float:
    """Parse one typed number; raises :class:`ValueError` with a learner-friendly message.

    The syntax is the data card's (:func:`~gerald_na.registry.models.parse_data_card_token`);
    an int field also accepts an integral real such as ``20.``.
    """
    value = text.strip()
    if not value:
        raise ValueError("a value is required")
    if len(value) > MAX_FIELD_LENGTH:
        raise ValueError("the value is too long")
    try:
        if not integer:
            return parse_data_card_token(value, integer=False)
        try:
            return parse_data_card_token(value, integer=True)
        except ValueError:
            # Web-only leniency: an integral real such as "20." or "1.E1" fills an int field
            # (the CLI keeps Fortran's strict integer syntax).
            number = float(parse_data_card_token(value, integer=False))
            if number.is_integer() and abs(number) < 2**53:
                return int(number)
            raise
    except ValueError:
        if integer:
            raise ValueError(f"{value!r} is not an integer") from None
        raise ValueError(f"{value!r} is not a number (examples: 0.5, 1.E-5)") from None


def format_number(value: float) -> str:
    """A number as a form field shows it (shortest round-tripping text)."""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer() and abs(value) < 1e15:
        return f"{value:.1f}"
    return repr(float(value))


@dataclass
class FormValues:
    """Raw field values for (re-)rendering the run form."""

    scalars: dict[str, str] = field(default_factory=dict)
    lists: dict[str, list[str]] = field(default_factory=dict)
    points: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    engine: str = "python"
    function: str = ""
    expression: str = ""


@dataclass
class ParsedRunForm:
    """A parsed run form: typed inputs, the run options, and per-field errors."""

    values: FormValues
    inputs: dict[str, object]
    errors: dict[str, str]
    engine: str
    preset: int | None
    expression: str | None


def default_form_values(entry: CatalogEntry) -> FormValues:
    """The form prefilled with the book data card and the default preset."""
    values = FormValues()
    for item in entry.inputs:
        default = item.default
        if item.type in ("real", "int") and not isinstance(default, tuple):
            values.scalars[item.name] = format_number(default)
        elif item.type == "real_list" and isinstance(default, tuple):
            values.lists[item.name] = [
                format_number(number) for number in default if not isinstance(number, tuple)
            ]
        elif isinstance(default, tuple):
            values.points[item.name] = [
                (format_number(point[0]), format_number(point[1]))
                for point in default
                if isinstance(point, tuple)
            ]
    if entry.function.takes_function and entry.function.default_preset is not None:
        values.function = str(entry.function.default_preset)
    return values


def _strings(form: FormLike, key: str) -> list[str]:
    return [item if isinstance(item, str) else "" for item in form.getlist(key)]


def _first(form: FormLike, key: str) -> str:
    items = _strings(form, key)
    return items[0] if items else ""


def _parse_list(
    item: CatalogInput, texts: Sequence[str], errors: dict[str, str]
) -> list[float] | None:
    if len(texts) > MAX_LIST_ITEMS:
        errors[item.name] = f"at most {MAX_LIST_ITEMS} entries are accepted"
        return None
    numbers: list[float] = []
    for position, text in enumerate(texts, start=1):
        try:
            numbers.append(float(parse_number(text, integer=False)))
        except ValueError as exc:
            errors[item.name] = f"entry {position}: {exc}"
            return None
    return numbers


def parse_run_form(entry: CatalogEntry, form: FormLike) -> ParsedRunForm:
    """Parse the run form of ``entry``; problems land in ``errors`` keyed by input name.

    ``errors`` may also hold ``engine``, ``function`` and ``expression`` keys. Range checks
    (``min``/``max``, list length) are left to :func:`gerald_na.web.services.field_problems`.
    """
    values = FormValues()
    inputs: dict[str, object] = {}
    errors: dict[str, str] = {}
    for item in entry.inputs:
        key = f"in_{item.name}"
        match item.type:
            case "real" | "int":
                text = _first(form, key)
                values.scalars[item.name] = text
                try:
                    inputs[item.name] = parse_number(text, integer=item.type == "int")
                except ValueError as exc:
                    errors[item.name] = str(exc)
            case "real_list":
                texts = _strings(form, key)
                values.lists[item.name] = texts
                numbers = _parse_list(item, texts, errors)
                if numbers is not None:
                    inputs[item.name] = numbers
            case "point_list":
                xs, ys = _strings(form, f"{key}.x"), _strings(form, f"{key}.y")
                values.points[item.name] = list(zip(xs, ys, strict=False))
                if len(xs) != len(ys):
                    errors[item.name] = "every point needs both an x and a y value"
                    continue
                parsed_x = _parse_list(item, xs, errors)
                parsed_y = _parse_list(item, ys, errors) if parsed_x is not None else None
                if parsed_x is not None and parsed_y is not None:
                    inputs[item.name] = [[x, y] for x, y in zip(parsed_x, parsed_y, strict=True)]

    engine = _first(form, "engine") or "python"
    values.engine = engine
    function = _first(form, "function")
    values.function = function
    expression_text = _first(form, "expression")
    values.expression = expression_text
    preset: int | None = None
    expression: str | None = None
    if entry.function.takes_function:
        if function == CUSTOM_FUNCTION:
            if not expression_text.strip():
                errors["expression"] = "enter a function of x, for example x**2 - 2"
            else:
                expression = expression_text
        elif function:
            try:
                preset = int(function)
            except ValueError:
                errors["function"] = f"unknown function choice {function!r}"
    return ParsedRunForm(
        values=values,
        inputs=inputs,
        errors=errors,
        engine=engine,
        preset=preset,
        expression=expression,
    )
