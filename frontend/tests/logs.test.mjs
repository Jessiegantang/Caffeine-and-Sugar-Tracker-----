import assert from 'node:assert/strict';
import test from 'node:test';
import { createOptimisticLog, normalizeDrinkInput } from '../src/domain/logs.js';

test('normalizeDrinkInput trims values and parses numeric fields', () => {
  const { value, errors } = normalizeDrinkInput({
    date: '2026-07-17',
    brand: '  Test Brand ',
    name: '  Latte ',
    type: 'coffee',
    sugar: 'half',
    volume: '500',
    baseSugarOverride: '12.5',
    saveToLibrary: true,
  });

  assert.deepEqual(errors, []);
  assert.equal(value.brand, 'Test Brand');
  assert.equal(value.name, 'Latte');
  assert.equal(value.volume, 500);
  assert.equal(value.baseSugarOverride, 12.5);
  assert.equal(value.saveToLibrary, true);
});

test('normalizeDrinkInput reports all required-field errors', () => {
  const { errors } = normalizeDrinkInput({ volume: 5 });
  assert.deepEqual(errors, ['请选择日期', '请输入饮品名称', '请选择饮品类型', '请选择甜度', '容量必须在10-2000ml之间']);
});

test('createOptimisticLog creates a stable pending log shape', () => {
  const { value } = normalizeDrinkInput({
    date: '2026-07-17', name: 'Latte', type: 'coffee', sugar: 'none', volume: 350,
    startTime: '09:00', endTime: '09:30', baseSugarOverride: 4,
  });
  const log = createOptimisticLog(value, { now: 1234, random: 0.5 });

  assert.match(log.id, /^log_1234_/);
  assert.equal(log.caffeine, 0);
  assert.equal(log.sugarContent, 0);
  assert.equal(log.baseSugarDensity, 4);
  assert.equal(log.isCalculating, true);
});
