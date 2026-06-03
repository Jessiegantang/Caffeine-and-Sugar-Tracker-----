// ==========================================
// Caffeine and Sugar Tracker - Calculation Module
// ==========================================

import {
  CAFFEINE_DENSITIES,
  BASE_SUGAR_DENSITIES,
  SWEETENER_SUGAR_DENSITIES,
  SWEETNESS_MULTIPLIERS,
  ALCOHOL_DENSITY
} from './config.js';

/**
 * Calculates Caffeine content (mg)
 * Formula: volume (ml) * caffeine_density (mg/100ml) / 100
 * @param {string} type - Drink Type (coffee, tea, milktea, fruittea)
 * @param {number} volume - Volume in ml
 * @returns {number} Estimated caffeine in mg (rounded)
 */
export function calculateCaffeine(type, volume) {
  const density = CAFFEINE_DENSITIES[type] || 0;
  return Math.round((volume * density) / 100);
}

/**
 * Calculates Sugar content (g)
 * Formula: volume (ml) * (base_sugar_density + sweetener_sugar_density * sweetness_multiplier) / 100
 * @param {string} type - Drink Type (coffee, tea, milktea, fruittea)
 * @param {string} sugarLevel - Sweetness Level (none, three, half, seven, full)
 * @param {number} volume - Volume in ml
 * @returns {number} Estimated sugar in g (rounded to 1 decimal place)
 */
export function calculateSugar(type, sugarLevel, volume) {
  const baseDensity = BASE_SUGAR_DENSITIES[type] || 0;
  const sweetenerDensity = SWEETENER_SUGAR_DENSITIES[type] || 0;
  const multiplier = SWEETNESS_MULTIPLIERS[sugarLevel] !== undefined ? SWEETNESS_MULTIPLIERS[sugarLevel] : 0;

  const totalDensity = baseDensity + (sweetenerDensity * multiplier);
  return parseFloat(((volume * totalDensity) / 100).toFixed(1));
}

/**
 * Calculates alcohol intake (g)
 * Formula: volume (ml) * alcoholByVolume(%) * alcoholDensity(g/ml)
 * @param {number} volume - Volume in ml
 * @param {number} abv - Alcohol by volume percentage, e.g. 4.0 for beer
 * @returns {number} Estimated alcohol in g (rounded to 1 decimal place)
 */
export function calculateAlcohol(volume, abv) {
  if (!abv || abv <= 0) return 0;
  const alcoholGrams = volume * (abv / 100) * ALCOHOL_DENSITY;
  return parseFloat(alcoholGrams.toFixed(1));
}

/**
 * Estimate base sugar by drink style (g/100ml)
 * This models "intrinsic sugar" from milk/coconut/juice etc, not added syrup.
 * @param {string} type
 * @param {string} name
 * @returns {number}
 */
// export function estimateBaseSugarDensity(type, name = '') {
//   const lower = name.toLowerCase();

//   if (type === 'coffee' || type === 'teacoffee') {
//     if (lower.includes('椰') || lower.includes('coconut')) return 4.0;
//     if (lower.includes('橙') || lower.includes('柚') || lower.includes('柠') || lower.includes('果')) return 3.5; // 果咖（如橙C美式）
//     if (lower.includes('美式') || lower.includes('americano') || lower.includes('long black')) return 0;
//     if (lower.includes('拿铁') || lower.includes('latte') || lower.includes('澳白') || lower.includes('卡布') || lower.includes('cappuccino')) return 2.8;
//     if (lower.includes('摩卡')) return 4.0;
//     return 0.8;
//   }

//   if (type === 'tea') return 0;
//   if (type === 'milktea') return 1.8;
//   if (type === 'fruittea') return 2.2;
//   if (type === 'soda') return 0;
//   if (type === 'alcohol') return 0;
//   return 0;
// }
export function estimateBaseSugarDensity(type, name = '') {
  const lower = name.toLowerCase();

  // ===== 咖啡类 =====
  if (type === 'coffee' || type === 'teacoffee') {

    // 纯黑咖啡
    if (
      lower.includes('美式') ||
      lower.includes('americano') ||
      lower.includes('long black')
    ) {
      return 0;
    }

    // 牛奶咖啡
    if (
      lower.includes('拿铁') ||
      lower.includes('latte') ||
      lower.includes('澳白') ||
      lower.includes('flat white') ||
      lower.includes('卡布') ||
      lower.includes('cappuccino')
    ) {
      return 4.8;
    }

    // 摩卡
    if (
      lower.includes('摩卡') ||
      lower.includes('mocha')
    ) {
      return 6.0;
    }

    // 椰乳咖啡
    if (
      lower.includes('椰') ||
      lower.includes('coconut')
    ) {
      return 5.0;
    }

    // 果咖
    if (
      lower.includes('橙') ||
      lower.includes('柚') ||
      lower.includes('柠') ||
      lower.includes('果')
    ) {
      return 4.5;
    }

    return 2.0;
  }

  // ===== 原叶茶 =====
  if (type === 'tea') {
    return 0;
  }

  // ===== 奶茶 =====
  if (type === 'milktea') {

    if (
      lower.includes('厚乳') ||
      lower.includes('鲜奶')
    ) {
      return 4.5;
    }

    if (
      lower.includes('奶盖') ||
      lower.includes('芝士')
    ) {
      return 5.5;
    }

    return 4.0;
  }

  // ===== 果茶 =====
  if (type === 'fruittea') {

    if (
      lower.includes('柠檬')
    ) {
      return 2.5;
    }

    if (
      lower.includes('百香果') ||
      lower.includes('芒果') ||
      lower.includes('葡萄') ||
      lower.includes('桃')
    ) {
      return 4.0;
    }

    return 3.5;
  }

  // ===== 汽水 =====
  if (type === 'soda') {
    return 10.0;
  }

  // ===== 酒精 =====
  if (type === 'alcohol') {

    if (
      lower.includes('啤酒')
    ) {
      return 0.5;
    }

    if (
      lower.includes('鸡尾酒')
    ) {
      return 5.0;
    }

    return 0;
  }

  return 0;
}

/**
 * Estimate sweetener multiplier when user cannot provide exact sugar option.
 * @param {string} type
 * @returns {number}
 */
export function estimateSweetnessMultiplier(type) {
  switch (type) {
    case 'soda':
      return 1.0;
    case 'milktea':
    case 'fruittea':
      return 0.7;
    case 'coffee':
    case 'teacoffee':
      return 0.3;
    case 'alcohol':
      return 0.3;
    default:
      return 0;
  }
}

/**
 * Calculate sugar with explicit base-density + user selected (or estimated) sweetness.
 * @param {string} type
 * @param {string} sugarLevel
 * @param {number} volume
 * @param {number} baseSugarDensity
 * @returns {number}
 */
export function calculateSugarWithContext(type, sugarLevel, volume, baseSugarDensity) {
  const sweetenerDensity = SWEETENER_SUGAR_DENSITIES[type] || 0;
  const fallbackMultiplier = estimateSweetnessMultiplier(type);
  const multiplier = sugarLevel === 'unknown'
    ? fallbackMultiplier
    : (SWEETNESS_MULTIPLIERS[sugarLevel] !== undefined ? SWEETNESS_MULTIPLIERS[sugarLevel] : 0);
  const totalDensity = (baseSugarDensity || 0) + (sweetenerDensity * multiplier);
  return parseFloat(((volume * totalDensity) / 100).toFixed(1));
}
