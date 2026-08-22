// Platformnavigatie (minimaal niveau, D-021/D-022). De hub woont per
// conventie op poort 8600 van deze machine. Eén poging per paginalading;
// geen hub = geen balk — de tool is volledig autonoom.
(async () => {
  const hub = `${location.protocol}//${location.hostname}:8600`;
  let tools;
  try {
    tools = await (await fetch(`${hub}/api/tools`)).json();
  } catch {
    return; // hub niet bereikbaar: niets tonen (autonoom)
  }
  const bar = document.createElement("div");
  bar.style.cssText =
    "background:#1f2937;color:#e5e7eb;font:0.85rem " +
    "-apple-system,sans-serif;padding:0.4rem 1rem;display:flex;gap:1rem;" +
    "align-items:center;flex-wrap:wrap;";
  const home = document.createElement("a");
  home.href = hub;
  home.textContent = "⌂ platform";
  home.style.cssText = "color:#93c5fd;text-decoration:none;font-weight:600;";
  bar.append(home);
  for (const t of tools) {
    if (!t.name) continue;
    const a = document.createElement("a");
    a.href = t.url.startsWith("http") ? t.url : hub + t.url;
    a.textContent = t.title;
    a.style.cssText =
      "color:#e5e7eb;text-decoration:none;" +
      (t.name === "housedata" ? "font-weight:700;" : "opacity:0.8;");
    bar.append(a);
  }
  document.body.prepend(bar);
})();
