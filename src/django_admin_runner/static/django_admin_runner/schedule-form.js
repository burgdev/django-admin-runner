/**
 * django-admin-runner — dynamic kind-conditional fields on schedule forms.
 *
 * Shows only the fields relevant to the selected schedule kind:
 *   cron     → cron expression
 *   interval → interval minutes + repeats
 *   clocked  → run-at datetime
 *
 * Works with the native admin form-row markup, Unfold's layout and the
 * split date/time widgets (run_at_0 / run_at_1 subwidgets).
 * Progressive enhancement: without JS all fields stay visible.
 */
(function () {
  "use strict";

  var KIND_FIELDS = {
    cron: ["cron"],
    interval: ["interval_minutes", "repeats"],
    clocked: ["run_at"],
  };

  function fieldNodes(name) {
    var nodes = [];
    ["", "_0", "_1"].forEach(function (suffix) {
      var el = document.querySelector(
        "#id_" + name + suffix + ', [name="' + name + suffix + '"]',
      );
      if (el) nodes.push(el);
      var lab = document.querySelector('label[for="id_' + name + suffix + '"]');
      if (lab) nodes.push(lab);
    });
    return nodes;
  }

  function containerFor(node, nodes) {
    // Native admin: everything sits inside a .form-row.
    var row = node.closest(".form-row");
    if (row) return row;
    // Split datetime: both subwidgets live in a .datetime wrapper.
    var dt = node.closest(".datetime");
    if (dt) return dt;
    // Unfold: climb until the container also holds the field's label.
    var label = null;
    nodes.forEach(function (n) {
      if (n.tagName === "LABEL") label = n;
    });
    var cur = node.parentElement;
    while (cur && label && !cur.contains(label)) cur = cur.parentElement;
    return cur || node;
  }

  function update() {
    var kind = document.getElementById("id_kind");
    if (!kind) return;
    var active = KIND_FIELDS[kind.value] || [];
    Object.keys(KIND_FIELDS).forEach(function (k) {
      KIND_FIELDS[k].forEach(function (fieldName) {
        var nodes = fieldNodes(fieldName);
        var containers = [];
        nodes.forEach(function (node) {
          var c = containerFor(node, nodes);
          if (containers.indexOf(c) === -1) containers.push(c);
        });
        var show = active.indexOf(fieldName) !== -1;
        containers.forEach(function (c) {
          c.style.display = show ? "" : "none";
        });
      });
    });
  }

  function init() {
    var kind = document.getElementById("id_kind");
    if (!kind) return;
    kind.addEventListener("change", update);
    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
