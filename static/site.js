/* ============ Mapt Daily — interactions ============ */
(function () {
  "use strict";

  // mobile nav
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector(".mainnav .in");
  if (toggle && nav) toggle.addEventListener("click", function () { nav.classList.toggle("open"); });

  // breaking-news ticker rotation
  var ticker = document.querySelector("[data-ticker]");
  if (ticker) {
    var ticks = ticker.querySelectorAll(".tk"), ti = 0;
    if (ticks.length > 1) setInterval(function () {
      ticks[ti].hidden = true; ti = (ti + 1) % ticks.length; ticks[ti].hidden = false;
    }, 4000);
  }

  // dark-mode toggle (persisted)
  var themeBtn = document.querySelector("[data-theme]");
  function applyTheme(t) { document.documentElement.classList.toggle("dark", t === "dark"); }
  try { applyTheme(localStorage.getItem("md-theme")); } catch (e) {}
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var d = !document.documentElement.classList.contains("dark");
    applyTheme(d ? "dark" : "light");
    try { localStorage.setItem("md-theme", d ? "dark" : "light"); } catch (e) {}
  });

  // sidebar Recent/Popular tabs
  document.querySelectorAll(".wtabs").forEach(function (w) {
    w.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        w.querySelectorAll("button").forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on");
        var host = w.parentElement;
        host.querySelectorAll("[data-wp]").forEach(function (panel) {
          panel.hidden = panel.getAttribute("data-wp") !== b.getAttribute("data-wt");
        });
      });
    });
  });

  // "Load More" reveals hidden cards
  var lm = document.querySelector("[data-loadmore]");
  if (lm) lm.addEventListener("click", function () {
    document.querySelectorAll(".hcard.more").forEach(function (c) { c.hidden = false; });
    lm.style.display = "none";
  });

  // reveal on scroll
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
  }, { threshold: 0.1 });
  document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
})();
