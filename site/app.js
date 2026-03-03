const state = {
  data: null,
  query: "",
  filter: "all",
  categories: [],
};

const els = {
  search: document.querySelector("#search"),
  resetFilters: document.querySelector("#reset-filters"),
  resetCategories: document.querySelector("#reset-categories"),
  resultCount: document.querySelector("#result-count"),
  sections: document.querySelector("#catalog-sections"),
  chips: Array.from(document.querySelectorAll(".chip")),
  categoryFilterList: document.querySelector("#category-filter-list"),
};

function normalize(text) {
  return String(text || "").toLowerCase();
}

function itemMatchesFilter(item) {
  const hasOfficial = item.sourceBadges.includes("official");
  const hasCommunity = item.sourceBadges.includes("community");

  if (state.filter === "official") {
    return hasOfficial && !hasCommunity;
  }
  if (state.filter === "community") {
    return hasCommunity && !hasOfficial;
  }
  if (state.filter === "both") {
    return hasOfficial || hasCommunity;
  }
  return true;
}

function itemMatchesQuery(item) {
  if (!state.query) {
    return true;
  }

  const haystack = [
    item.name,
    item.description,
    item.author,
    item.section,
    item.subsection,
  ].map(normalize).join(" ");

  return haystack.includes(state.query);
}

function itemMatchesCategory(item) {
  if (!state.categories.length) {
    return true;
  }
  return state.categories.includes(item.section);
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function populateCategoryFilter(data) {
  const options = [];
  data.sections.forEach((section) => {
    const itemCount = section.subsections.reduce(
      (total, subsection) => total + subsection.items.length,
      0
    );
    const checked = state.categories.includes(section.name) ? "checked" : "";
    options.push(`
      <label class="check-item">
        <span class="check-main">
          <input type="checkbox" value="${section.name}" ${checked}>
          <span>${section.name}</span>
        </span>
        <span class="check-count">${itemCount}</span>
      </label>
    `);
  });
  els.categoryFilterList.innerHTML = options.join("");

  Array.from(els.categoryFilterList.querySelectorAll("input[type='checkbox']")).forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      state.categories = Array.from(
        els.categoryFilterList.querySelectorAll("input[type='checkbox']:checked")
      ).map((input) => input.value);
      render();
      scrollToTop();
    });
  });
}

function renderSections(data) {
  const blocks = [];
  let count = 0;

  const featuredItems = data.featured.filter((item) => {
    if (!state.query) {
      return true;
    }
    return normalize(item.name).includes(state.query);
  });

  if (!state.categories.length && featuredItems.length) {
    const featuredCards = featuredItems.map((item) => `
      <article class="featured-card">
        <a href="${item.url}" rel="noopener"><strong>${item.name}</strong></a>
        <div class="badge-line">
          <span class="badge">${item.category}</span>
          ${item.rating ? `<span class="badge">${item.rating}</span>` : ""}
        </div>
        <p>${item.description}</p>
      </article>
    `).join("");

    blocks.push(`
      <section class="section-block">
        <h3>Featured 123fzero</h3>
        <div class="featured-list featured-grid">${featuredCards}</div>
      </section>
    `);
  }

  data.sections.forEach((section) => {
    const subsectionBlocks = [];

    section.subsections.forEach((subsection) => {
      const items = subsection.items.filter(
        (item) => itemMatchesFilter(item) && itemMatchesCategory(item) && itemMatchesQuery(item)
      );

      if (!items.length) {
        return;
      }

      count += items.length;
      const cards = items.map((item) => `
        <article class="app-card">
          <div class="app-top">
            <div>
              <h4 class="app-name">
                <a href="${item.repoUrl || item.officialUrl || item.communityUrl}" rel="noopener">${item.name}</a>
              </h4>
              <div class="badge-line">
                <span class="badge">${item.sourceIcons}</span>
                ${item.rating ? `<span class="badge">${item.rating}</span>` : ""}
              </div>
            </div>
          </div>
          <p class="app-description">${item.description}</p>
          <div class="meta">
            ${item.author ? `<span>Author: ${
              item.authorUrl
                ? `<a href="${item.authorUrl}" rel="noopener">${item.author}</a>`
                : item.author
            }</span>` : ""}
            ${item.subsection ? `<span>${item.subsection}</span>` : ""}
          </div>
          <div class="link-row">
            ${item.links.official ? `<a href="${item.links.official}" rel="noopener">Official</a>` : ""}
            ${item.links.github ? `<a href="${item.links.github}" rel="noopener">GitHub</a>` : ""}
            ${item.links.community ? `<a href="${item.links.community}" rel="noopener">Community</a>` : ""}
          </div>
        </article>
      `).join("");

      subsectionBlocks.push(`
        <section class="subsection-block">
          ${subsection.name ? `<h4>${subsection.name}</h4>` : ""}
          <div class="grid">${cards}</div>
        </section>
      `);
    });

    if (!subsectionBlocks.length) {
      return;
    }

    blocks.push(`
      <section class="section-block">
        <h3>${section.name}</h3>
        ${subsectionBlocks.join("")}
      </section>
    `);
  });

  if (!blocks.length) {
    els.sections.innerHTML = '<div class="empty">No catalog entries match this search. Try a different term or source filter.</div>';
  } else {
    els.sections.innerHTML = blocks.join("");
  }

  els.resultCount.textContent = `${count} matching entries`;
}

function syncUrl() {
  const url = new URL(window.location.href);
  if (state.query) {
    url.searchParams.set("q", state.query);
  } else {
    url.searchParams.delete("q");
  }
  if (state.filter !== "all") {
    url.searchParams.set("source", state.filter);
  } else {
    url.searchParams.delete("source");
  }
  if (state.categories.length) {
    url.searchParams.set("categories", state.categories.join(","));
  } else {
    url.searchParams.delete("categories");
  }
  window.history.replaceState({}, "", url);
}

function syncFilterUi() {
  els.chips.forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.filter === state.filter);
  });

  els.resetCategories.hidden = state.categories.length === 0;

  if (!els.categoryFilterList) {
    return;
  }

  Array.from(els.categoryFilterList.querySelectorAll("input[type='checkbox']")).forEach((checkbox) => {
    checkbox.checked = state.categories.includes(checkbox.value);
  });
}

function resetFilters() {
  state.query = "";
  state.filter = "all";
  state.categories = [];
  els.search.value = "";
  syncFilterUi();
  render();
}

function resetCategories() {
  state.categories = [];
  syncFilterUi();
  render();
  scrollToTop();
}

function render() {
  if (!state.data) {
    return;
  }
  syncFilterUi();
  renderSections(state.data);
  syncUrl();
}

function getCatalogUrl() {
  let basePath = window.location.pathname;

  if (basePath.endsWith("/index.html")) {
    basePath = basePath.slice(0, -"/index.html".length);
  }

  if (!basePath.endsWith("/")) {
    basePath = `${basePath}/`;
  }

  return `${window.location.origin}${basePath}catalog.json`;
}

async function loadCatalog() {
  const response = await fetch(getCatalogUrl());
  if (!response.ok) {
    throw new Error(`Failed to load catalog: ${response.status}`);
  }
  state.data = await response.json();
  populateCategoryFilter(state.data);
  render();
}

function init() {
  const url = new URL(window.location.href);
  const initialQuery = normalize(url.searchParams.get("q"));
  const initialFilter = normalize(url.searchParams.get("source"));
  const initialCategories = url.searchParams.get("categories");
  if (initialQuery) {
    state.query = initialQuery;
    els.search.value = url.searchParams.get("q");
  }
  if (["official", "community", "both"].includes(initialFilter)) {
    state.filter = initialFilter;
  }
  if (initialCategories) {
    state.categories = initialCategories
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
  }

  els.search.addEventListener("input", (event) => {
    state.query = normalize(event.target.value);
    render();
  });

  els.chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      state.filter = chip.dataset.filter;
      syncFilterUi();
      render();
    });
  });

  els.resetFilters.addEventListener("click", resetFilters);
  els.resetCategories.addEventListener("click", resetCategories);
  syncFilterUi();

  loadCatalog().catch((error) => {
    console.error(error);
    els.resultCount.textContent = "Catalog failed to load";
    els.sections.innerHTML = '<div class="empty">Could not load catalog.json. Re-run the generator and redeploy Pages.</div>';
  });
}

init();
