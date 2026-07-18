<script setup>
import { computed, ref, watch } from 'vue';
import { addDrink, deleteDrink, getAllDrinks, resetDatabase, updateDrink } from '../drinks-database.js';
import { state } from '../state.js';
import DatabaseDrinkForm from './database/DatabaseDrinkForm.vue';
import DatabaseDrinkModal from './database/DatabaseDrinkModal.vue';
import DatabaseDrinkTable from './database/DatabaseDrinkTable.vue';
import DatabaseImportModal from './database/DatabaseImportModal.vue';
import DatabaseOverview from './database/DatabaseOverview.vue';

const drinks = ref([]);
const query = ref('');
const editingDrink = ref(null);
const importOpen = ref(false);

const customCount = computed(() => drinks.value.filter(drink => String(drink.id).startsWith('custom_')).length);
const filteredDrinks = computed(() => {
  const needle = normalize(query.value);
  if (!needle) return drinks.value;
  return drinks.value.filter(drink => [drink.brand, drink.name, drink.type, drink.caffeine, drink.baseSugar, drink.defaultVolume].some(value => normalize(value).includes(needle)));
});

watch(() => state.databaseRevision, refresh, { immediate: true });

function refresh() {
  drinks.value = getAllDrinks();
}

function notifyChanged() {
  state.databaseRevision += 1;
  refresh();
}

async function addNewDrink(payload) {
  await addDrink(payload.type, payload);
  notifyChanged();
}

async function saveDrink(payload) {
  await updateDrink(payload.id, payload);
  editingDrink.value = null;
  notifyChanged();
}

async function removeDrink(id) {
  if (!window.confirm('确定要删除这个饮品吗？')) return;
  await deleteDrink(id);
  editingDrink.value = null;
  notifyChanged();
}

async function resetAll() {
  if (!window.confirm('确定要重置数据库吗？所有自定义数据将被清除！')) return;
  await resetDatabase();
  notifyChanged();
}

async function importCsv(content) {
  const lines = content.split(/\r?\n/).filter(line => line.trim());
  if (lines.length < 2) return { success: false, message: 'CSV 文件内容为空或只有表头' };
  const validTypes = new Set(['coffee', 'teacoffee', 'tea', 'milktea', 'fruittea', 'soda', 'other']);
  const errors = [];
  let imported = 0;
  for (let index = 1; index < lines.length; index += 1) {
    const [type, brand, name, caffeineText, sugarText, volumeText] = parseCsvLine(lines[index]);
    const caffeine = Number(caffeineText);
    const baseSugar = Number(sugarText);
    const defaultVolume = Number(volumeText);
    if (!validTypes.has(type) || !name?.trim() || !Number.isFinite(caffeine) || !Number.isFinite(baseSugar) || !Number.isFinite(defaultVolume) || defaultVolume <= 0) {
      errors.push(`第 ${index + 1} 行数据无效`);
      continue;
    }
    await addDrink(type, { brand: brand || '', name: name.trim(), caffeine, baseSugar, defaultVolume });
    imported += 1;
  }
  if (imported) notifyChanged();
  const suffix = errors.length ? `；${errors.slice(0, 5).join('；')}${errors.length > 5 ? `（另有 ${errors.length - 5} 条）` : ''}` : '';
  return { success: imported > 0, message: `成功导入 ${imported} 条饮品${suffix}` };
}

function parseCsvLine(line) {
  const values = [];
  let current = '';
  let quoted = false;
  for (const character of line) {
    if (character === '"') quoted = !quoted;
    else if (character === ',' && !quoted) { values.push(current.trim()); current = ''; }
    else current += character;
  }
  values.push(current.trim());
  return values;
}

function normalize(value) {
  return String(value ?? '').trim().toLocaleLowerCase('zh-CN');
}
</script>

<template>
  <DatabaseOverview :total="drinks.length" :custom="customCount" @import="importOpen = true" @reset="resetAll" />
  <DatabaseDrinkForm @submit="addNewDrink" />
  <DatabaseDrinkTable v-model:query="query" :drinks="filteredDrinks" :total="drinks.length" @edit="editingDrink = $event" />
  <DatabaseDrinkModal :drink="editingDrink" @close="editingDrink = null" @save="saveDrink" @delete="removeDrink" />
  <DatabaseImportModal :open="importOpen" :importer="importCsv" @close="importOpen = false" />
</template>
