// ==========================================
// Caffeine and Sugar Tracker - Local Storage Database Manager
// ==========================================

const KEY_LOGS = 'drink_logs_v2';
const KEY_CUSTOM = 'custom_drinks_v2';

/**
 * Loads all logs from LocalStorage
 * @returns {Array} List of logged drinks
 */
export function loadLogs() {
  const data = localStorage.getItem(KEY_LOGS);
  if (!data) {
    // Migrate v1 logs if they exist
    const v1Data = localStorage.getItem('drink_logs');
    if (v1Data) {
      try {
        const v1Logs = JSON.parse(v1Data);
        // Map sugar levels 'half' and 'none' and set default dates
        const migrated = v1Logs.map(log => ({
          ...log,
          // v1 didn't have date, default to today
          date: log.date || new Date().toISOString().split('T')[0],
          // v1 didn't have startTime/endTime, default to fallback values
          startTime: log.startTime || '09:00',
          endTime: log.endTime || '09:30'
        }));
        saveLogs(migrated);
        return migrated;
      } catch (e) {
        return [];
      }
    }
    return [];
  }
  try {
    return JSON.parse(data);
  } catch (e) {
    return [];
  }
}

/**
 * Saves all logs to LocalStorage
 * @param {Array} logs
 */
export function saveLogs(logs) {
  localStorage.setItem(KEY_LOGS, JSON.stringify(logs));
}

/**
 * Loads custom drinks library from LocalStorage
 * @returns {Array} List of custom drinks
 */
export function loadCustomDrinks() {
  const data = localStorage.getItem(KEY_CUSTOM);
  if (!data) {
    // Migrate v1 custom drinks if they exist
    const v1Data = localStorage.getItem('custom_drinks');
    if (v1Data) {
      try {
        const v1Custom = JSON.parse(v1Data);
        saveCustomDrinks(v1Custom);
        return v1Custom;
      } catch (e) {
        return [];
      }
    }
    return [];
  }
  try {
    return JSON.parse(data);
  } catch (e) {
    return [];
  }
}

/**
 * Saves custom drinks library to LocalStorage
 * @param {Array} drinks
 */
export function saveCustomDrinks(drinks) {
  localStorage.setItem(KEY_CUSTOM, JSON.stringify(drinks));
}

/**
 * Adds a drink setup to the custom library
 * @param {Array} drinks - Current library state
 * @param {object} item - Drink to add (brand, name, type, sugar, volume)
 * @returns {Array} Updated custom library state
 */
export function addDrinkToLibrary(drinks, { brand, name, type, sugar, volume }) {
  const exists = drinks.some(d => 
    d.brand === brand && 
    d.name === name && 
    d.type === type && 
    d.sugar === sugar && 
    d.volume === volume
  );

  if (!exists) {
    const newDrinks = [...drinks, {
      id: 'lib_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
      brand,
      name,
      type,
      sugar,
      volume
    }];
    saveCustomDrinks(newDrinks);
    return newDrinks;
  }
  return drinks;
}

/**
 * Filters logs to only return those matching a specific date (YYYY-MM-DD)
 * @param {Array} logs
 * @param {string} dateStr
 * @returns {Array}
 */
export function getLogsForDate(logs, dateStr) {
  return logs.filter(log => log.date === dateStr);
}

/**
 * Gets logs for the past 7 days ending at a specific date
 * @param {Array} logs
 * @param {string} endDateStr - Ending date (YYYY-MM-DD)
 * @returns {Array} List of logs in the range, and an array of 7 date strings (YYYY-MM-DD) representing the week
 */
export function getWeeklyLogs(logs, endDateStr) {
  const endDate = new Date(endDateStr);
  const weekDates = [];
  
  // Generate past 7 dates
  for (let i = 6; i >= 0; i--) {
    const d = new Date(endDate.getTime() - i * 24 * 60 * 60 * 1000);
    weekDates.push(d.toISOString().split('T')[0]);
  }

  const weeklyLogs = logs.filter(log => weekDates.includes(log.date));
  return { weeklyLogs, weekDates };
}
