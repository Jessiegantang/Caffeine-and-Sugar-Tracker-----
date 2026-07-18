import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, 'dist');
const server = createServer(async (request, response) => {
  if (request.url?.startsWith('/api/')) {
    response.writeHead(503, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ detail: 'Smoke test backend stub' }));
    return;
  }

  const pathname = decodeURIComponent(new URL(request.url || '/', 'http://localhost').pathname);
  const relativePath = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const filePath = join(dist, relativePath);
  try {
    const content = await readFile(filePath);
    response.writeHead(200, { 'Content-Type': contentType(filePath) });
    response.end(content);
  } catch {
    response.writeHead(404);
    response.end('Not found');
  }
});

let browser;
let page;
const chatHistory = [];
try {
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(4175, '127.0.0.1', resolve);
  });
  browser = await puppeteer.launch({
    headless: true,
    timeout: 15_000,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--no-proxy-server'],
  });
  page = await browser.newPage();
  page.setDefaultTimeout(10_000);
  await page.setRequestInterception(true);
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['localhost', '127.0.0.1'].includes(url.hostname) || url.port !== '8000' || !url.pathname.startsWith('/api/')) {
      request.continue();
      return;
    }

    const isPreflight = request.method() === 'OPTIONS';
    request.respond({
      status: isPreflight ? 204 : 200,
      contentType: 'application/json',
      headers: {
        'access-control-allow-origin': 'http://127.0.0.1:4175',
        'access-control-allow-methods': 'GET, POST, DELETE, OPTIONS',
        'access-control-allow-headers': 'content-type',
      },
      body: isPreflight ? '' : JSON.stringify(mockApiResponse(request, url, chatHistory)),
    });
  });
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.setViewport({ width: 1440, height: 1000 });
  await page.goto('http://127.0.0.1:4175', { waitUntil: 'domcontentloaded', timeout: 20_000 });
  await page.waitForSelector('#chat-input');

  const initial = await page.evaluate(() => ({
    daily: getComputedStyle(document.getElementById('tab-daily')).display,
    database: getComputedStyle(document.getElementById('tab-database')).display,
    hasExplainability: Boolean(document.getElementById('agent-workspace')),
  }));
  assert.notEqual(initial.daily, 'none');
  assert.equal(initial.database, 'none');
  assert.equal(initial.hasExplainability, true);

  await page.type('#chat-input', '我刚刚早上喝了一杯瑞幸的超大杯苹果茉莉冰奶，微微甜');
  await page.click('#chat-send-btn');
  await page.waitForFunction(() => !document.querySelector('#chat-input').disabled);
  await page.type('#chat-input', '应该是三分糖');
  await page.click('#chat-send-btn');
  await page.waitForSelector('.chat-add-log-btn:not([disabled])');
  assert.match(await page.$eval('.chat-add-log-btn', element => element.textContent), /添加到当天摄入记录/);

  await page.click('[data-tab="tab-database"]');
  await page.waitForFunction(() => getComputedStyle(document.getElementById('tab-database')).display !== 'none');
  assert.equal(await page.$eval('#main-content', element => getComputedStyle(element).display), 'none');
  assert.ok(await page.$('.database-stats-card'));
  assert.ok(await page.$('.knowledge-acquisition-section'));

  await page.click('[data-tab="tab-daily"]');
  await page.waitForFunction(() => getComputedStyle(document.getElementById('main-content')).display !== 'none');
  assert.equal(await page.$eval('#tab-database', element => getComputedStyle(element).display), 'none');

  await page.setViewport({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#chat-input');
  const mobileLayout = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    contentWidth: document.documentElement.scrollWidth,
    tabsVisible: document.querySelectorAll('.tab-btn').length === 2,
  }));
  assert.ok(mobileLayout.contentWidth <= mobileLayout.viewportWidth + 1, `Mobile layout overflows by ${mobileLayout.contentWidth - mobileLayout.viewportWidth}px`);
  assert.equal(mobileLayout.tabsVisible, true);
  assert.deepEqual(pageErrors, []);

  console.log('Smoke test passed: Vue mounted and both primary tabs rendered.');
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}

function contentType(filePath) {
  return ({
    '.css': 'text/css; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
  })[extname(filePath)] || 'application/octet-stream';
}

function mockApiResponse(request, url, history) {
  if (url.pathname === '/api/chat' && request.method() === 'GET') {
    return { status: 'success', history };
  }
  if (url.pathname === '/api/chat' && request.method() === 'POST') {
    const { message } = JSON.parse(request.postData() || '{}');
    const complete = message.includes('三分糖');
    history.push(
      { role: 'user', content: message },
      { role: 'assistant', content: complete ? '饮品信息已补充完整。' : '这杯甜度是无糖、三分糖、半糖、七分糖还是全糖？' },
    );
    return {
      status: 'success',
      parsed_intake: {
        intent: 'log_drink',
        brand: '瑞幸咖啡',
        name: '苹果茉莉冰奶',
        type: 'coffee',
        volume: 650,
        sugar: complete ? 'three' : null,
        time: 'now',
        missing_fields: complete ? [] : ['sugar'],
      },
    };
  }
  if (url.pathname === '/api/agent/act') return { agent_state: {} };
  if (url.pathname === '/api/logs' || url.pathname === '/api/knowledge_base') return [];
  if (url.pathname.endsWith('/candidates')) return { candidates: [] };
  if (url.pathname.endsWith('/evidence')) return { evidence: [] };
  return {};
}
