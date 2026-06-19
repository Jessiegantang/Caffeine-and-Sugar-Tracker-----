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
  const height = 248;
  const paddingLeft = 52;
  const paddingRight = 24;
  const paddingTop = 28;
  const paddingBottom = 52;
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
            stroke="#e7eeeb" stroke-dasharray="5,7" stroke-width="1" />
      <text x="${paddingLeft - 10}" y="${y + 4}" fill="#7b8d94" font-size="10" font-weight="700" font-family="Plus Jakarta Sans" text-anchor="end">
        ${label}
      </text>
    `;
  });

  // Calculate X-axis spacing
  const dayCount = weekDates.length;
  const dayColWidth = chartWidth / dayCount;
  const slotWidth = Math.min(48, dayColWidth - 14);
  const barWidth = 12;
  const barSpacing = 8; // Gap between caffeine and sugar bars

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

    svgHTML += `
      <rect x="${xCenter - slotWidth / 2}" y="${paddingTop}" width="${slotWidth}" height="${chartHeight}" 
            rx="12" fill="#fbfdff" stroke="#edf3f5" class="weekly-chart-day-slot" />
    `;

    // Caffeine Bar Rect
    svgHTML += `
      <rect x="${cafX}" y="${cafY}" width="${barWidth}" height="${cafBarH}" 
            rx="6" fill="url(#chart-caffeine-grad)" class="weekly-chart-bar bar-caffeine">
        <title>日期: ${day.date}\n咖啡因: ${day.caffeine}mg (${Math.round(cafRatio * 100)}% 推荐限额)</title>
      </rect>
    `;

    // Sugar Bar Rect
    svgHTML += `
      <rect x="${sugX}" y="${sugY}" width="${barWidth}" height="${sugBarH}" 
            rx="6" fill="url(#chart-sugar-grad)" class="weekly-chart-bar bar-sugar">
        <title>日期: ${day.date}\n糖分: ${day.sugar.toFixed(1)}g (${Math.round(sugRatio * 100)}% 推荐限额)</title>
      </rect>
    `;

    // X-axis label
    svgHTML += `
      <rect x="${xCenter - 21}" y="${height - paddingBottom + 14}" width="42" height="20" rx="10" fill="#f3f7f8" stroke="#e1eaec" />
      <text x="${xCenter}" y="${height - paddingBottom + 28}" fill="#6f828a" font-size="10" font-weight="700" font-family="Plus Jakarta Sans" text-anchor="middle">
        ${shortDate}
      </text>
    `;
  });

  // Draw X Axis Baseline
  svgHTML += `
    <line x1="${paddingLeft}" y1="${height - paddingBottom}" x2="${width - paddingRight}" y2="${height - paddingBottom}" 
          stroke="#d5e1de" stroke-width="1.5" stroke-linecap="round" />
  `;

  // Define Gradients & Styles
  svgHTML += `
    <defs>
      <linearGradient id="chart-caffeine-grad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#5f8ea8" stop-opacity="0.92"/>
        <stop offset="100%" stop-color="#9fc7d8" stop-opacity="1"/>
      </linearGradient>
      <linearGradient id="chart-sugar-grad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0%" stop-color="#789b87" stop-opacity="0.9"/>
        <stop offset="100%" stop-color="#b7d3c0" stop-opacity="1"/>
      </linearGradient>
    </defs>
  </svg>
  `;

  container.innerHTML = svgHTML;
}
