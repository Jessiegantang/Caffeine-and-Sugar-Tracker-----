<script setup>
import { computed } from 'vue';
import { notifyDateChanged } from '../app-events.js';
import { state } from '../state.js';

const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
const today = getLocalDateString();

if (!state.selectedDate) state.selectedDate = today;
if (!state.calendarMonth) state.calendarMonth = today.slice(0, 7);

const logCounts = computed(() => state.logs.reduce((counts, log) => {
  if (log.date) counts[log.date] = (counts[log.date] || 0) + 1;
  return counts;
}, {}));

const monthParts = computed(() => {
  const [year, month] = state.calendarMonth.split('-').map(Number);
  return { year, month };
});

const monthLabel = computed(() => (
  `${monthParts.value.year}年${monthParts.value.month}月`
));

const calendarDays = computed(() => {
  const { year, month } = monthParts.value;
  const startWeekday = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const daysInMonth = new Date(year, month, 0).getDate();
  const days = Array.from({ length: startWeekday }, (_, index) => ({
    key: `empty-${index}`,
    empty: true,
  }));

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    days.push({
      key: date,
      date,
      day,
      count: logCounts.value[date] || 0,
    });
  }

  return days;
});

function getLocalDateString() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function shiftMonth(delta) {
  const { year, month } = monthParts.value;
  const date = new Date(year, month - 1 + delta, 1);
  state.calendarMonth = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

function selectDate(date) {
  state.selectedDate = date;
  state.calendarMonth = date.slice(0, 7);
  notifyDateChanged(date);
}
</script>

<template>
  <section class="calendar-section card glass">
    <div class="section-header-row calendar-header-row">
      <h3 class="card-title">补录日历</h3>
      <div class="calendar-nav-group">
        <button
          id="calendar-prev-month"
          type="button"
          class="calendar-nav-btn"
          aria-label="上一个月"
          @click="shiftMonth(-1)"
        >
          ←
        </button>
        <span id="calendar-month-label" class="calendar-month-label">{{ monthLabel }}</span>
        <button
          id="calendar-next-month"
          type="button"
          class="calendar-nav-btn"
          aria-label="下一个月"
          @click="shiftMonth(1)"
        >
          →
        </button>
      </div>
    </div>

    <div class="calendar-week-head">
      <span v-for="weekday in weekdays" :key="weekday">{{ weekday }}</span>
    </div>

    <div id="calendar-grid" class="calendar-grid">
      <template v-for="item in calendarDays" :key="item.key">
        <div v-if="item.empty" class="calendar-day empty"></div>
        <button
          v-else
          type="button"
          class="calendar-day"
          :class="{
            selected: item.date === state.selectedDate,
            today: item.date === today,
            'has-data': item.count > 0,
          }"
          :aria-label="`${item.date}${item.count ? `，${item.count}条记录` : ''}`"
          @click="selectDate(item.date)"
        >
          <span>{{ item.day }}</span>
          <small v-if="item.count">{{ item.count }}条</small>
        </button>
      </template>
    </div>

    <p class="calendar-hint">点日期即可切换到该日查看/补录，带小点表示当天有记录。</p>
  </section>
</template>
