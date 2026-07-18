import { computed } from 'vue';
import { state } from '../state.js';

export function useDailyMetrics() {
  const dailyLogs = computed(() => (
    state.logs.filter((log) => log.date === state.selectedDate)
  ));

  const totalCaffeine = computed(() => (
    dailyLogs.value.reduce((sum, log) => sum + Number(log.caffeine || 0), 0)
  ));

  const totalSugar = computed(() => (
    dailyLogs.value.reduce((sum, log) => sum + Number(log.sugarContent || 0), 0)
  ));

  return {
    dailyLogs,
    totalCaffeine,
    totalSugar,
  };
}
