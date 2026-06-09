export const state = {
  logs: [],
  customDrinks: [],
  selectedDate: '', // Date currently selected for daily dashboard (YYYY-MM-DD)
  activeTab: 'tab-daily', // 'tab-daily' or 'tab-weekly'
  calendarMonth: '', // YYYY-MM
  currentDrinkFromDatabase: null, // Stores the reference to a db drink if selected
  lastNutritionResult: null
};

export function getElementByIdSafe(id, defaultValue = null) {
  const element = document.getElementById(id);
  return element || defaultValue;
}

export const elements = {
  form: getElementByIdSafe('drink-form'),
  inputDate: getElementByIdSafe('input-date'),
  inputBrand: getElementByIdSafe('input-brand'),
  inputName: getElementByIdSafe('input-name'),
  inputVolume: getElementByIdSafe('input-volume'),
  inputStartTime: getElementByIdSafe('input-start-time'),
  inputEndTime: getElementByIdSafe('input-end-time'),
  inputBaseSugarOverride: getElementByIdSafe('input-base-sugar-override'),
  saveToLibrary: getElementByIdSafe('save-to-library'),
  startTimeNow: getElementByIdSafe('start-time-now'),
  endTimeNow: getElementByIdSafe('end-time-now'),
  
  // Search Elements
  drinkSearchInput: getElementByIdSafe('drink-search-input'),
  drinkSearchBtn: getElementByIdSafe('drink-search-btn'),
  drinkSearchResults: getElementByIdSafe('drink-search-results'),
  hotDrinksList: getElementByIdSafe('hot-drinks-list'),
  
  caffeineTotal: getElementByIdSafe('caffeine-total'),
  sugarTotal: getElementByIdSafe('sugar-total'),
  alcoholTotal: getElementByIdSafe('alcohol-total'),
  caffeineProgress: getElementByIdSafe('caffeine-progress'),
  sugarProgress: getElementByIdSafe('sugar-progress'),
  
  libraryCount: getElementByIdSafe('library-count'),
  libraryGrid: getElementByIdSafe('library-grid'),
  libraryEmpty: getElementByIdSafe('library-empty'),
  
  logsCount: getElementByIdSafe('logs-count'),
  logsGrid: getElementByIdSafe('logs-list'),
  logsEmpty: getElementByIdSafe('logs-empty'),
  
  insightsList: getElementByIdSafe('insights-list'),
  filterDate: getElementByIdSafe('filter-date'),
  calendarGrid: getElementByIdSafe('calendar-grid'),
  calendarMonthLabel: getElementByIdSafe('calendar-month-label'),
  calendarPrevMonth: getElementByIdSafe('calendar-prev-month'),
  calendarNextMonth: getElementByIdSafe('calendar-next-month'),
  
  // Weekly Tab
  weeklyCaffeineTotal: getElementByIdSafe('weekly-caffeine-total'),
  weeklySugarTotal: getElementByIdSafe('weekly-sugar-total'),
  weeklyAlcoholTotal: getElementByIdSafe('weekly-alcohol-total'),
  weeklyActiveDays: getElementByIdSafe('weekly-active-days'),
  weeklyChartContainer: getElementByIdSafe('weekly-chart-container'),
  weeklyInsightsList: getElementByIdSafe('weekly-insights-list'),
  
  // Database Management
  dbTotalCount: getElementByIdSafe('db-total-count'),
  dbCustomCount: getElementByIdSafe('db-custom-count'),
  dbResetBtn: getElementByIdSafe('db-reset-btn'),
  dbImportBtn: getElementByIdSafe('db-import-btn'),
  addDrinkForm: getElementByIdSafe('add-drink-form'),
  drinksTableBody: getElementByIdSafe('drinks-table-body'),
  editDrinkModal: getElementByIdSafe('edit-drink-modal'),
  modalCloseBtn: getElementByIdSafe('modal-close-btn'),
  editDrinkForm: getElementByIdSafe('edit-drink-form'),
  editDeleteBtn: getElementByIdSafe('edit-delete-btn'),
  
  // Import Modal
  importModal: getElementByIdSafe('import-modal'),
  importModalClose: getElementByIdSafe('import-modal-close'),
  importSelectBtn: getElementByIdSafe('import-select-btn'),
  importFile: document.getElementById('import-file'),
  importFilename: document.getElementById('import-filename'),
  importExecuteBtn: document.getElementById('import-execute-btn'),
  importResult: document.getElementById('import-result'),
  nutritionExplainabilityPanel: getElementByIdSafe('nutrition-explainability-panel')
};
