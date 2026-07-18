<script setup>
import { ref } from 'vue';
import { notifyDrinkSelected } from '../app-events.js';
import { searchDrinks } from '../drinks-database.js';

const query = ref('');
const results = ref([]);

function runSearch() {
  const keyword = query.value.trim();
  results.value = keyword ? searchDrinks(keyword) : [];
}

function handleInput() {
  if (query.value.trim().length >= 2) {
    runSearch();
  } else {
    results.value = [];
  }
}

function selectDrink(drink) {
  notifyDrinkSelected({
    kind: 'database',
    drinkId: drink.id,
    drinkType: drink.type,
  });
  query.value = '';
  results.value = [];
}
</script>

<template>
  <section class="drink-search-section card glass">
    <h3 class="card-title">饮品搜索</h3>
    <div class="search-container">
      <input
        id="drink-search-input"
        v-model="query"
        type="search"
        placeholder="搜索饮品名称或品牌..."
        autocomplete="off"
        @input="handleInput"
        @keydown.enter.prevent="runSearch"
      >
      <button id="drink-search-btn" type="button" aria-label="搜索饮品" @click="runSearch">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </button>
    </div>

    <div v-if="results.length" id="drink-search-results" class="search-results">
      <div class="search-results-header">找到 {{ results.length }} 个结果</div>
      <div class="search-results-list">
        <button
          v-for="drink in results"
          :key="`${drink.type}-${drink.id}`"
          type="button"
          class="search-result-item"
          @click="selectDrink(drink)"
        >
          <span class="search-result-brand">{{ drink.brand }}</span>
          <span class="search-result-name">{{ drink.name }}</span>
          <span class="search-result-meta">{{ drink.defaultVolume }}ml</span>
          <span class="search-result-info">☕ {{ drink.caffeine }}mg | 🍬 {{ drink.baseSugar }}g</span>
        </button>
      </div>
    </div>
  </section>
</template>
