const listEl = document.getElementById("facility-list");
const searchEl = document.getElementById("search");
const villageEl = document.getElementById("village");
const divisionEl = document.getElementById("division");

let facilities = [];

function createOption(value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  return option;
}

function renderFacilities(data) {
  if (!listEl) return;
  listEl.innerHTML = "";

  if (data.length === 0) {
    listEl.innerHTML = `<div class="card muted">找不到符合條件的設施。</div>`;
    return;
  }

  data.forEach((facility) => {
    const card = document.createElement("a");
    card.href = `./facility/${facility.slug}.html`;
    card.className = "card facility-card";
    card.innerHTML = `
      <div class="pill">${facility.village}</div>
      <h3>${facility.name}</h3>
      <div class="muted">${facility.address}</div>
      <div class="stats">
        <span class="stat">容量：${facility.capacity ?? "未提供"}</span>
        <span class="stat">${facility.division || "轄區分局未註明"}</span>
      </div>
    `;
    listEl.appendChild(card);
  });
}

function populateFilters(data) {
  const villages = Array.from(new Set(data.map((item) => item.village))).sort();
  const divisions = Array.from(new Set(data.map((item) => item.division))).sort();

  villages.forEach((village) => villageEl.appendChild(createOption(village, village)));
  divisions.forEach((division) => divisionEl.appendChild(createOption(division, division)));
}

function applyFilters() {
  const term = searchEl.value.trim();
  const village = villageEl.value;
  const division = divisionEl.value;

  const keyword = term.toLowerCase();
  const filtered = facilities.filter((item) => {
    const matchesVillage = village ? item.village === village : true;
    const matchesDivision = division ? item.division === division : true;
    const combined = `${item.name} ${item.address} ${item.village} ${item.division}`.toLowerCase();
    const matchesTerm = keyword ? combined.includes(keyword) : true;
    return matchesVillage && matchesDivision && matchesTerm;
  });

  renderFacilities(filtered);
}

async function boot() {
  try {
    const res = await fetch("./data/facilities.json");
    facilities = await res.json();
    populateFilters(facilities);
    renderFacilities(facilities);
    [searchEl, villageEl, divisionEl].forEach((el) => el?.addEventListener("input", applyFilters));
    [villageEl, divisionEl].forEach((el) => el?.addEventListener("change", applyFilters));
  } catch (err) {
    if (listEl) {
      listEl.innerHTML = `<div class="card muted">載入資料失敗：${err}</div>`;
    }
  }
}

boot();
