export function normalizeDrinkInput(formData = {}) {
  const volume = Number.parseInt(formData.volume, 10);
  const value = {
    date: String(formData.date || ''),
    brand: String(formData.brand || '').trim(),
    name: String(formData.name || '').trim(),
    type: String(formData.type || ''),
    sugar: String(formData.sugar || ''),
    volume,
    startTime: String(formData.startTime || ''),
    endTime: String(formData.endTime || ''),
    saveToLibrary: Boolean(formData.saveToLibrary),
  };

  const errors = [];
  if (!value.date) errors.push('请选择日期');
  if (value.name.length < 2) errors.push('请输入饮品名称');
  if (!value.type) errors.push('请选择饮品类型');
  if (!value.sugar) errors.push('请选择甜度');
  if (!Number.isFinite(value.volume) || value.volume < 10 || value.volume > 2000) {
    errors.push('容量必须在10-2000ml之间');
  }

  return { value, errors };
}

export function createOptimisticLog(input, options = {}) {
  const now = options.now ?? Date.now();
  const random = options.random ?? Math.random();
  return {
    id: `log_${now}_${random.toString(36).slice(2, 11)}`,
    date: input.date,
    brand: input.brand,
    name: input.name,
    type: input.type,
    sugar: input.sugar,
    volume: input.volume,
    startTime: input.startTime,
    endTime: input.endTime,
    caffeine: 0,
    sugarContent: 0,
    isCalculating: true,
  };
}
