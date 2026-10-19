import { FALLBACK_PORTFOLIO, FALLBACK_PRICES, FALLBACK_HISTORY } from './sampleData.js';
import {
  parseLocalizedNumber,
  computePortfolioSummary,
  computeHistoryStats,
  computeDipTiers,
  computeWhatIfTable,
  computeRiskReport
} from './math.js';

const STORAGE_KEY_PORTFOLIO = 'WEALTH_DASHBOARD_PORTFOLIO_V2';
const STORAGE_KEY_MANUAL_PRICES = 'WEALTH_DASHBOARD_MANUAL_PRICES_V2';

const state = {
  unit: 'toman', // 'toman' | 'rial'
  portfolio: null,
  prices: null,
  history: [],
  charts: {}
};

const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

function toPersianDigits(val) {
  if (val === null || val === undefined) return '۰';
  return String(val).replace(/\d/g, d => persianDigits[Number(d)]);
}

function fmtNum(val, decimals = 0) {
  const num = parseLocalizedNumber(val, 0);
  const parts = num.toFixed(decimals).split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
  return toPersianDigits(parts.join('٫'));
}

function fmtMoney(tomanVal) {
  const num = parseLocalizedNumber(tomanVal, 0);
  const mult = state.unit === 'rial' ? 10 : 1;
  const suffix = state.unit === 'rial' ? ' ریال' : ' تومان';
  return fmtNum(Math.round(num * mult), 0) + suffix;
}

function fmtJalali(dateInput) {
  try {
    const d = dateInput ? new Date(dateInput) : new Date();
    if (isNaN(d.getTime())) return toPersianDigits(String(dateInput));
    return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).format(d);
  } catch {
    return '۱۴۰۵/۰۷/۲۷';
  }
}

async function fetchJsonWithCacheBust(relativePath) {
  const bust = `v=${Date.now()}`;
  const sep = relativePath.includes('?') ? '&' : '?';
  const response = await fetch(`${relativePath}${sep}${bust}`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} در خواندن ${relativePath}`);
  }
  return await response.json();
}

async function initializeData() {
  const errBanner = document.getElementById('errorBanner');
  const errText = document.getElementById('errorBannerText');
  const warnings = [];

  // 1. Load Portfolio (Priority: localStorage -> fetch('data/portfolio.json') -> FALLBACK_PORTFOLIO)
  const localPortfolioRaw = localStorage.getItem(STORAGE_KEY_PORTFOLIO);
  if (localPortfolioRaw) {
    try {
      state.portfolio = JSON.parse(localPortfolioRaw);
    } catch {
      state.portfolio = null;
    }
  }

  if (!state.portfolio) {
    try {
      state.portfolio = await fetchJsonWithCacheBust('data/portfolio.json');
    } catch (e) {
      warnings.push(`عدم دسترسی به فایل data/portfolio.json (${e.message})؛ از داده پیش‌فرض داخلی استفاده شد.`);
      state.portfolio = JSON.parse(JSON.stringify(FALLBACK_PORTFOLIO));
    }
  }

  // 2. Load Prices (Priority: fetch('data/prices.json') + manual overrides -> FALLBACK_PRICES)
  try {
    state.prices = await fetchJsonWithCacheBust('data/prices.json');
  } catch (e) {
    warnings.push(`عدم دسترسی به فایل data/prices.json (${e.message})؛ از قیمت‌های نمونه داخلی استفاده شد.`);
    state.prices = JSON.parse(JSON.stringify(FALLBACK_PRICES));
  }

  const manualPricesRaw = localStorage.getItem(STORAGE_KEY_MANUAL_PRICES);
  if (manualPricesRaw) {
    try {
      const manualObj = JSON.parse(manualPricesRaw);
      state.prices.fx = { ...state.prices.fx, ...(manualObj.fx || {}) };
      state.prices.stocks = { ...state.prices.stocks, ...(manualObj.stocks || {}) };
      state.prices.lastUpdated = manualObj.lastUpdated || state.prices.lastUpdated;
    } catch {
      // ignore corrupted manual price cache
    }
  }

  // 3. Load History
  try {
    state.history = await fetchJsonWithCacheBust('data/history.json');
  } catch {
    state.history = JSON.parse(JSON.stringify(FALLBACK_HISTORY));
  }

  if (warnings.length > 0) {
    errText.textContent = warnings.join(' | ');
    errBanner.classList.add('show');
  } else {
    errBanner.classList.remove('show');
  }

  renderDashboard();
}

function renderDashboard() {
  const summary = computePortfolioSummary(state.portfolio, state.prices);

  // Ensure today's net worth is appended to history in memory
  const todayIso = new Date().toISOString().slice(0, 10);
  if (Array.isArray(state.history) && state.history.length > 0) {
    const lastEntry = state.history[state.history.length - 1];
    if (lastEntry.date === todayIso) {
      lastEntry.totalToman = Math.round(summary.totalNetWorthToman);
    } else {
      state.history.push({ date: todayIso, totalToman: Math.round(summary.totalNetWorthToman) });
    }
  }

  // Header & Badges
  document.getElementById('jalaliTodayText').textContent = fmtJalali(new Date());
  const sampleBadge = document.getElementById('sampleDataBadge');
  sampleBadge.style.display = state.portfolio.isSampleData ? 'inline-flex' : 'none';

  const lastUpStr = state.prices?.lastUpdated || '2026-10-19T12:00:00Z';
  document.getElementById('lastUpdatedBadge').textContent = `بروزرسانی: ${fmtJalali(lastUpStr)}`;

  const ageHours = (Date.now() - new Date(lastUpStr).getTime()) / (1000 * 3600);
  const staleBanner = document.getElementById('staleBanner');
  if (ageHours > 48 || state.prices?.fx?.stale) {
    staleBanner.classList.add('show');
  } else {
    staleBanner.classList.remove('show');
  }

  // Top KPI Cards
  document.getElementById('kpiNetWorthToman').textContent = fmtMoney(summary.totalNetWorthToman);
  document.getElementById('kpiNetWorthUsd').textContent = `معادل دلاری: $${fmtNum(summary.totalNetWorthUsd, 2)}`;

  document.getElementById('kpiStocksToman').textContent = fmtMoney(summary.stocksValueToman);
  const stockPnlEl = document.getElementById('kpiStocksPnl');
  const signS = summary.stocksPnlToman >= 0 ? '+' : '';
  stockPnlEl.textContent = `${signS}${fmtMoney(summary.stocksPnlToman)} (${signS}${fmtNum(summary.stocksPnlPct, 1)}٪)`;
  stockPnlEl.style.color = summary.stocksPnlToman >= 0 ? 'var(--success)' : 'var(--danger)';

  document.getElementById('kpiStableToman').textContent = fmtMoney(summary.stableValueFreeToman);
  document.getElementById('kpiStableUsd').textContent = `موجودی: $${fmtNum(summary.stableUsdTotal, 2)} (به نرخ آزاد)`;

  document.getElementById('kpiCashNftToman').textContent = fmtMoney(summary.cash.cashToman + summary.nftsValueToman);
  document.getElementById('kpiCashNftSub').textContent = `نقد: ${fmtNum(summary.weights.cashPct, 0)}٪ | NFT: ${fmtNum(summary.weights.nftsPct, 0)}٪`;

  renderOverviewTab(summary);
  renderStocksTab(summary);
  renderCryptoDipTab(summary);
  renderCashNftTab(summary);
  renderWhatIfTab(summary);
  renderRiskTab(summary);
}

function renderOverviewTab(summary) {
  // Allocation Donut Chart
  const donutCtx = document.getElementById('allocationDonutCanvas').getContext('2d');
  if (state.charts.donut) state.charts.donut.destroy();

  state.charts.donut = new Chart(donutCtx, {
    type: 'doughnut',
    data: {
      labels: ['بورس ایران', 'استیبل‌کوین اتریوم', 'نقدینگی ریالی', 'NFT تلگرام'],
      datasets: [{
        data: [
          Math.round(summary.stocksValueToman),
          Math.round(summary.stableValueUsdtToman),
          Math.round(summary.cash.cashToman),
          Math.round(summary.nftsValueToman)
        ],
        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Vazirmatn', size: 11 } } }
      }
    }
  });

  renderHistoryChart();
}

function renderHistoryChart() {
  const rangeSelect = document.getElementById('historyRangeSelect');
  const rangeVal = rangeSelect ? rangeSelect.value : 'all';
  const rawList = Array.isArray(state.history) && state.history.length > 0 ? state.history : FALLBACK_HISTORY;
  const sliceCount = rangeVal === 'all' ? rawList.length : Number(rangeVal);
  const filtered = rawList.slice(-sliceCount);

  const histStats = computeHistoryStats(filtered);
  document.getElementById('histCumReturnBadge').textContent =
    `بازده دوره: ${histStats.cumulativeReturnPct >= 0 ? '+' : ''}${fmtNum(histStats.cumulativeReturnPct, 1)}٪`;
  document.getElementById('histBestDayBadge').textContent =
    histStats.bestDay ? `بهترین روز: +${fmtNum(histStats.bestDay.pct, 1)}٪ (${fmtJalali(histStats.bestDay.date)})` : 'بهترین روز: -';
  document.getElementById('histWorstDayBadge').textContent =
    histStats.worstDay ? `بدترین روز: ${fmtNum(histStats.worstDay.pct, 1)}٪ (${fmtJalali(histStats.worstDay.date)})` : 'بدترین روز: -';

  const ctx = document.getElementById('historyLineCanvas').getContext('2d');
  if (state.charts.history) state.charts.history.destroy();

  const mult = state.unit === 'rial' ? 10 : 1;
  state.charts.history = new Chart(ctx, {
    type: 'line',
    data: {
      labels: filtered.map(item => fmtJalali(item.date)),
      datasets: [{
        label: `ارزش کل ثروت (${state.unit === 'rial' ? 'ریال' : 'تومان'})`,
        data: filtered.map(item => Math.round(item.totalToman * mult)),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.15)',
        fill: true,
        tension: 0.3,
        pointRadius: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { family: 'Vazirmatn', size: 10 }, maxTicksLimit: 6 } },
        y: { ticks: { color: '#94a3b8', font: { family: 'Vazirmatn', size: 10 } } }
      }
    }
  });
}

function renderStocksTab(summary) {
  const tbody = document.getElementById('stocksTableBody');
  tbody.innerHTML = '';

  summary.stocks.forEach(s => {
    const tr = document.createElement('tr');
    const signPnl = s.pnlToman >= 0 ? '+' : '';
    const signDay = s.dailyChangePct >= 0 ? '+' : '';
    tr.innerHTML = `
      <td><strong>${s.symbol}</strong> ${s.stale ? '<span class="badge badge-warning">قدیمی</span>' : ''}</td>
      <td>${s.name}</td>
      <td class="sensitive">${fmtNum(s.qty)}</td>
      <td class="sensitive">${fmtMoney(s.avgBuyToman)}</td>
      <td class="sensitive"><strong>${fmtMoney(s.currentPriceToman)}</strong></td>
      <td><span class="badge ${s.dailyChangePct >= 0 ? 'badge-success' : 'badge-danger'}">${signDay}${fmtNum(s.dailyChangePct, 2)}٪</span></td>
      <td class="sensitive"><strong>${fmtMoney(s.valueToman)}</strong></td>
      <td class="sensitive" style="color:${s.pnlToman >= 0 ? 'var(--success)' : 'var(--danger)'}; font-weight:700;">
        ${signPnl}${fmtMoney(s.pnlToman)} (${signPnl}${fmtNum(s.pnlPct, 1)}٪)
      </td>
      <td>${fmtNum(s.shareOfTotalPct, 1)}٪</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderCryptoDipTab(summary) {
  const stableBody = document.getElementById('stablecoinsTableBody');
  stableBody.innerHTML = '';
  summary.stablecoins.forEach(st => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${st.symbol}</strong> (${st.network})</td>
      <td class="sensitive">${fmtNum(st.amount, 2)}</td>
      <td class="sensitive">$${fmtNum(st.usdValue, 2)}</td>
      <td class="sensitive">${fmtMoney(st.valueFreeUsdToman)}</td>
      <td class="sensitive">${fmtMoney(st.valueUsdtToman)}</td>
    `;
    stableBody.appendChild(tr);
  });

  document.getElementById('fxSpreadInfo').textContent =
    `نرخ تتر: ${fmtMoney(summary.rates.usdtToman)} | دلار آزاد: ${fmtMoney(summary.rates.freeUsdToman)} | اختلاف: ${fmtMoney(summary.rates.spreadToman)}`;

  const allocs = state.portfolio.dipPlan?.allocations || { BTC: 50, ETH: 30, SOL: 20 };
  document.getElementById('dipAllocBtc').value = allocs.BTC;
  document.getElementById('dipAllocEth').value = allocs.ETH;
  document.getElementById('dipAllocSol').value = allocs.SOL;

  const container = document.getElementById('dipPlannerCards');
  container.innerHTML = '';

  const cryptoPrices = state.prices?.crypto || FALLBACK_PRICES.crypto;
  ['BTC', 'ETH', 'SOL'].forEach(sym => {
    const pct = parseLocalizedNumber(allocs[sym], 0);
    const coinUsdBudget = summary.stableUsdTotal * (pct / 100);
    const plan = computeDipTiers(cryptoPrices[sym], coinUsdBudget);

    const rowsHtml = plan.tiers.map(t => `
      <tr>
        <td>${t.name}</td>
        <td><strong>$${fmtNum(t.levelUsd, sym === 'SOL' ? 1 : 0)}</strong></td>
        <td class="sensitive">$${fmtNum(t.tierUsd, 1)}</td>
        <td class="sensitive"><strong>${fmtNum(t.units, 4)} ${sym}</strong></td>
        <td><span class="badge ${t.triggered ? 'badge-success' : 'badge-info'}">${t.triggered ? 'در محدوده خرید' : 'انتظار'}</span></td>
      </tr>
    `).join('');

    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="section-header">
        <span class="section-title">${sym} — بودجه: $${fmtNum(coinUsdBudget, 2)} (${fmtNum(pct)}٪)</span>
        <span class="badge badge-info">قیمت: $${fmtNum(plan.priceUsd, 1)}</span>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.35rem; font-size:0.75rem; margin-bottom:0.6rem; color:var(--text-muted);">
        <div>فاصله از سقف تاریخی: <b style="color:var(--danger)">${fmtNum(plan.drawdownAthPct, 1)}٪</b></div>
        <div>فاصله از سقف ۹۰ روزه: <b style="color:var(--warning)">${fmtNum(plan.drawdown90dPct, 1)}٪</b></div>
        <div>میانگین ۲۰۰ روزه: <b>$${fmtNum(plan.ma200Usd, 0)}</b></div>
        <div>شاخص RSI(14): <b>${fmtNum(plan.rsi14, 1)}</b></div>
      </div>
      <div class="table-responsive">
        <table>
          <thead>
            <tr><th>پله</th><th>قیمت هدف</th><th>بودجه</th><th>مقدار واحد</th><th>وضعیت</th></tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderCashNftTab(summary) {
  const c = summary.cash;
  document.getElementById('cashAmountInput').value = c.cashToman;
  document.getElementById('cashTargetUsdtInput').value = c.targetUsdtToman;

  document.getElementById('cashBuysNowText').textContent = `${fmtNum(c.cashBuysUsdtNow, 1)} USDT`;
  document.getElementById('cashBuysTargetText').textContent = `${fmtNum(c.cashBuysUsdtAtTarget, 1)} USDT`;

  const badge = document.getElementById('cashTargetBadge');
  if (c.isTargetReached) {
    badge.className = 'badge badge-success';
    badge.textContent = '🎯 قیمت تتر به هدف خرید شما رسید!';
  } else {
    badge.className = 'badge badge-warning';
    badge.textContent = `فاصله تا هدف: ${fmtNum(c.targetDistancePct, 1)}٪ بالاتر`;
  }

  // Purchasing power erosion vs initial USD & Gold
  const initUsd = c.cashToman / c.initialUsdtToman;
  const initGold = c.cashToman / c.initialGold18kToman;
  const nowGold = c.cashToman / summary.rates.gold18kToman;

  document.getElementById('cashErosionText').textContent =
    `قدرت خرید اولیه: ${fmtNum(initUsd, 0)} دلار یا ${fmtNum(initGold, 2)} گرم طلای ۱۸ عیار | امروز: ${fmtNum(c.cashBuysUsdtNow, 0)} دلار یا ${fmtNum(nowGold, 2)} گرم طلا`;

  // NFTs Table
  const nftBody = document.getElementById('nftsTableBody');
  nftBody.innerHTML = '';
  summary.nfts.forEach((nf, idx) => {
    const sign = nf.pnlToman >= 0 ? '+' : '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${nf.name}</strong></td>
      <td><span class="badge badge-danger">${nf.category}</span></td>
      <td class="sensitive">${fmtMoney(nf.buyToman)}</td>
      <td>
        <input type="number" value="${nf.currentToman}" style="width:110px;" onchange="window.updateNftValue(${idx}, this.value)" />
      </td>
      <td class="sensitive" style="color:${nf.pnlToman >= 0 ? 'var(--success)' : 'var(--danger)'}; font-weight:700;">
        ${sign}${fmtMoney(nf.pnlToman)} (${sign}${fmtNum(nf.pnlPct, 1)}٪)
      </td>
    `;
    nftBody.appendChild(tr);
  });
}

function renderWhatIfTab(summary) {
  const periodKey = document.getElementById('whatIfPeriodSelect').value || '180d';
  const daysMap = { '30d': 30, '90d': 90, '180d': 180, '365d': 365 };
  const days = daysMap[periodKey] || 180;

  const initialCapInput = document.getElementById('whatIfCapitalInput');
  const initialCap = parseLocalizedNumber(initialCapInput.value, 150000000);
  const bankRate = parseLocalizedNumber(document.getElementById('whatIfBankRateInput').value, 23);

  const bmAll = state.prices?.benchmarks || FALLBACK_PRICES.benchmarks;
  const bm = bmAll[periodKey] || bmAll['180d'];

  const totalCost = summary.stocksCostToman + summary.stableValueFreeToman + summary.cash.cashToman + summary.nftsCostToman;
  const myRatio = totalCost > 0 ? summary.totalNetWorthToman / totalCost : 1.15;

  const rows = computeWhatIfTable(initialCap, days, myRatio, bm, bankRate);
  const tbody = document.getElementById('whatIfTableBody');
  tbody.innerHTML = '';

  rows.forEach((r, idx) => {
    const tr = document.createElement('tr');
    if (r.isMe) tr.style.background = 'var(--accent-soft)';
    tr.innerHTML = `
      <td>#${toPersianDigits(idx + 1)}</td>
      <td><strong>${r.title}</strong></td>
      <td class="sensitive"><strong>${fmtMoney(r.finalValue)}</strong></td>
      <td><span class="badge ${r.returnPct >= 0 ? 'badge-success' : 'badge-danger'}">+${fmtNum(r.returnPct, 1)}٪</span></td>
      <td class="sensitive" style="color:${r.diffFromMe >= 0 ? 'var(--success)' : 'var(--danger)'}">
        ${r.isMe ? 'سبد شما' : (r.diffFromMe >= 0 ? `${fmtMoney(r.diffFromMe)} جلوتر` : `${fmtMoney(Math.abs(r.diffFromMe))} عقب‌تر`)}
      </td>
    `;
    tbody.appendChild(tr);
  });

  const ctx = document.getElementById('whatIfBarCanvas').getContext('2d');
  if (state.charts.whatIf) state.charts.whatIf.destroy();

  state.charts.whatIf = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.title),
      datasets: [{
        label: 'ارزش نهایی (تومان)',
        data: rows.map(r => r.finalValue),
        backgroundColor: rows.map(r => r.isMe ? '#10b981' : '#3b82f6'),
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { family: 'Vazirmatn', size: 10 } } },
        y: { ticks: { color: '#94a3b8', font: { family: 'Vazirmatn', size: 10 } } }
      }
    }
  });
}

function renderRiskTab(summary) {
  const histStats = computeHistoryStats(state.history);
  const risk = computeRiskReport(summary, histStats);

  const circle = document.getElementById('riskScoreCircle');
  circle.textContent = toPersianDigits(risk.score);
  circle.style.borderColor = risk.score >= 65 ? 'var(--danger)' : (risk.score >= 40 ? 'var(--warning)' : 'var(--success)');

  const badge = document.getElementById('riskLevelBadge');
  badge.className = `badge ${risk.score >= 65 ? 'badge-danger' : (risk.score >= 40 ? 'badge-warning' : 'badge-success')}`;
  badge.textContent = risk.score >= 65 ? 'ریسک بالا' : (risk.score >= 40 ? 'ریسک متوسط رو به بالا' : 'ریسک متعادل');

  document.getElementById('riskMetricsBox').innerHTML = `
    <div>تمرکز سهم اول بورس (${risk.top1StockSymbol}): <strong>${fmtNum(risk.top1StockPct, 1)}٪</strong></div>
    <div>تمرکز ۳ سهم برتر بورس: <strong>${fmtNum(risk.top3StockPct, 1)}٪</strong></div>
    <div>شاخص هرفیندال (HHI): <strong>${fmtNum(risk.hhi, 0)}</strong></div>
    <div>حداکثر افت تاریخی (Max DD): <strong style="color:var(--danger)">${fmtNum(histStats.maxDrawdownPct, 1)}٪</strong></div>
    <div>نقدشوندگی آنی: <strong>${fmtNum(risk.liquidity.liquidPct, 1)}٪</strong> | نیمه‌نقدشونده: <strong>${fmtNum(risk.liquidity.semiLiquidPct, 1)}٪</strong></div>
    <div>دارایی غیرنقدشونده (NFT تلگرام): <strong style="color:var(--danger)">${fmtNum(risk.liquidity.illiquidPct, 1)}٪</strong></div>
    <div>مواجهه ارزی: <strong>${fmtNum(risk.currencyExposure.tomanPct, 1)}٪ ریالی</strong> در برابر <strong>${fmtNum(risk.currencyExposure.usdPct, 1)}٪ دلاری/TON</strong></div>
  `;

  const notes = [];
  if (risk.liquidity.illiquidPct > 20) {
    notes.push(`⚠️ <strong>هشدار نقدشوندگی NFT تلگرام:</strong> ${fmtNum(risk.liquidity.illiquidPct, 1)}٪ از کل ثروت شما در NFTهای تلگرام قرار دارد که دارایی غیرنقدشونده (Illiquid) و پرریسک محسوب می‌شود.`);
  }
  if (risk.top1StockPct > 25) {
    notes.push(`📌 <strong>تمرکز تک‌سهم:</strong> نماد «${risk.top1StockSymbol}» بیش از ${fmtNum(risk.top1StockPct, 1)}٪ از سبد بورس شما را تشکیل می‌دهد.`);
  }
  notes.push(`✅ <strong>ذخیره دلاری اتریوم:</strong> نگهداری $${fmtNum(summary.stableUsdTotal, 2)} استیبل‌کوین آماده شکار ریزش‌ها، پوشش ریسک ارزی مناسبی ایجاد کرده است.`);

  document.getElementById('riskSuggestionsList').innerHTML = notes
    .map(n => `<div style="padding:0.6rem; background:var(--bg-input); border-radius:8px; margin-bottom:0.45rem; font-size:0.78rem;">${n}</div>`)
    .join('');
}

// Global UI Handlers attached to window for inline HTML attributes
window.switchTab = function(tabId, btnEl) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
  btnEl.classList.add('active');
};

window.toggleTheme = function() {
  document.documentElement.classList.toggle('light');
};

window.togglePrivacy = function() {
  document.body.classList.toggle('privacy-blur');
};

window.toggleUnit = function() {
  state.unit = state.unit === 'toman' ? 'rial' : 'toman';
  document.getElementById('unitToggleBtn').textContent = state.unit === 'toman' ? 'تومان' : 'ریال';
  renderDashboard();
};

window.saveDipAllocations = function() {
  const b = parseLocalizedNumber(document.getElementById('dipAllocBtc').value, 50);
  const e = parseLocalizedNumber(document.getElementById('dipAllocEth').value, 30);
  const s = parseLocalizedNumber(document.getElementById('dipAllocSol').value, 20);
  state.portfolio.dipPlan = { allocations: { BTC: b, ETH: e, SOL: s } };
  state.portfolio.isSampleData = false;
  localStorage.setItem(STORAGE_KEY_PORTFOLIO, JSON.stringify(state.portfolio));
  renderDashboard();
};

window.saveCashConfig = function() {
  state.portfolio.cash.amountToman = parseLocalizedNumber(document.getElementById('cashAmountInput').value, 56000000);
  state.portfolio.cash.targetUsdtToman = parseLocalizedNumber(document.getElementById('cashTargetUsdtInput').value, 64500);
  state.portfolio.isSampleData = false;
  localStorage.setItem(STORAGE_KEY_PORTFOLIO, JSON.stringify(state.portfolio));
  renderDashboard();
};

window.updateNftValue = function(idx, newVal) {
  if (state.portfolio.nfts[idx]) {
    state.portfolio.nfts[idx].currentToman = parseLocalizedNumber(newVal, 0);
    state.portfolio.isSampleData = false;
    localStorage.setItem(STORAGE_KEY_PORTFOLIO, JSON.stringify(state.portfolio));
    renderDashboard();
  }
};

window.openPortfolioModal = function() {
  document.getElementById('portfolioJsonTextarea').value = JSON.stringify(state.portfolio, null, 2);
  document.getElementById('portfolioModal').classList.add('open');
};

window.closePortfolioModal = function() {
  document.getElementById('portfolioModal').classList.remove('open');
};

window.savePortfolioJson = function() {
  try {
    const parsed = JSON.parse(document.getElementById('portfolioJsonTextarea').value);
    parsed.isSampleData = false;
    state.portfolio = parsed;
    localStorage.setItem(STORAGE_KEY_PORTFOLIO, JSON.stringify(parsed));
    closePortfolioModal();
    renderDashboard();
  } catch (e) {
    alert('فرمت JSON نامعتبر است: ' + e.message);
  }
};

window.exportPortfolioFile = function() {
  const blob = new Blob([JSON.stringify(state.portfolio, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'portfolio.json';
  a.click();
};

window.importPortfolioFile = function(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const parsed = JSON.parse(e.target.result);
      parsed.isSampleData = false;
      state.portfolio = parsed;
      localStorage.setItem(STORAGE_KEY_PORTFOLIO, JSON.stringify(parsed));
      closePortfolioModal();
      renderDashboard();
    } catch {
      alert('فایل JSON انتخاب‌شده معتبر نیست.');
    }
  };
  reader.readAsText(file);
};

window.openManualPriceModal = function() {
  const box = document.getElementById('manualPricesFormBox');
  box.innerHTML = '';
  state.portfolio.stocks.forEach((s, i) => {
    const cur = state.prices?.stocks?.[s.symbol]?.priceToman ?? s.avgBuyToman;
    box.innerHTML += `
      <div class="form-group">
        <label>${s.symbol} (تومان):</label>
        <input type="number" id="manStock_${i}" value="${cur}" />
      </div>
    `;
  });
  box.innerHTML += `
    <div class="form-group">
      <label>نرخ تتر (تومان):</label>
      <input type="number" id="manUsdt" value="${state.prices?.fx?.usdtToman || 68400}" />
    </div>
    <div class="form-group">
      <label>نرخ دلار آزاد (تومان):</label>
      <input type="number" id="manUsdFree" value="${state.prices?.fx?.freeUsdToman || 68100}" />
    </div>
  `;
  document.getElementById('manualPriceModal').classList.add('open');
};

window.closeManualPriceModal = function() {
  document.getElementById('manualPriceModal').classList.remove('open');
};

window.saveManualPrices = function() {
  const stocksMap = { ...(state.prices.stocks || {}) };
  state.portfolio.stocks.forEach((s, i) => {
    const val = parseLocalizedNumber(document.getElementById(`manStock_${i}`).value, 0);
    if (val > 0) {
      stocksMap[s.symbol] = {
        ...(stocksMap[s.symbol] || {}),
        priceToman: val,
        stale: false,
        updatedAt: new Date().toISOString().slice(0, 10)
      };
    }
  });

  const usdt = parseLocalizedNumber(document.getElementById('manUsdt').value, 68400);
  const usdFree = parseLocalizedNumber(document.getElementById('manUsdFree').value, 68100);

  state.prices.stocks = stocksMap;
  state.prices.fx = { ...(state.prices.fx || {}), usdtToman: usdt, freeUsdToman: usdFree, stale: false };
  state.prices.lastUpdated = new Date().toISOString();

  localStorage.setItem(STORAGE_KEY_MANUAL_PRICES, JSON.stringify({
    fx: state.prices.fx,
    stocks: state.prices.stocks,
    lastUpdated: state.prices.lastUpdated
  }));

  closeManualPriceModal();
  renderDashboard();
};

window.renderHistoryChart = renderHistoryChart;
window.renderWhatIfTab = () => renderWhatIfTab(computePortfolioSummary(state.portfolio, state.prices));

window.addEventListener('DOMContentLoaded', initializeData);
