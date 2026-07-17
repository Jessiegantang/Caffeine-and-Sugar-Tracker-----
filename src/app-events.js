export const DATE_CHANGED_EVENT = 'drinkmind:date-changed';
export const DRINK_SELECTED_EVENT = 'drinkmind:drink-selected';
export const LOG_DELETE_EVENT = 'drinkmind:log-delete';
export const LOG_SELECTED_EVENT = 'drinkmind:log-selected';
export const FORM_SUBMIT_EVENT = 'drinkmind:form-submit';
export const FORM_SAVED_EVENT = 'drinkmind:form-saved';
export const SLEEP_SAVED_EVENT = 'drinkmind:sleep-saved';
export const INTAKE_PARSED_EVENT = 'drinkmind:intake-parsed';
export const ADD_PARSED_INTAKE_EVENT = 'drinkmind:add-parsed-intake';
export const NUTRITION_RESULT_EVENT = 'drinkmind:nutrition-result';

const listeners = new Map();

export function emitAppEvent(eventName, payload) {
  const eventListeners = listeners.get(eventName);
  if (!eventListeners) return;
  [...eventListeners].forEach(listener => listener(payload));
}

export function onAppEvent(eventName, listener) {
  if (!listeners.has(eventName)) listeners.set(eventName, new Set());
  listeners.get(eventName).add(listener);

  return () => {
    const eventListeners = listeners.get(eventName);
    if (!eventListeners) return;
    eventListeners.delete(listener);
    if (!eventListeners.size) listeners.delete(eventName);
  };
}

export function notifyDateChanged(date) {
  emitAppEvent(DATE_CHANGED_EVENT, { date });
}

export function notifyDrinkSelected(detail) {
  emitAppEvent(DRINK_SELECTED_EVENT, detail);
}

export function notifyLogDelete(id) {
  emitAppEvent(LOG_DELETE_EVENT, { id });
}

export function notifyLogSelected(log) {
  emitAppEvent(LOG_SELECTED_EVENT, { log });
}

export function notifyFormSubmit(formData) {
  emitAppEvent(FORM_SUBMIT_EVENT, formData);
}

export function notifyFormSaved(date) {
  emitAppEvent(FORM_SAVED_EVENT, { date });
}

export function notifySleepSaved(date) {
  emitAppEvent(SLEEP_SAVED_EVENT, { date });
}
