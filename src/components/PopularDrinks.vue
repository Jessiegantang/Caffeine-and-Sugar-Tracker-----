<script setup>
import { computed } from 'vue';
import { notifyDrinkSelected } from '../app-events.js';
import { getDatabase } from '../drinks-database.js';
import { state } from '../state.js';

const popularIds = [
  'luckin-americano',
  'luckin-coconut-americano',
  'luckin-latte',
  'cotti-americano',
  'starbucks-americano',
  'heytea-milk-tea',
  'mixue-milk-tea',
  'cola',
];

const drinks = computed(() => {
  state.databaseRevision;
  const database = getDatabase();
  if (!database) return [];

  return popularIds.flatMap((drinkId) => {
    for (const [type, category] of Object.entries(database)) {
      const drink = category.items.find((item) => item.id === drinkId);
      if (drink) return [{ ...drink, type }];
    }
    return [];
  });
});

function selectDrink(drink) {
  notifyDrinkSelected({
    kind: 'database',
    drinkId: drink.id,
    drinkType: drink.type,
  });
}
</script>

<template>
  <section class="templates-section card glass">
    <h3 class="card-title">热门饮品</h3>
    <div id="hot-drinks-list" class="templates-list">
      <button
        v-for="drink in drinks"
        :key="`${drink.type}-${drink.id}`"
        type="button"
        class="template-chip"
        @click="selectDrink(drink)"
      >
        <span class="chip-brand">{{ drink.brand }}</span>
        <span class="chip-name">{{ drink.name }}</span>
        <span class="chip-size">{{ drink.defaultVolume }}ml</span>
      </button>
    </div>
  </section>
</template>
