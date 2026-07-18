import { onBeforeUnmount, onMounted, ref } from 'vue';
import * as api from '../api.js';
import {
  DATE_CHANGED_EVENT,
  FORM_SUBMIT_EVENT,
  LOG_DELETE_EVENT,
  onAppEvent,
  SLEEP_SAVED_EVENT,
} from '../app-events.js';
import { loadDatabaseAsync } from '../drinks-database.js';
import { state } from '../state.js';
import { loadCustomDrinks, loadLogs, saveLogs } from '../storage.js';
import { useAgentInsights } from './useAgentInsights.js';
import { useLogActions } from './useLogActions.js';

export function useAppController() {
  const ready = ref(false);
  const initializationError = ref('');
  const agent = useAgentInsights();
  const logs = useLogActions(agent);
  const eventUnsubscribers = [];

  initializeDate();

  const handlers = {
    dateChanged({ date } = {}) {
      if (!date) return;
      state.selectedDate = date;
      state.calendarMonth = date.slice(0, 7);
      agent.refreshDailyInsights(date);
    },
    formSubmit(formData) {
      logs.addDrink(formData);
    },
    logDelete({ id } = {}) {
      if (id) logs.deleteLog(id);
    },
    sleepSaved({ date } = {}) {
      if (date) agent.refreshDailyInsights(date);
    },
  };

  onMounted(async () => {
    registerEvents();
    setupMemoryDebugApi();
    try {
      await loadInitialData();
      await agent.refreshDailyInsights(state.selectedDate);
      ready.value = true;
    } catch (error) {
      initializationError.value = error.message || '应用初始化失败';
      ready.value = true;
    }
  });

  onBeforeUnmount(unregisterEvents);

  async function loadInitialData() {
    await loadDatabaseAsync();
    state.databaseRevision += 1;
    state.customDrinks = loadCustomDrinks();

    const localLogs = loadLogs();
    try {
      const backendLogs = await api.fetchLogsApi();
      if (Array.isArray(backendLogs) && backendLogs.length) {
        state.logs = backendLogs;
        saveLogs(backendLogs);
      } else {
        state.logs = localLogs;
        if (localLogs.length) await api.syncLogsApi(localLogs);
      }
    } catch (error) {
      state.logs = localLogs;
      console.error('Failed to load logs from backend:', error);
    }
  }

  function registerEvents() {
    eventUnsubscribers.push(
      onAppEvent(DATE_CHANGED_EVENT, handlers.dateChanged),
      onAppEvent(FORM_SUBMIT_EVENT, handlers.formSubmit),
      onAppEvent(LOG_DELETE_EVENT, handlers.logDelete),
      onAppEvent(SLEEP_SAVED_EVENT, handlers.sleepSaved),
    );
  }

  function unregisterEvents() {
    eventUnsubscribers.splice(0).forEach(unsubscribe => unsubscribe());
  }

  function setupMemoryDebugApi() {
    window.DrinkMindMemory = {
      list: () => api.fetchUserPreferencesApi(),
      clear: () => api.clearUserPreferencesApi(),
    };
  }

  return { ready, initializationError, ...agent, ...logs };
}

function initializeDate() {
  if (state.selectedDate) return;
  const date = getLocalDateString();
  state.selectedDate = date;
  state.calendarMonth = date.slice(0, 7);
}

function getLocalDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
