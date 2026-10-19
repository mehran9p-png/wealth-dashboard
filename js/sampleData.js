/**
 * داده‌های پیش‌فرض (Fallback) تعبیه‌شده در کد جاوااسکریپت
 * تضمین می‌کند حتی در صورت خطای شبکه یا باز کردن فایل به صورت آفلاین، هیچ عددی صفر نباشد.
 */

export const FALLBACK_PORTFOLIO = {
  isSampleData: true,
  lastEdited: "2026-10-19T12:00:00Z",
  stocks: [
    { symbol: "فپنتا", name: "صندوق سرمایه‌گذاری پنتا", sector: "فلزات اساسی", qty: 1489, avgBuyToman: 4450, insCode: "17914401175772326" },
    { symbol: "وفیروزه", name: "صندوق فیروزه موفقیت", sector: "صندوق سهامی", qty: 7749, avgBuyToman: 560, insCode: "55254206302462116" },
    { symbol: "شپدیس", name: "پتروشیمی پردیس", sector: "پتروشیمی", qty: 3139, avgBuyToman: 1180, insCode: "44891482026867833" },
    { symbol: "فهامون", name: "صندوق سرمایه‌گذاری هامون", sector: "فلزات اساسی", qty: 3607, avgBuyToman: 610, insCode: "38232437866669967" },
    { symbol: "فکور", name: "صندوق سرمایه‌گذاری کوروش", sector: "صندوق بخشی", qty: 1240, avgBuyToman: 590, insCode: "66442254613568889" },
    { symbol: "فپردیس", name: "صندوق سرمایه‌گذاری پردیس", sector: "صندوق سهامی", qty: 62, avgBuyToman: 8200, insCode: "41933952242799993" },
    { symbol: "وسرمایه", name: "صندوق سرمایه‌گذاری سرمایه", sector: "صندوق سهامی", qty: 658, avgBuyToman: 430, insCode: "21963356012832211" },
    { symbol: "زشک", name: "کشاورزی و دامپروری زشک", sector: "زراعت", qty: 211, avgBuyToman: 1190, insCode: "61449234123698745" },
    { symbol: "فساپ", name: "صندوق سرمایه‌گذاری ساپ", sector: "صندوق بخشی", qty: 212, avgBuyToman: 420, insCode: "51617145879012365" }
  ],
  stablecoins: [
    { symbol: "LUSD", network: "Ethereum", amount: 406.90, pegUsd: 1.004 },
    { symbol: "USDT", network: "Ethereum", amount: 5.49, pegUsd: 1.000 }
  ],
  dipPlan: {
    allocations: { BTC: 50, ETH: 30, SOL: 20 }
  },
  cash: {
    amountToman: 56000000,
    targetUsdtToman: 64500,
    initialUsdtToman: 62000,
    initialGold18kToman: 4100000
  },
  nfts: [
    { id: "nft-1", name: "Plush Pepe Gift #104", category: "Telegram Gift", buyToman: 24000000, currentToman: 28500000 },
    { id: "nft-2", name: "Fragment Username @...", category: "Username", buyToman: 18000000, currentToman: 19500000 },
    { id: "nft-3", name: "Anonymous Number +888", category: "Number", buyToman: 14000000, currentToman: 15000000 }
  ],
  whatIfConfig: {
    bankRateAnnual: 23
  }
};

export const FALLBACK_PRICES = {
  lastUpdated: "2026-10-19T12:30:00Z",
  fx: {
    usdtToman: 68400,
    freeUsdToman: 68100,
    gold18kToman: 4580000,
    stale: false
  },
  stocks: {
    "فپنتا": { priceToman: 4725, dailyChangePct: -0.95, stale: false, updatedAt: "2026-10-19" },
    "وفیروزه": { priceToman: 615, dailyChangePct: 2.84, stale: false, updatedAt: "2026-10-19" },
    "شپدیس": { priceToman: 1266, dailyChangePct: 2.92, stale: false, updatedAt: "2026-10-19" },
    "فهامون": { priceToman: 659, dailyChangePct: 2.97, stale: false, updatedAt: "2026-10-19" },
    "فکور": { priceToman: 632, dailyChangePct: 2.93, stale: false, updatedAt: "2026-10-19" },
    "فپردیس": { priceToman: 8858, dailyChangePct: 3.00, stale: false, updatedAt: "2026-10-19" },
    "وسرمایه": { priceToman: 463, dailyChangePct: 2.89, stale: false, updatedAt: "2026-10-19" },
    "زشک": { priceToman: 1293, dailyChangePct: 2.95, stale: false, updatedAt: "2026-10-19" },
    "فساپ": { priceToman: 456, dailyChangePct: 2.93, stale: false, updatedAt: "2026-10-19" }
  },
  crypto: {
    BTC: { priceUsd: 68450, athUsd: 73750, high1yUsd: 73750, high90dUsd: 70200, ma200Usd: 63400, rsi14: 54.2, stale: false },
    ETH: { priceUsd: 2725, athUsd: 4878, high1yUsd: 4090, high90dUsd: 3420, ma200Usd: 2980, rsi14: 46.8, stale: false },
    SOL: { priceUsd: 158.4, athUsd: 259.9, high1yUsd: 209.0, high90dUsd: 188.5, ma200Usd: 151.2, rsi14: 51.5, stale: false },
    USDT: { priceUsd: 1.0, stale: false }
  },
  benchmarks: {
    "30d": { tedpix: 1.04, gold18k: 1.08, usdFree: 1.06, btcToman: 1.11, ethToman: 1.03, inflation: 1.03 },
    "90d": { tedpix: 1.09, gold18k: 1.17, usdFree: 1.12, btcToman: 1.21, ethToman: 1.06, inflation: 1.09 },
    "180d": { tedpix: 1.15, gold18k: 1.31, usdFree: 1.19, btcToman: 1.34, ethToman: 1.11, inflation: 1.18 },
    "365d": { tedpix: 1.22, gold18k: 1.49, usdFree: 1.35, btcToman: 1.63, ethToman: 1.20, inflation: 1.38 }
  },
  sources: {
    usdtToman: "embedded_sample",
    BTC: "embedded_sample"
  }
};

export const FALLBACK_HISTORY = [
  { date: "2026-09-18", totalToman: 151200000 },
  { date: "2026-09-19", totalToman: 151450000 },
  { date: "2026-09-20", totalToman: 152100000 },
  { date: "2026-09-21", totalToman: 151800000 },
  { date: "2026-09-22", totalToman: 152900000 },
  { date: "2026-09-23", totalToman: 153400000 },
  { date: "2026-09-24", totalToman: 153100000 },
  { date: "2026-09-25", totalToman: 153600000 },
  { date: "2026-09-26", totalToman: 154200000 },
  { date: "2026-09-27", totalToman: 154900000 },
  { date: "2026-09-28", totalToman: 154300000 },
  { date: "2026-09-29", totalToman: 155100000 },
  { date: "2026-09-30", totalToman: 155800000 },
  { date: "2026-10-01", totalToman: 156200000 },
  { date: "2026-10-02", totalToman: 156000000 },
  { date: "2026-10-03", totalToman: 156900000 },
  { date: "2026-10-04", totalToman: 157500000 },
  { date: "2026-10-05", totalToman: 157100000 },
  { date: "2026-10-06", totalToman: 158000000 },
  { date: "2026-10-07", totalToman: 158600000 },
  { date: "2026-10-08", totalToman: 159200000 },
  { date: "2026-10-09", totalToman: 159500000 },
  { date: "2026-10-10", totalToman: 160100000 },
  { date: "2026-10-11", totalToman: 159800000 },
  { date: "2026-10-12", totalToman: 160700000 },
  { date: "2026-10-13", totalToman: 161400000 },
  { date: "2026-10-14", totalToman: 162100000 },
  { date: "2026-10-15", totalToman: 163000000 },
  { date: "2026-10-16", totalToman: 163800000 },
  { date: "2026-10-17", totalToman: 164900000 },
  { date: "2026-10-18", totalToman: 166100000 },
  { date: "2026-10-19", totalToman: 167303527 }
];
