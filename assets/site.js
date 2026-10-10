"use strict";
(function () {
  const STORE_URL = "https://mrpiracy94.github.io/MrStore";
  const PREFIX = "io.github.mrpiracy94.";
  const BATCH_SIZE = 12;
  const CATEGORY_LABELS = {
    Media: "Multimédia", Productivity: "Produtividade", Home: "Casa",
    Networking: "Redes", Network: "Redes", Cloud: "Cloud",
    Browser: "Navegadores", Downloader: "Downloads", Games: "Jogos",
    Graphics: "Gráficos", Developer: "Desenvolvimento", AI: "Inteligência artificial",
    Finance: "Finanças", Social: "Social", Utilities: "Utilitários",
    Others: "Outras"
  };
  const CATEGORY_SYMBOLS = { "": "▦", Media: "▣", Productivity: "◈", Home: "⌂", Networking: "⛨", Network: "⛨", Cloud: "☁", Browser: "◉", Downloader: "↓", Games: "✦", Graphics: "▧", Developer: "</>", AI: "✺", Finance: "▤", Social: "◎", Utilities: "⚙", Others: "◇" };
  const $ = (id) => document.getElementById(id);
  const state = { apps: [], filtered: [], category: "", query: "", arch: "",
    favoritesOnly: false, limit: BATCH_SIZE, saved: new Set(), validated: false };
  const base = new URL(STORE_URL + "/");
  function readFavorites() {
    try {
      const value = JSON.parse(localStorage.getItem("mrstore-favorites-v1") || "[]");
      if (Array.isArray(value)) {
        state.saved = new Set(value.filter(function (x) {
          return typeof x === "string" && x.startsWith(PREFIX) && x.length < 160;
        }).slice(0, 300));
      }
    } catch (_) { state.saved = new Set(); }
  }
  function saveFavorites() {
    try { localStorage.setItem("mrstore-favorites-v1", JSON.stringify(Array.from(state.saved))); }
    catch (_) { /* Private mode may reject storage. Favorites still work this session. */ }
  }
  // Só são aceites recursos do catálogo ou de fornecedores identificados.
  // Nunca aceitar URLs arbitrários vindos de metadados externos.
  function safePath(value, extension) {
    if (typeof value !== "string") return null;
    // Original app artwork is mirrored inside this GitHub Pages artifact.
    if (!extension && /^\.\/assets\/catalog-icons\/[0-9a-f]{22}\.(?:png|jpg|gif|webp|svg)$/.test(value)) return value;
    if (!extension) {
      const trustedCDN = /^https:\/\/cdn\.jsdelivr\.net\/gh\/walkxcode\/dashboard-icons\/(?:png|svg)\/[a-zA-Z0-9._-]+\.(?:png|svg)$/;
      const trustedRaw = /^https:\/\/raw\.githubusercontent\.com\/(?:selfhst\/icons|homarr-labs\/dashboard-icons|linuxserver\/docker-templates|dosbox-staging\/dosbox-staging|luanti-org\/luanti|selkies-project\/sealskin)\/[0-9a-f]{40}\/[a-zA-Z0-9._/-]+\.(?:png|svg|webp|gif)$/;
      const trustedSeedit = /^https:\/\/seedit4\.me\/assets\/img\/icons\/software\/[a-zA-Z0-9._-]+\.(?:png|webp)$/;
      const trustedStore = /^https:\/\/raw\.githubusercontent\.com\/mrpiracy94\/MrStore\/main\/Apps\/[a-z0-9._-]+\/icon\.svg$/;
      if (trustedCDN.test(value) || trustedRaw.test(value) || trustedSeedit.test(value) || trustedStore.test(value)) {
        return value;
      }
    }
    if (!value.startsWith("/apps/") || value.includes("..") ||
        value.includes("\\") || value.includes("?") || value.includes("#") ||
        !/^\/apps\/[a-z0-9._-]+\/[a-zA-Z0-9._/-]+$/.test(value)) return null;
    if (extension && !value.toLowerCase().endsWith(extension)) return null;
    const candidate = new URL("." + value, base);
    if (candidate.origin !== base.origin ||
        !candidate.pathname.startsWith(base.pathname + "apps/")) return null;
    return candidate.href;
  }
  function element(tag, className, textValue) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (textValue !== undefined) node.textContent = String(textValue);
    return node;
  }
  function appTitle(app) { return app.title && typeof app.title === "string" ? app.title : app.id.slice(PREFIX.length); }
  function categoryLabel(name) { return CATEGORY_LABELS[name] || name || "Outras"; }
  function setNotice(message, error) {
    const item = $("catalog-alert"); item.hidden = !message;
    item.textContent = message || ""; item.classList.toggle("is-error", Boolean(error));
  }
  function iconNode(app, className) {
    const wrap = element("div", className);
    const src = safePath(app.icon);
    if (src) {
      const img = document.createElement("img");
      img.src = src; img.alt = ""; img.loading = "lazy";
      img.addEventListener("error", function () { img.remove(); wrap.textContent = appTitle(app).charAt(0).toLocaleUpperCase("pt"); }, { once: true });
      wrap.appendChild(img);
    } else wrap.textContent = appTitle(app).charAt(0).toLocaleUpperCase("pt");
    return wrap;
  }
  function categoryList() {
    const counts = new Map();
    state.apps.forEach(function (app) { counts.set(app.category, (counts.get(app.category) || 0) + 1); });
    const list = $("categories"); list.replaceChildren();
    const all = [["", "Todas", state.apps.length]].concat(
      Array.from(counts).sort(function (a, b) {
        return categoryLabel(a[0]).localeCompare(categoryLabel(b[0]), "pt");
      }).map(function (entry) { return [entry[0], categoryLabel(entry[0]), entry[1]]; })
    );
    all.forEach(function (entry) {
      const button = element("button", "chip" + (state.category === entry[0] ? " active" : ""));
      button.type = "button"; button.dataset.category = entry[0];
      button.setAttribute("aria-pressed", String(state.category === entry[0]));
      button.appendChild(element("span", "chip-symbol", CATEGORY_SYMBOLS[entry[0]] || "◇"));
      button.appendChild(element("span", "chip-label", entry[1]));
      button.appendChild(element("span", "count", entry[2] + " aplicações"));
      button.addEventListener("click", function () {
        state.category = entry[0]; state.limit = BATCH_SIZE; categoryList(); render();
      });
      list.appendChild(button);
    });
    $("total-categories").textContent = String(counts.size);
  }
  function fold(value) {
    return String(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt");
  }
  function scoreSearch(app, query) {
    const title = fold(app.title || "");
    const slug = fold(app.id.slice(PREFIX.length));
    const label = fold(app.tagline || "");
    return title.includes(query) || slug.includes(query) ||
      label.includes(query) || fold(categoryLabel(app.category)).includes(query);
  }
  function makeCard(app) {
    const card = element("article", "app-card"), head = element("div", "app-card-head");
    // Screenshot from index.json, with a local icon fallback when unavailable.
    const cover = element("div", "app-card-cover");
    const screenshotURL = safePath(app.thumbnail);
    function coverFallback() {
      cover.classList.add("cover-placeholder");
      cover.replaceChildren(iconNode(app, "cover-placeholder-icon"));
    }
    if (screenshotURL && /\.(?:png|jpe?g|webp|avif)$/i.test(new URL(screenshotURL).pathname)) {
      const shot = document.createElement("img");
      shot.src = screenshotURL;
      shot.loading = "lazy"; shot.decoding = "async"; shot.alt = "";
      shot.addEventListener("error", coverFallback, { once: true });
      cover.appendChild(shot);
    } else coverFallback();
    card.appendChild(cover);
    head.appendChild(iconNode(app, "app-icon"));
    const copy = element("div", "app-header-copy");
    copy.appendChild(element("h3", "", appTitle(app)));
    copy.appendChild(element("span", "app-category", categoryLabel(app.category)));
    head.appendChild(copy);
    const favorite = element("button", "favorite-btn", state.saved.has(app.id) ? "★" : "☆");
    favorite.type = "button";
    favorite.setAttribute("aria-label", (state.saved.has(app.id) ? "Remover dos favoritos: " : "Adicionar aos favoritos: ") + appTitle(app));
    favorite.setAttribute("aria-pressed", String(state.saved.has(app.id)));
    favorite.addEventListener("click", function () {
      if (state.saved.has(app.id)) state.saved.delete(app.id);
      else state.saved.add(app.id);
      saveFavorites(); render();
    });
    head.appendChild(favorite); card.appendChild(head);
    card.appendChild(element("p", "app-desc", app.tagline || "Conhece esta aplicação no catálogo MrStore."));
    const footer = element("div", "app-footer"), arches = element("div", "architectures");
    (app.architectures || []).forEach(function (arch) {
      arches.appendChild(element("span", "architecture", arch.toUpperCase()));
    });
    footer.appendChild(arches);
    const details = element("button", "details-button", "Ver detalhes →");
    details.type = "button"; details.addEventListener("click", function () { openDetails(app); });
    footer.appendChild(details); card.appendChild(footer);
    return card;
  }
  function render() {
    const needle = fold(state.query.trim());
    state.filtered = state.apps.filter(function (app) {
      return (!state.category || app.category === state.category) &&
        (!state.arch || (app.architectures || []).includes(state.arch)) &&
        (!state.favoritesOnly || state.saved.has(app.id)) &&
        (!needle || scoreSearch(app, needle));
    });
    const grid = $("app-grid"), fragment = document.createDocumentFragment();
    state.filtered.slice(0, state.limit).forEach(function (app) { fragment.appendChild(makeCard(app)); });
    grid.replaceChildren(fragment);
    const shown = Math.min(state.limit, state.filtered.length);
    $("results-summary").textContent = state.filtered.length + " resultado(s)";
    $("catalog-state").hidden = state.filtered.length > 0;
    if (!state.filtered.length) {
      $("catalog-state").textContent = "Não encontrámos aplicações com estes filtros. Experimenta outra pesquisa ou categoria.";
    }
    $("clear-filters").disabled = !(state.category || state.arch || state.query.trim() || state.favoritesOnly);
    const more = $("load-more"); more.hidden = shown >= state.filtered.length;
    if (!more.hidden) more.textContent = "Mostrar mais aplicações (" + (state.filtered.length - shown) + " restantes) ↓";
  }
  function openDetails(app) {
    $("details-icon").replaceChildren(iconNode(app, "detail-icon-inner"));
    $("details-title").textContent = appTitle(app);
    $("details-tagline").textContent = app.tagline || "Aplicação self-hosted";
    $("details-category").textContent = categoryLabel(app.category);
    $("details-arches").textContent = (app.architectures || []).map(function (x) { return x.toUpperCase(); }).join(" / ") || "Não indicado";
    $("details-version").textContent = app.version || "Não indicada";
    $("details-developer").textContent = app.developer || "Não indicado";
    // Preview a real screenshot from the verified local catalog, never a remote URL.
    const preview = $("details-preview");
    preview.replaceChildren();
    preview.hidden = true;
    const thumbnail = safePath(app.thumbnail);
    if (thumbnail && /\.(?:png|jpe?g|webp|avif)$/i.test(new URL(thumbnail).pathname)) {
      const screenshot = document.createElement("img");
      screenshot.alt = "Pré-visualização de " + appTitle(app);
      screenshot.loading = "eager"; // Hidden preview containers cannot trigger lazy loads reliably.
      screenshot.decoding = "async";
      screenshot.addEventListener("load", function () { preview.hidden = false; }, { once: true });
      screenshot.addEventListener("error", function () { preview.hidden = true; screenshot.remove(); }, { once: true });
      screenshot.src = thumbnail;
      preview.appendChild(screenshot);
    }
    const compose = $("details-compose"), url = safePath(app.compose_url, ".yml");
    compose.hidden = !url; if (url) compose.href = url;
    const slug = app.id.slice(PREFIX.length);
    $("details-github").href = "https://github.com/mrpiracy94/MrStore/tree/main/Apps/" + encodeURIComponent(slug);
    $("details").showModal();
  }
  function validateIndex(data) {
    if (!data || data.version !== 2 || !Array.isArray(data.apps) ||
        !Number.isInteger(data.app_count) || data.app_count !== data.apps.length) {
      throw new Error("Índice v2 incompleto ou inválido.");
    }
    const seen = new Set();
    for (const app of data.apps) {
      if (!app || typeof app.id !== "string" ||
          !/^io\.github\.mrpiracy94\.[a-z0-9._-]+$/.test(app.id) ||
          seen.has(app.id) || typeof app.title !== "string" ||
          typeof app.category !== "string" || !Array.isArray(app.architectures)) {
        throw new Error("Existem entradas inválidas ou duplicadas no catálogo.");
      }
      seen.add(app.id);
    }
    // Display the original concept's examples first only when they genuinely
    // exist in the approved published index. Never inject extra app records.
    const preferred = ["plex", "immich", "nextcloud", "jellyfin"];
    function rank(app) {
      const index = preferred.indexOf(app.id.slice(PREFIX.length));
      return index < 0 ? preferred.length : index;
    }
    return data.apps.slice().sort(function (a, b) {
      return rank(a) - rank(b) || appTitle(a).localeCompare(appTitle(b), "pt");
    });
  }
  function verifyRelease(release, appList) {
    if (!release || !Array.isArray(release.approved) ||
        !Number.isInteger(release.approved_count) ||
        release.approved_count !== release.approved.length ||
        release.approved_count !== appList.length) return false;
    const expected = new Set(release.approved.map(function (s) { return PREFIX + s; }));
    return expected.size === appList.length && appList.every(function (app) { return expected.has(app.id); });
  }
  async function initialize() {
    $("store-address").textContent = STORE_URL;
    let index;
    try {
      const response = await fetch("./index.json", { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      index = await response.json(); state.apps = validateIndex(index);
    } catch (_) {
      setNotice("Não foi possível carregar o índice da MrStore. O catálogo público pode ainda estar a ser publicado. Consulta o GitHub Actions para o estado do release.", true);
      $("catalog-state").textContent = "Catálogo indisponível.";
      $("results-summary").textContent = "Indisponível"; return;
    }
    $("total-apps").textContent = String(state.apps.length);
    const pilotCounter = $("pilot-count");
    if (pilotCounter) pilotCounter.textContent = state.apps.length + " aplicações selecionadas";
    const previewCounter = $("preview-app-count");
    if (previewCounter) previewCounter.textContent = String(state.apps.length);
    try {
      const reply = await fetch("./release-status.json", { cache: "no-store" });
      if (!reply.ok) throw new Error("Sem relatório de publicação");
      state.validated = verifyRelease(await reply.json(), state.apps);
    } catch (_) { state.validated = false; }
    if (state.validated) {
      setNotice("Catálogo publicado a partir da seleção aprovada pelo processo automático de verificação do MrStore. Um scan sem alertas conhecidos não garante ausência absoluta de vulnerabilidades; confirma os requisitos antes de instalar.", false);
    } else {
      setNotice("Esta edição pública não inclui evidência completa de quarentena, ou existe uma divergência entre o índice e os relatórios. Podes consultar as fichas, mas NÃO interpretes estas aplicações como aprovadas pelos scanners atuais. Verifica os relatórios no GitHub antes de instalar.", true);
    }
    categoryList(); render();
  }
  $("search").addEventListener("input", function (event) { state.query = event.target.value; state.limit = BATCH_SIZE; render(); });
  $("architecture").addEventListener("change", function (event) { state.arch = event.target.value; state.limit = BATCH_SIZE; render(); });
  $("favorites-toggle").addEventListener("click", function () {
    state.favoritesOnly = !state.favoritesOnly;
    $("favorites-toggle").setAttribute("aria-pressed", String(state.favoritesOnly));
    state.limit = BATCH_SIZE; render();
  });
  $("clear-filters").addEventListener("click", function () {
    state.category = ""; state.arch = ""; state.query = ""; state.favoritesOnly = false;
    state.limit = BATCH_SIZE;
    $("search").value = "";
    $("architecture").value = "";
    $("favorites-toggle").setAttribute("aria-pressed", "false");
    categoryList(); render();
    $("search").focus();
  });
  $("load-more").addEventListener("click", function () { state.limit += BATCH_SIZE; render(); });
  $("details-close").addEventListener("click", function () { $("details").close(); });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
    if (document.activeElement && ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if ($("details").open) return;
    event.preventDefault(); $("search").focus();
  });
  $("copy-store").addEventListener("click", async function () {
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard não disponível");
      await navigator.clipboard.writeText(STORE_URL);
      $("copy-feedback").textContent = "Endereço copiado!";
    } catch (_) { $("copy-feedback").textContent = "Seleciona e copia o endereço manualmente."; }
  });
  // A pesquisa do cabeçalho conduz ao filtro real do catálogo.
  const navSearch = document.querySelector(".nav-search");
  if (navSearch) navSearch.addEventListener("click", function () {
    window.setTimeout(function () { $("search").focus({ preventScroll: true }); }, 60);
  });
  // Fecha o menu móvel ao navegar para uma secção.
  const mobileNav = document.querySelector(".mobile-nav");
  if (mobileNav) mobileNav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () { mobileNav.open = false; });
  });
  readFavorites(); initialize();
})();
