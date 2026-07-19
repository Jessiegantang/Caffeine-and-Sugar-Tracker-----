<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import {
  ADD_PARSED_INTAKE_EVENT,
  DRINK_SELECTED_EVENT,
  FORM_SAVED_EVENT,
  INTAKE_PARSED_EVENT,
  notifyFormSubmit,
  onAppEvent,
} from '../app-events.js';
import { getDrinkById } from '../drinks-database.js';
import { state } from '../state.js';

const brandSuggestions = ['瑞幸咖啡', '库迪咖啡', '喜茶', '奈雪的茶', '星巴克', '蜜雪冰城', '霸王茶姬', '茶颜悦色'];
const drinkTypes = [
  ['coffee', '☕ 咖啡'],
  ['teacoffee', '🥥 茶咖'],
  ['tea', '🍵 原叶茶'],
  ['milktea', '🧋 奶茶'],
  ['fruittea', '🍋 果茶'],
  ['soda', '🥤 汽水'],
  ['other', '其他'],
];
const sugarLevels = [
  ['unknown', '未知(估算)'],
  ['none', '不另加糖 (0%)'],
  ['three', '三分 (30%)'],
  ['half', '半糖 (50%)'],
  ['seven', '七分 (70%)'],
  ['full', '全糖 (100%)'],
];

const highlighted = ref(false);
const form = reactive(createInitialForm());
const eventUnsubscribers = [];

watch(() => state.selectedDate, (date) => {
  if (date) form.date = date;
});

onMounted(() => {
  eventUnsubscribers.push(
    onAppEvent(DRINK_SELECTED_EVENT, handleDrinkSelection),
    onAppEvent(FORM_SAVED_EVENT, handleFormSaved),
    onAppEvent(INTAKE_PARSED_EVENT, handleParsedIntake),
    onAppEvent(ADD_PARSED_INTAKE_EVENT, handleParsedAndSubmit),
  );
});

onBeforeUnmount(() => {
  eventUnsubscribers.splice(0).forEach(unsubscribe => unsubscribe());
});

function createInitialForm(date = state.selectedDate) {
  const { startTime, endTime } = getDefaultTimes();
  return {
    date: date || getLocalDateString(),
    brand: '',
    name: '',
    type: 'coffee',
    sugar: 'unknown',
    volume: 500,
    startTime,
    endTime,
    saveToLibrary: false,
  };
}

function getLocalDateString() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatTime(date) {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function getDefaultTimes() {
  const now = new Date();
  return {
    startTime: formatTime(now),
    endTime: formatTime(new Date(now.getTime() + 30 * 60 * 1000)),
  };
}

function setCurrentTime(field) {
  form[field] = formatTime(new Date());
}

function normalizeType(type) {
  const key = String(type || '').toLowerCase().replaceAll('-', '_').trim();
  const aliases = {
    americano: 'coffee',
    latte: 'coffee',
    coconut_latte: 'coffee',
    oat_latte: 'coffee',
    mocha: 'coffee',
    tea_coffee: 'teacoffee',
    pure_tea: 'tea',
    milk_tea: 'milktea',
    fruit_tea: 'fruittea',
    packaged: 'soda',
    energy_drink: 'soda',
  };
  return drinkTypes.some(([value]) => value === key) ? key : (aliases[key] || 'coffee');
}

function normalizeSugar(sugar) {
  const key = String(sugar || '').toLowerCase().replaceAll('-', '_').trim();
  const aliases = {
    no: 'none',
    no_sugar: 'none',
    zero: 'none',
    zero_sugar: 'none',
    unsweetened: 'none',
    less: 'three',
    low: 'three',
    normal: 'full',
  };
  const normalized = aliases[key] || key;
  return sugarLevels.some(([value]) => value === normalized) ? normalized : 'unknown';
}

function populateForm(data) {
  form.brand = data.brand || '';
  form.name = data.name || '';
  form.type = normalizeType(data.type);
  form.sugar = normalizeSugar(data.sugar);
  form.volume = Number(data.volume || data.defaultVolume || 500);
  highlighted.value = true;
  window.setTimeout(() => {
    highlighted.value = false;
  }, 500);
}

function handleDrinkSelection(selection) {
  if (selection?.kind === 'database') {
    const drink = getDrinkById(selection.drinkId);
    if (!drink) return;
    populateForm({ ...drink, type: selection.drinkType, sugar: 'none', volume: drink.defaultVolume });
  } else if (selection?.kind === 'custom' && selection.drink) {
    populateForm(selection.drink);
  }
}

function applyParsedIntake(parsedIntake) {
  if (!parsedIntake || parsedIntake.intent !== 'log_drink') return false;
  if (parsedIntake.missing_fields?.length) return false;

  populateForm({
    brand: parsedIntake.brand || '',
    name: parsedIntake.name,
    type: parsedIntake.type || 'coffee',
    sugar: parsedIntake.sugar || 'unknown',
    volume: parsedIntake.volume || 500,
  });
  form.date = state.selectedDate;

  if (parsedIntake.time === 'now') {
    const current = formatTime(new Date());
    form.startTime = current;
    form.endTime = current;
  } else if (/^\d{2}:\d{2}$/.test(parsedIntake.time || '')) {
    form.startTime = parsedIntake.time;
    form.endTime = parsedIntake.time;
  }
  return true;
}

function handleParsedIntake(parsedIntake) {
  applyParsedIntake(parsedIntake);
}

async function handleParsedAndSubmit(parsedIntake) {
  if (!applyParsedIntake(parsedIntake)) return;
  await nextTick();
  submitForm();
}

function submitForm() {
  notifyFormSubmit({ ...form });
}

function handleFormSaved({ date } = {}) {
  Object.assign(form, createInitialForm(date));
}
</script>

<template>
  <section class="form-section card glass" :class="{ 'form-section-highlight': highlighted }">
    <h3 class="card-title">录入新饮品</h3>
    <form id="drink-form" autocomplete="off" @submit.prevent="submitForm">

      <div class="form-group">
        <label for="input-date">饮用日期 <span class="required">*</span></label>
        <input id="input-date" v-model="form.date" type="date" required>
      </div>

      <div class="form-row">
        <div class="form-group flex-1">
          <label for="input-brand">品牌 <span class="label-note">(选填)</span></label>
          <input id="input-brand" v-model.trim="form.brand" type="text" placeholder="例如：瑞幸、喜茶" list="brand-suggestions">
          <datalist id="brand-suggestions">
            <option v-for="brand in brandSuggestions" :key="brand" :value="brand"></option>
          </datalist>
        </div>
        <div class="form-group flex-2">
          <label for="input-name">饮品名称 <span class="required">*</span></label>
          <input id="input-name" v-model.trim="form.name" type="text" minlength="2" placeholder="例如：冰美式、芝芝莓莓" required>
        </div>
      </div>

      <div class="form-group">
        <label>饮品类型 <span class="required">*</span></label>
        <div class="radio-chips-group">
          <label v-for="([value, label]) in drinkTypes" :key="value" class="radio-chip">
            <input v-model="form.type" type="radio" name="drink-type" :value="value">
            <span class="chip-label">{{ label }}</span>
          </label>
        </div>
      </div>

      <div class="form-group">
        <label>糖度等级 <span class="required">*</span></label>
        <div class="radio-chips-group sugar-chips">
          <label v-for="([value, label]) in sugarLevels" :key="value" class="radio-chip">
            <input v-model="form.sugar" type="radio" name="sugar-level" :value="value">
            <span class="chip-label">{{ label }}</span>
          </label>
        </div>
        <p class="calendar-hint">提示：不另外加糖 ≠ 0糖。拿铁/生椰/果汁基底等仍会有本身糖分。</p>
      </div>

      <div class="form-group">
        <label for="input-volume">容量 (毫升 ml) <span class="required">*</span></label>
        <div class="input-with-presets">
          <input id="input-volume" v-model.number="form.volume" type="number" min="10" max="2000" required>
          <span class="input-suffix">ml</span>
        </div>
        <div class="preset-volumes-row">
          <button type="button" class="volume-preset-btn" @click="form.volume = 350">中杯 (350ml)</button>
          <button type="button" class="volume-preset-btn" @click="form.volume = 500">大杯 (500ml)</button>
          <button type="button" class="volume-preset-btn" @click="form.volume = 650">超大杯 (650ml)</button>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group flex-1">
          <label for="input-start-time">开始时间 <span class="required">*</span></label>
          <div class="time-input-group">
            <input id="input-start-time" v-model="form.startTime" type="time" required>
            <button id="start-time-now" type="button" class="time-now-btn" @click="setCurrentTime('startTime')">现在</button>
          </div>
        </div>
        <div class="form-group flex-1">
          <label for="input-end-time">预计喝完 <span class="required">*</span></label>
          <div class="time-input-group">
            <input id="input-end-time" v-model="form.endTime" type="time" required>
            <button id="end-time-now" type="button" class="time-now-btn" @click="setCurrentTime('endTime')">现在</button>
          </div>
        </div>
      </div>

      <div class="form-footer-row">
        <label class="checkbox-container">
          <input id="save-to-library" v-model="form.saveToLibrary" type="checkbox">
          <span class="checkmark"></span>
          同时保存到常用饮品库
        </label>
        <button type="submit" class="submit-btn">
          <svg class="btn-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          添加摄入记录
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.form-section {
  transition: border-color 0.2s ease;
}

.form-section-highlight {
  border-color: var(--caffeine-primary);
}
</style>
