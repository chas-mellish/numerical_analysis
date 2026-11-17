/* gerald-na web UI: charts, tabs, function/engine coupling, list rows and row counts.
 * No inline scripts (strict CSP); behaviour is attached by event delegation so it survives
 * HTMX swaps. Chart specs arrive as <script type="application/json" data-chart-spec>. */
(function () {
  "use strict";

  // ------------------------------------------------------------ charts
  function renderCharts(root) {
    var specs = root.querySelectorAll ? root.querySelectorAll("script[data-chart-spec]") : [];
    specs.forEach(function (script) {
      if (script.dataset.rendered === "1") return;
      var host = script.closest("[data-chart-host]");
      if (!host || !window.Plotly) return;
      var figures;
      try {
        figures = JSON.parse(script.textContent);
      } catch (err) {
        return;
      }
      script.dataset.rendered = "1";
      figures.forEach(function (fig) {
        var target = host.querySelector('[data-figure="' + fig.id + '"]');
        if (!target) return;
        window.Plotly.newPlot(target, fig.data, fig.layout, {
          responsive: true,
          displaylogo: false,
          modeBarButtonsToRemove: ["lasso2d", "select2d"],
        });
      });
    });
  }

  // ------------------------------------------------------------ tabs
  function selectTab(tab) {
    var list = tab.closest('[role="tablist"]');
    var container = tab.closest("[data-tabs]");
    if (!list || !container) return;
    list.querySelectorAll('[role="tab"]').forEach(function (other) {
      var selected = other === tab;
      other.setAttribute("aria-selected", selected ? "true" : "false");
      other.tabIndex = selected ? 0 : -1;
      var panel = document.getElementById(other.getAttribute("aria-controls"));
      if (panel) panel.hidden = !selected;
    });
  }

  document.addEventListener("click", function (event) {
    var tab = event.target.closest('[role="tab"]');
    if (tab) {
      selectTab(tab);
      return;
    }
    var add = event.target.closest("[data-add-row]");
    if (add) {
      addRow(add.closest("[data-list-name]"));
      return;
    }
    var remove = event.target.closest("[data-remove-row]");
    if (remove) {
      var fieldset = remove.closest("[data-list-name]");
      remove.closest("[data-row]").remove();
      renumber(fieldset);
      syncCounts(fieldset);
    }
  });

  document.addEventListener("keydown", function (event) {
    var tab = event.target.closest && event.target.closest('[role="tab"]');
    if (!tab || (event.key !== "ArrowRight" && event.key !== "ArrowLeft")) return;
    var tabs = Array.prototype.slice.call(
      tab.closest('[role="tablist"]').querySelectorAll('[role="tab"]')
    );
    var index = tabs.indexOf(tab) + (event.key === "ArrowRight" ? 1 : -1);
    var next = tabs[(index + tabs.length) % tabs.length];
    selectTab(next);
    next.focus();
    event.preventDefault();
  });

  // ------------------------------------------------------------ list inputs
  function makeInput(id, name, testid, value) {
    var input = document.createElement("input");
    input.type = "text";
    input.id = id;
    input.name = name;
    input.value = value || "";
    input.autocomplete = "off";
    input.inputMode = "decimal";
    input.maxLength = 64;
    input.dataset.testid = testid;
    return input;
  }

  function makeLabel(forId, text, sub) {
    var label = document.createElement("label");
    label.htmlFor = forId;
    label.textContent = text;
    var s = document.createElement("sub");
    s.textContent = String(sub);
    label.appendChild(s);
    return label;
  }

  function addRow(fieldset) {
    if (!fieldset) return;
    var rows = fieldset.querySelector("[data-rows]");
    var li = document.createElement("li");
    li.className = "row";
    li.setAttribute("data-row", "");
    if (fieldset.dataset.listKind === "point_list") {
      li.appendChild(document.createElement("label"));
      li.appendChild(makeInput("", "in_" + fieldset.dataset.listName + ".x", "", ""));
      li.appendChild(document.createElement("label"));
      li.appendChild(makeInput("", "in_" + fieldset.dataset.listName + ".y", "", ""));
    } else {
      li.appendChild(document.createElement("label"));
      li.appendChild(makeInput("", "in_" + fieldset.dataset.listName, "", ""));
    }
    var button = document.createElement("button");
    button.type = "button";
    button.className = "icon";
    button.setAttribute("data-remove-row", "");
    button.textContent = "Remove";
    li.appendChild(button);
    rows.appendChild(li);
    renumber(fieldset);
    syncCounts(fieldset);
    var first = li.querySelector("input");
    if (first) first.focus();
  }

  // Re-number ids, labels and data-testids after rows are added or removed.
  function renumber(fieldset) {
    if (!fieldset) return;
    var name = fieldset.dataset.listName;
    var points = fieldset.dataset.listKind === "point_list";
    fieldset.querySelectorAll("[data-row]").forEach(function (row, i) {
      var inputs = row.querySelectorAll("input");
      var labels = row.querySelectorAll("label");
      var suffixes = points ? ["-x", "-y"] : [""];
      var texts = points ? ["x", "y"] : [fieldset.dataset.listLabel || name];
      suffixes.forEach(function (suffix, k) {
        var id = "in-" + name + "-" + i + suffix;
        inputs[k].id = id;
        inputs[k].dataset.testid = "input-" + name + "-" + i + suffix;
        var fresh = makeLabel(id, texts[k], i + 1);
        labels[k].replaceWith(fresh);
      });
      var button = row.querySelector("[data-remove-row]");
      if (button) {
        button.dataset.testid = "remove-row-" + name + "-" + i;
        button.setAttribute("aria-label", "Remove " + (points ? "point " : "entry ") + (i + 1));
      }
    });
  }

  // Keep count fields (data-count-of="<list name>", e.g. Lagrange's N) equal to the number of
  // rows after a row is added or removed. The server still validates N against the rows.
  function syncCounts(fieldset) {
    if (!fieldset) return;
    var form = fieldset.closest("form");
    if (!form) return;
    var name = fieldset.dataset.listName;
    var count = String(fieldset.querySelectorAll("[data-row]").length);
    form.querySelectorAll("[data-count-of]").forEach(function (input) {
      if (input.dataset.countOf !== name || input.value === count) return;
      input.value = count;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  // ------------------------------------------------------------ function / engine coupling
  function syncFunction(form) {
    if (!form) return;
    var select = form.querySelector("[data-function-select]");
    if (!select) return;
    var custom = select.value === "custom";
    var exprNote = form.querySelector("[data-preset-expr]");
    if (exprNote) {
      exprNote.hidden = custom;
      var option = select.options[select.selectedIndex];
      var code = exprNote.querySelector("code");
      if (code && option && option.dataset.expr) code.textContent = option.dataset.expr;
    }
    var note = form.querySelector("[data-custom-note]");
    if (note) note.hidden = !custom;
    var python = form.querySelector('input[name="engine"][value="python"]');
    form.querySelectorAll('input[name="engine"][data-needs-preset]').forEach(function (radio) {
      var unavailable = radio.dataset.unavailable === "true";
      radio.disabled = unavailable || custom;
      if (radio.disabled && radio.checked && python && !python.disabled) python.checked = true;
    });
  }

  document.addEventListener("change", function (event) {
    if (event.target.matches && event.target.matches("[data-function-select]")) {
      syncFunction(event.target.form);
    }
  });

  document.addEventListener("input", function (event) {
    if (event.target.matches && event.target.matches("[data-custom-expr]")) {
      var form = event.target.form;
      var select = form && form.querySelector("[data-function-select]");
      if (select && event.target.value.trim() !== "" && select.value !== "custom") {
        select.value = "custom";
        syncFunction(form);
      }
    }
  });

  function init(root) {
    renderCharts(root);
    var forms = root.querySelectorAll ? root.querySelectorAll("form.run-form") : [];
    forms.forEach(syncFunction);
    if (root.matches && root.matches("form.run-form")) syncFunction(root);
  }

  if (window.htmx) {
    window.htmx.onLoad(init);
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  }
  // Plotly loads deferred after htmx; render anything already on the page once it is ready.
  window.addEventListener("load", function () {
    renderCharts(document);
  });
})();
