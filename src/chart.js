// ==========================================
// Caffeine and Sugar Tracker - SVG Weekly Chart
// ==========================================

import { CAFFEINE_LIMIT, SUGAR_LIMIT } from './config.js';

/**
 * Renders the weekly double-bar chart in SVG
 * @param {HTMLElement} container - Target container element
 * @param {Array} logs - All logged entries
 * @param {Array} weekDates - Array of 7 date strings (YYYY-MM-DD)
 */
export function renderWeeklyChart(container, logs, weekDates) {
  if (!container) return;
  container.innerHTML = '';

  // Aggregate daily totals
  const dailyTotals = weekDates.map(date => {
    const dayLogs = logs.filter(log => log.date === date);
    const caffeine = dayLogs.reduce((sum, l) => sum + l.caffeine, 0);
    const sugar = dayLogs.reduce((sum, l) => sum + l.sugarContent, 0);
    return { date, caffeine, sugar };
  });

  // Chart SVG settings
  const width = 600;
  const height = 240;
  const paddingLeft = 45;
  const paddingRight = 15;
  const paddingTop = 30;
  const paddingBottom = 40;
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // Calculate percentage of limits to scale height
  // Limit heights to their relative daily limits, but scale dynamically if exceeded
  let maxPercent = 1.0; // 100% limit minimum scale
  dailyTotals.forEach(day => {
    const cafPercent = day.caffeine / CAFFEINE_LIMIT;
    const sugPercent = day.sugar / SUGAR_LIMIT;
    if (cafPercent > maxPercent) maxPercent = cafPercent;
    if (sugPercent > maxPercent) maxPercent = sugPercent;
  });

  // Add 10% padding on top if limit exceeded
  if (maxPercent > 1.0) maxPercent *= 1.1;

  // Build SVG string
  let svgHTML = `<svg viewBox="0 0 ${width} ${height}" class="weekly-svg-chart" width="100%" height="100%">`;

  // Draw Grid Lines (0%, 50%, 100%)
  const gridLevels = [0, 0.5, 1.0];
  gridLevels.forEach(lvl => {
    if (lvl > maxPercent) return;
    const y = height - paddingBottom - (lvl / maxPercent) * chartHeight;
    const label = `${lvl * 100}%`;
    
    // Gridline
    svgHTML += `
      <line x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}" 
            stroke="#dce6e2" stroke-dasharray="4,4" stroke-width="1" />
      <text x="${paddingLeft - 8}" y="${y + 4}" fill="#71858b" font-size="10" font-family="Plus Jakarta Sans" text-anchor="end">
        ${label}
      </text>
    `;
  });

  // Calculate X-axis spacing
  const dayCount = weekDates.length;
  const dayColWidth = chartWidth / dayCount;
  const barWidth = 14;
  const barSpacing = 4; // Gap between caffeine and sugar bars

  // Render Bars for each day
  dailyTotals.forEach((day, index) => {
    const xCenter = paddingLeft + (index * dayColWidth) + (dayColWidth / 2);
    
    // Caffeine Bar (Left)
    const cafRatio = day.caffeine / CAFFEINE_LIMIT;
    const cafBarH = (cafRatio / maxPercent) * chartHeight;
    const cafX = xCenter - barWidth - (barSpacing / 2);
    const cafY = height - paddingBottom - cafBarH;

    // Sugar Bar (Right)
    const sugRatio = day.sugar / SUGAR_LIMIT;
    const sugBarH = (sugRatio / maxPercent) * chartHeight;
    const sugX = xCenter + (barSpacing / 2);
    const sugY = height - paddingBottom - sugBarH;

    // Format Date Label (MM-DD)
    const [,, dStr] = day.date.split('-');
    const mStr = day.date.split('-')[1];
    const shortDate = `${mStr}-${dStr}`;

    // Caffeine Bar Rect
    svgHTML += `
      <rect x="${cafX}" y="${cafY}" width="${barWidth}" height="${Math.max(cafBarH, 1)}" 
            rx="4" fill="url(#chart-caffeine-grad)" class="chart-bar bar-caffeine">
        <title>日期: ${day.date}\n咖啡因: ${day.caffeine}mg (${Math.round(cafRatio * 100)}% 推荐限额)</title>
      </rect>
    `;

    // Sugar Bar Rect
    svgHTML += `
      <rect x="${sugX}" y="${sugY}" width="${barWidth}" height="${Math.max(sugBarH, 1)}" 
            rx="4" fill="url(#chart-sugar-grad)" class="chart-bar bar-sugar">
        <title>日期: ${day.date}\n糖分: ${day.sugar.toFixed(1)}g (${Math.round(sugRatio * 100)}% 推荐限额)</title>
      </rect>
    `;

    // X-axis label
    svgHTML += `
      <text x="${xCenter}" y="${height - paddingBottom + 18}" fill="#8a9ca1" font-size="10" font-family="Plus Jakarta Sans" text-anchor="middle">
        ${shortDate}
      </text>
    `;
  });

  // Draw X Axis Baseline
  svgHTML += `
    <line x1="${paddingLeft}" y1="${height - paddingBottom}" x2="${width - paddingRight}" y2="${height - paddingBottom}" 
          stroke="#cbdad5" stroke-width="1.5" />
  `;

  // Define Gradients & Styles
  svgHTML += `
    <defs>
      <linearGradient id="chart-caffeine-grad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#2f8f83" stop-opacity="0.78"/>
        <stop offset="100%" stop-color="#6fc0a8" stop-opacity="0.95"/>
      </linearGradient>
      <linearGradient id="chart-sugar-grad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#d59a22" stop-opacity="0.72"/>
        <stop offset="100%" stop-color="#f0c96b" stop-opacity="0.9"/>
      </linearGradient>
    </defs>
  </svg>
  `;

  container.innerHTML = svgHTML;
}
