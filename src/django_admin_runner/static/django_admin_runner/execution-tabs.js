/**
 * django-admin-runner — tab fallback for the base Django admin theme.
 *
 * Unfold renders fieldsets with classes=["tab"] as native tabs. The base
 * theme has no such feature; this script builds an equivalent tab bar from
 * those fieldsets. Progressive enhancement: without JS all fieldsets stay
 * visible (stacked).
 */
(function () {
  "use strict";

  var form = document.querySelector("#commandexecution_form, form fieldset");
  if (!form) return;

  var fieldsets = Array.prototype.slice
    .call(document.querySelectorAll("fieldset"))
    .filter(function (fs) {
      return (fs.className || "").split(/\s+/).indexOf("tab") !== -1;
    });
  if (fieldsets.length < 2) return;

  var bar = document.createElement("ul");
  bar.className = "dar-tabs";

  fieldsets.forEach(function (fs, i) {
    var header = fs.querySelector("h2");
    var title = header ? header.textContent : "Tab " + (i + 1);
    var tab = document.createElement("li");
    var link = document.createElement("a");
    link.href = "#";
    link.textContent = title;
    link.addEventListener("click", function (e) {
      e.preventDefault();
      activate(i);
    });
    tab.appendChild(link);
    bar.appendChild(tab);
    if (header) header.style.display = "none";
  });

  function activate(index) {
    Array.prototype.forEach.call(bar.children, function (li, i) {
      li.className = i === index ? "active" : "";
    });
    fieldsets.forEach(function (fs, i) {
      fs.style.display = i === index ? "" : "none";
    });
  }

  var target = fieldsets[0].parentNode;
  target.insertBefore(bar, fieldsets[0]);
  activate(0);
})();
