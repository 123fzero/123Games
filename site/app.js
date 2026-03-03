const state = {
  data: null,
  query: "",
  filter: "all",
  category: "all",
};

const els = {
  search: document.querySelector("#search"),
  resultCount: document.querySelector("#result-count"),
  featured: document.querySelector("#featured-list"),
  sections: document.querySelector("#catalog-sections"),
  chips: Array.from(document.querySelectorAll(".chip")),
  categoryFilter: document.querySelector("#category-filter"),
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
    return hasOfficial && hasCommunity;
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
  if (state.category === "all") {
    return true;
  }
  return item.section === state.category;
}

function flattenItems(data) {
  const items = [];
  data.sections.forEach((section) => {
    section.subsections.forEach((subsection) => {
      subsection.items.forEach((item) => items.push(item));
    });
  });
  return items;
}

function renderFeatured(data) {
  if (!data.featured.length) {
    els.featured.innerHTML = '<p class="muted">Featured 123fzero apps will appear here after catalog generation.</p>';
    return;
  }

  els.featured.innerHTML = data.featured.map((item) => `
    <article class="featured-card">
      <a href="${item.url}" rel="noopener"><strong>${item.name}</strong></a>
      <div class="badge-line">
        <span class="badge">${item.category}</span>
        ${item.rating ? `<span class="badge">${item.rating}</span>` : ""}
      </div>
      <p>${item.description}</p>
    </article>
  `).join("");
}

function populateCategoryFilter(data) {
  const options = ['<option value="all">All categories</option>'];
  data.sections.forEach((section) => {
    options.push(`<option value="${section.name}">${section.name}</option>`);
  });
  els.categoryFilter.innerHTML = options.join("");
  els.categoryFilter.value = state.category;
}

function renderSections(data) {
  const blocks = [];
  let count = 0;

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
  window.history.replaceState({}, "", url);
}

function render() {
  if (!state.data) {
    return;
  }
  renderFeatured(state.data);
  renderSections(state.data);
  syncUrl();
}

async function loadCatalog() {
  const response = await fetch("catalog.json");
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
  if (initialQuery) {
    state.query = initialQuery;
    els.search.value = url.searchParams.get("q");
  }

  els.search.addEventListener("input", (event) => {
    state.query = normalize(event.target.value);
    render();
  });

  els.chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      els.chips.forEach((candidate) => candidate.classList.remove("active"));
      chip.classList.add("active");
      state.filter = chip.dataset.filter;
      render();
    });
  });

  els.categoryFilter.addEventListener("change", (event) => {
    state.category = event.target.value;
    render();
  });

  loadCatalog().catch((error) => {
    console.error(error);
    els.resultCount.textContent = "Catalog failed to load";
    els.sections.innerHTML = '<div class="empty">Could not load catalog.json. Re-run the generator and redeploy Pages.</div>';
  });
}

init();
