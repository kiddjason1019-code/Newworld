(() => {
  const dataTag = document.getElementById("shelter-data");
  const shelters = JSON.parse(dataTag.textContent);
  const results = document.getElementById("results");
  const searchInput = document.getElementById("search");

  const formatNumber = (value) =>
    Number(value).toLocaleString("zh-Hant", { maximumFractionDigits: 0 });

  const render = (items) => {
    results.innerHTML = "";

    if (!items.length) {
      results.innerHTML = `<p class="empty">找不到符合條件的避難設施，請嘗試其他關鍵字。</p>`;
      return;
    }

    for (const item of items) {
      const card = document.createElement("article");
      card.className = "card";
      card.innerHTML = `
        <div class="meta-line">
          <span class="badge">${item.village}</span>
          <span class="capacity">${formatNumber(item.capacity)} 人</span>
        </div>
        <h2>${item.name}</h2>
        <p class="meta-line">${item.address}</p>
        <footer>
          <span class="meta-line">${item.branch}</span>
          <a class="button" href="./facilities/${encodeURIComponent(
            item.slug
          )}/" aria-label="查看 ${item.name} 詳細資訊">詳細頁面</a>
        </footer>
      `;
      results.appendChild(card);
    }
  };

  const search = (term) => {
    const keyword = term.trim();
    if (!keyword) {
      render(shelters);
      return;
    }

    const lowered = keyword.toLowerCase();
    render(
      shelters.filter((item) =>
        [item.name, item.village, item.address, item.branch]
          .join(" ")
          .toLowerCase()
          .includes(lowered)
      )
    );
  };

  searchInput.addEventListener("input", (event) => search(event.target.value));

  render(shelters);
})();
