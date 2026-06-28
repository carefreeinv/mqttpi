/* Mermaid rendering for MkDocs Material (instant navigation + theme toggle). */
(function () {
  function mermaidTheme() {
    var scheme = document.body.getAttribute("data-md-color-scheme");
    return scheme === "slate" ? "dark" : "default";
  }

  function renderMermaid() {
    if (typeof mermaid === "undefined") {
      return;
    }

    mermaid.initialize({
      startOnLoad: false,
      theme: mermaidTheme(),
      securityLevel: "loose",
      flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis" },
    });

    var nodes = document.querySelectorAll(".mermaid:not([data-processed])");
    nodes.forEach(function (el, index) {
      var graph = el.textContent.trim();
      if (!graph) {
        return;
      }

      var id = "mqttpi-mermaid-" + index + "-" + Date.now();
      mermaid
        .render(id, graph)
        .then(function (result) {
          el.innerHTML = result.svg;
          el.setAttribute("data-processed", "true");
        })
        .catch(function (err) {
          console.error("Mermaid render failed:", err);
        });
    });
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(renderMermaid);
  } else {
    document.addEventListener("DOMContentLoaded", renderMermaid);
  }
})();