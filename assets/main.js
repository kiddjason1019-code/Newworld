const searchInput = document.querySelector('#search');
const precinctSelect = document.querySelector('#precinct-filter');
const sortSelect = document.querySelector('#sort');
const grid = document.querySelector('#card-grid');
const cards = Array.from(document.querySelectorAll('[data-card]'));
const resultCount = document.querySelector('#result-count');

function normalize(text) {
  return text.toLowerCase();
}

function applyFilters() {
  const term = normalize(searchInput?.value ?? '');
  const precinct = precinctSelect?.value ?? '';
  const sort = sortSelect?.value ?? 'default';

  let filtered = cards.filter((card) => {
    const name = normalize(card.dataset.name || '');
    const address = normalize(card.dataset.address || '');
    const precinctValue = card.dataset.precinct || '';

    const matchesTerm = term === '' || name.includes(term) || address.includes(term);
    const matchesPrecinct = precinct === '' || precinctValue === precinct;
    return matchesTerm && matchesPrecinct;
  });

  if (sort === 'capacity-desc' || sort === 'capacity-asc') {
    filtered.sort((a, b) => {
      const capA = Number(a.dataset.capacity || '0');
      const capB = Number(b.dataset.capacity || '0');
      return sort === 'capacity-desc' ? capB - capA : capA - capB;
    });
  } else {
    filtered.sort((a, b) => Number(a.dataset.index) - Number(b.dataset.index));
  }

  grid.innerHTML = '';
  filtered.forEach((card) => grid.appendChild(card));

  if (resultCount) {
    resultCount.textContent = `顯示 ${filtered.length} 筆避難設施，共 ${cards.length} 筆資料。`;
  }
}

function setup() {
  if (!grid || cards.length === 0) return;
  searchInput?.addEventListener('input', applyFilters);
  precinctSelect?.addEventListener('change', applyFilters);
  sortSelect?.addEventListener('change', applyFilters);
  applyFilters();
}

document.addEventListener('DOMContentLoaded', setup);
