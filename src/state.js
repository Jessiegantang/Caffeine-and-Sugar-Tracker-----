import { reactive } from 'vue';

export const state = reactive({
  logs: [],
  customDrinks: [],
  selectedDate: '', // Date currently selected for daily dashboard (YYYY-MM-DD)
  activeTab: 'tab-daily', // 'tab-daily' or 'tab-database'
  calendarMonth: '', // YYYY-MM
  databaseRevision: 0,
  agentAnalysis: null,
  agentStatus: 'idle',
  lastNutritionResult: null
});
