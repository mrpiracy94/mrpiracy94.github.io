"use strict";
// Executed in GitHub Actions against BOTH source files and the Pages artifact.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(process.argv[2] || ".");
const script = fs.readFileSync(path.join(root, "assets/site.js"), "utf8");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const catalog = JSON.parse(fs.readFileSync(path.join(root, "index.json"), "utf8"));
new vm.Script(script, {filename: "assets/site.js"}); // Must fail on ANY JS syntax error.
assert.equal(catalog.version, 2);
assert.equal(catalog.apps.length, catalog.app_count);
assert.ok(catalog.app_count > 0, "No catalog entries");
assert.equal(new Set(catalog.apps.map(app => app.id)).size, catalog.app_count);
assert.ok(/id="app-grid"/.test(html), "App grid is missing");
assert.ok(/id="categories"/.test(html), "Categories are missing");
assert.ok(/id="pilot-count"/.test(html), "Pilot app count target is missing");
assert.ok(script.includes('pilotCount.textContent = String(state.apps.length)') ||
          script.includes('pilotCounter.textContent = state.apps.length + " aplicações selecionadas"'),
          "App counter not dynamic");

const begin = script.indexOf("  function safePath(value, extension) {");
const end = script.indexOf("  function element(tag, className, textValue) {", begin);
assert.ok(begin >= 0 && end > begin, "Image resolver missing");
const ctx = vm.createContext({
  URL, base: new URL("https://mrpiracy94.github.io/MrStore/")
});
vm.runInContext(script.slice(begin, end), ctx, {filename: "image-resolver.js"});
const safePath = vm.runInContext("safePath", ctx);
for (const app of catalog.apps) {
  assert.ok(safePath(app.icon), "Catalog logo rejected: " + app.id + " (" + app.icon + ")");
  if (app.icon.startsWith("./assets/catalog-icons/")) {
    assert.ok(fs.existsSync(path.join(root, app.icon)),
              "Cached icon file missing from the Pages artifact: " + app.id);
  }
  if (app.thumbnail) assert.ok(safePath(app.thumbnail), "Screenshot rejected: " + app.id);
  if (app.compose_url) {
    const href = safePath(app.compose_url, ".yml");
    assert.ok(href && href.startsWith("https://mrpiracy94.github.io/MrStore/apps/"),
      "Invalid Compose download: " + app.id);
  }
}
for (const dangerous of [
  "http://evil.example/icon.png", "https://evil.example/icon.png",
  "https://cdn.jsdelivr.net@evil.example/icon.png",
  "/apps/../../etc/passwd", "/apps/test/../secret.png",
  "/apps/test/%2e%2e/secret.png", "javascript:alert(1)",
  "https://raw.githubusercontent.com/other/repo/main/bad.svg",
]) {
  assert.equal(safePath(dangerous), null, "Untrusted icon accepted: " + dangerous);
}
assert.equal(safePath("https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/a.png", ".yml"), null);
const policy = html.match(/Content-Security-Policy" content="([^"]+)"/);
assert.ok(policy, "Missing CSP");
for (const provider of ["https://cdn.jsdelivr.net", "https://raw.githubusercontent.com",
                        "https://seedit4.me"]) {
  assert.ok(policy[1].includes(provider), "CSP blocks provider: " + provider);
}
console.log("PASS: syntax, app catalogue, " + catalog.app_count +
            " image resolutions, Compose paths and CSP");
