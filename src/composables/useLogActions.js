import { deleteLogApi } from '../api.js';
import { notifyFormSaved } from '../app-events.js';
import { createOptimisticLog, normalizeDrinkInput } from '../domain/logs.js';
import { state } from '../state.js';
import { addDrinkToLibrary, saveLogs } from '../storage.js';

export function useLogActions({ analyzeLog, refreshDailyInsights }) {
  async function addDrink(formData) {
    const { value, errors } = normalizeDrinkInput(formData);
    if (errors.length) {
      window.alert(`请填写完整信息：\n${errors.join('\n')}`);
      return null;
    }

    const log = createOptimisticLog(value);
    state.logs.push(log);
    saveLogs(state.logs);

    if (value.saveToLibrary) {
      state.customDrinks = addDrinkToLibrary(state.customDrinks, {
        brand: value.brand,
        name: value.name,
        type: value.type,
        sugar: value.sugar,
        volume: value.volume,
      });
    }

    if (state.selectedDate !== value.date) {
      state.selectedDate = value.date;
      state.calendarMonth = value.date.slice(0, 7);
    }
    notifyFormSaved(value.date);
    await analyzeLog(log);
    return log;
  }

  async function deleteLog(id) {
    const previousLogs = state.logs;
    state.logs = state.logs.filter(log => log.id !== id);
    saveLogs(state.logs);
    try {
      await deleteLogApi(id);
      await refreshDailyInsights(state.selectedDate);
      return true;
    } catch (error) {
      state.logs = previousLogs;
      saveLogs(previousLogs);
      console.error('Failed to delete log from backend:', error);
      return false;
    }
  }

  return { addDrink, deleteLog };
}
