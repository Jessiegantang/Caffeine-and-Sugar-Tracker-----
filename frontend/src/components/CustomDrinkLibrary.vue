<script setup>
import { notifyDrinkSelected } from '../app-events.js';
import { saveCustomDrinks } from '../storage.js';
import { state } from '../state.js';

function selectDrink(drink) {
  notifyDrinkSelected({ kind: 'custom', drink });
}

function deleteDrink(id) {
  state.customDrinks = state.customDrinks.filter((drink) => drink.id !== id);
  saveCustomDrinks(state.customDrinks);
}

function getSugarLabel(sugar) {
  const labels = {
    none: '不另外加糖 (0%)',
    unknown: '糖分未知 (自动估算)',
    three: '三分糖 (30%)',
    half: '半糖 (50%)',
    seven: '七分糖 (70%)',
    full: '全糖 (100%)',
  };
  return labels[sugar] || '未知';
}
</script>

<template>
  <section class="custom-library-section card glass">
    <div class="section-header-row">
      <h3 class="card-title">我的常用饮品库</h3>
      <span id="library-count" class="badge count-badge">{{ state.customDrinks.length }}</span>
    </div>

    <div class="library-list-container">
      <div v-if="!state.customDrinks.length" id="library-empty" class="library-empty-msg">
        <p>暂无常用饮品，可在录入表单勾选保存</p>
      </div>

      <div v-else id="library-grid" class="library-grid">
        <div
          v-for="drink in state.customDrinks"
          :key="drink.id"
          class="library-item"
          role="button"
          tabindex="0"
          @click="selectDrink(drink)"
          @keydown.enter="selectDrink(drink)"
          @keydown.space.prevent="selectDrink(drink)"
        >
          <span class="chip-brand">{{ drink.brand || '自选' }}</span>
          <span class="chip-name">{{ drink.name }}</span>
          <span class="chip-size">{{ drink.volume }}ml ({{ getSugarLabel(drink.sugar) }})</span>
          <button
            type="button"
            class="library-item-del-btn"
            title="删除此常用饮品"
            aria-label="删除此常用饮品"
            @click.stop="deleteDrink(drink.id)"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
