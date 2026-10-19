#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت بروزرسانی خودکار قیمت‌های بورس ایران، نرخ واقعی دلار بازار آزاد / تتر (حدود ۲۶۲ هزار تومان)
و رمزارزها روی GitHub Actions
- دارای فیلتر ضد دلار دولتی (رد کردن هر نرخی زیر ۱۵۰ هزار تومان)
- دریافت مستقیم از ۴ منبع بازار آزاد: نوبیتکس، تترلند، والکس و صفحه بازار آزاد
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(ROOT_DIR, "data", "portfolio.json")
PRICES_FILE = os.path.join(ROOT_DIR, "data", "prices.json")
HISTORY_FILE = os.path.join(ROOT_DIR, "data", "history.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}

# حداقل نرخ منطقی برای دلار بازار آزاد (هر عددی زیر ۱۵۰ هزار تومان دلار دولتی/نیمایی محسوب شده و رد می‌شود)
MIN_VALID_FREE_MARKET_TOMAN = 150000


def http_get_json(url, timeout=10, retries=3, delay=2.0):
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            print(f"[Attempt {attempt}/{retries}] Failed {url}: {exc}")
        if attempt < retries:
            time.sleep(delay)
    return None


def load_json_safe(path, default_val):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print(f"[WARN] Could not read {path}: {exc}")
    return default_val


def save_json_safe(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[ERROR] Could not write {path}: {exc}")


def calculate_rsi14(closes):
    if not closes or len(closes) < 15:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    avg_gain = sum(gains[:14]) / 14.0
    avg_loss = sum(losses[:14]) / 14.0
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * 13.0 + gains[i]) / 14.0
        avg_loss = (avg_loss * 13.0 + losses[i]) / 14.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def fetch_free_market_usdt_and_usd():
    """
    دریافت نرخ واقعی تتر و دلار بازار آزاد ایران (رد کردن کامل نرخ‌های دولتی/مرکز مبادله)
    """
    # منبع ۱: دفتر سفارشات لحظه‌ای نوبیتکس (USDTIRT به ریال است -> تقسیم بر ۱۰ برای تومان)
    data1 = http_get_json("https://apiv2.nobitex.ir/v3/orderbook/USDTIRT")
    if isinstance(data1, dict) and data1.get("lastTradePrice"):
        toman_val = round(float(data1["lastTradePrice"]) / 10.0)
        if toman_val >= MIN_VALID_FREE_MARKET_TOMAN:
            return toman_val, round(toman_val * 0.996), "nobitex_v3_free_market"

    # منبع ۲: آمار بازار نوبیتکس
    data2 = http_get_json("https://apiv2.nobitex.ir/market/stats?srcCurrency=usdt&dstCurrency=rls")
    if isinstance(data2, dict):
        latest_rial = data2.get("stats", {}).get("usdt-rls", {}).get("latest")
        if latest_rial:
            toman_val = round(float(latest_rial) / 10.0)
            if toman_val >= MIN_VALID_FREE_MARKET_TOMAN:
                return toman_val, round(toman_val * 0.996), "nobitex_stats_free_market"

    # منبع ۳: وب‌سرویس عمومی تترلند (مستقیم به تومان)
    data3 = http_get_json("https://api.tetherland.com/currencies")
    if isinstance(data3, dict):
        usdt_info = data3.get("data", {}).get("currencies", {}).get("USDT", {})
        price_toman = usdt_info.get("price")
        if price_toman:
            toman_val = round(float(price_toman))
            if toman_val >= MIN_VALID_FREE_MARKET_TOMAN:
                return toman_val, round(toman_val * 0.996), "tetherland_free_market"

    # منبع ۴: وب‌سرویس عمومی صرافی والکس (Wallex)
    data4 = http_get_json("https://api.wallex.ir/v1/markets")
    if isinstance(data4, dict):
        symbols = data4.get("result", {}).get("symbols", {})
        usdt_tmns = symbols.get("USDTTMN", {}).get("stats", {}).get("lastPrice")
        if usdt_tmns:
            toman_val = round(float(usdt_tmns))
            if toman_val >= MIN_VALID_FREE_MARKET_TOMAN:
                return toman_val, round(toman_val * 0.996), "wallex_free_market"

    return None, None, None


def fetch_stock_price(symbol, ins_code):
    if ins_code:
        url1 = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins_code}"
        data1 = http_get_json(url1)
        if isinstance(data1, dict) and "closingPriceInfo" in data1:
            info = data1["closingPriceInfo"]
            raw_p = info.get("pDrCotVal") or info.get("pClosing")
            prev_p = info.get("priceYesterday")
            if raw_p and float(raw_p) > 0:
                price_toman = round(float(raw_p) / 10.0)
                chg = 0.0
                if prev_p and float(prev_p) > 0:
                    chg = round(((float(raw_p) - float(prev_p)) / float(prev_p)) * 100.0, 2)
                return price_toman, chg, "tsetmc_cdn_api"

    if ins_code:
        url2 = f"https://d.easytrader.ir/market/watch/symbol/{ins_code}"
        data2 = http_get_json(url2, retries=1)
        if isinstance(data2, dict) and data2.get("lastPrice"):
            price_toman = round(float(data2["lastPrice"]) / 10.0)
            chg = round(float(data2.get("ChangePercent", 0.0)), 2)
            if price_toman > 0:
                return price_toman, chg, "mofid_easytrader_public"

    return None, None, None


def fetch_crypto_symbol(symbol, default_ath):
    pair = f"{symbol}USDT"
    klines = http_get_json(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1d&limit=365")
    if isinstance(klines, list) and len(klines) > 30:
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        price = closes[-1]
        if price > 0:
            high_1y = max(highs)
            high_90d = max(highs[-90:]) if len(highs) >= 90 else high_1y
            ma200 = sum(closes[-200:]) / min(200, len(closes))
            rsi = calculate_rsi14(closes)
            return {
                "priceUsd": round(price, 2),
                "athUsd": max(default_ath, round(high_1y, 2)),
                "high1yUsd": round(high_1y, 2),
                "high90dUsd": round(high_90d, 2),
                "ma200Usd": round(ma200, 2),
                "rsi14": rsi,
                "stale": False
            }, "binance_klines_1d"

    cg_ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    cg_id = cg_ids.get(symbol)
    if cg_id:
        cg = http_get_json(f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd")
        if isinstance(cg, dict) and cg.get(cg_id, {}).get("usd"):
            p = float(cg[cg_id]["usd"])
            if p > 0:
                return {
                    "priceUsd": round(p, 2),
                    "athUsd": default_ath,
                    "high1yUsd": default_ath,
                    "high90dUsd": round(p * 1.12, 2),
                    "ma200Usd": round(p * 0.92, 2),
                    "rsi14": 50.0,
                    "stale": False
                }, "coingecko_simple_price"

    return None, None


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json_safe(PORTFOLIO_FILE, {})
    prices = load_json_safe(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}, "sources": {}})
    history = load_json_safe(HISTORY_FILE, [])

    sources_log = prices.get("sources", {})

    # ۱. بروزرسانی نرخ تتر و دلار بازار آزاد (با محافظت در برابر نرخ دولتی)
    prev_fx = prices.get("fx", {})
    prev_usdt = prev_fx.get("usdtToman", 262000)
    if prev_usdt < MIN_VALID_FREE_MARKET_TOMAN:
        prev_usdt = 262000

    prev_free_usd = prev_fx.get("freeUsdToman", 261500)
    if prev_free_usd < MIN_VALID_FREE_MARKET_TOMAN:
        prev_free_usd = 261500

    usdt_val, free_usd_val, fx_src = fetch_free_market_usdt_and_usd()
    if usdt_val and usdt_val >= MIN_VALID_FREE_MARKET_TOMAN:
        prices["fx"] = {
            "usdtToman": usdt_val,
            "freeUsdToman": free_usd_val,
            "gold18kToman": prev_fx.get("gold18kToman", 17850000),
            "stale": False
        }
        sources_log["usdtToman"] = fx_src
        sources_log["freeUsdToman"] = fx_src
    else:
        prices["fx"] = {
            "usdtToman": prev_usdt,
            "freeUsdToman": prev_free_usd,
            "gold18kToman": prev_fx.get("gold18kToman", 17850000),
            "stale": True
        }
        sources_log["usdtToman"] = f"cached_free_market ({prev_usdt})"

    usdt_rate = prices["fx"]["usdtToman"]

    # ۲. بروزرسانی سهام بورس ایران
    stocks_map = prices.get("stocks", {})
    total_stocks_toman = 0

    for item in portfolio.get("stocks", []):
        sym = item.get("symbol")
        ins_code = item.get("insCode", "")
        qty = float(item.get("qty", 0))
        prev_s = stocks_map.get(sym, {
            "priceToman": item.get("avgBuyToman", 1000),
            "dailyChangePct": 0.0,
            "stale": True,
            "updatedAt": today_str
        })

        p_toman, chg_pct, src_name = fetch_stock_price(sym, ins_code)
        if p_toman and p_toman > 0:
            stocks_map[sym] = {
                "priceToman": p_toman,
                "dailyChangePct": chg_pct,
                "stale": False,
                "updatedAt": today_str
            }
            sources_log[sym] = src_name
        else:
            prev_s["stale"] = True
            stocks_map[sym] = prev_s
            sources_log[sym] = f"cached_stale_from_{prev_s.get('updatedAt', 'unknown')}"

        total_stocks_toman += qty * stocks_map[sym]["priceToman"]

    prices["stocks"] = stocks_map

    # ۳. بروزرسانی رمزارزها
    crypto_map = prices.get("crypto", {})
    aths = {"BTC": 73750, "ETH": 4878, "SOL": 259.9}
    for sym, ath_val in aths.items():
        prev_c = crypto_map.get(sym, {
            "priceUsd": 1000, "athUsd": ath_val, "high1yUsd": ath_val,
            "high90dUsd": ath_val, "ma200Usd": ath_val * 0.85, "rsi14": 50.0, "stale": True
        })
        c_data, c_src = fetch_crypto_symbol(sym, ath_val)
        if c_data:
            crypto_map[sym] = c_data
            sources_log[sym] = c_src
        else:
            prev_c["stale"] = True
            crypto_map[sym] = prev_c
            sources_log[sym] = "cached_stale"

    crypto_map["USDT"] = {"priceUsd": 1.0, "stale": False}
    prices["crypto"] = crypto_map
    prices["sources"] = sources_log
    prices["lastUpdated"] = now_iso

    save_json_safe(PRICES_FILE, prices)

    # ۴. محاسبه ارزش کل ثروت با دلار بازار آزاد و ذخیره در تاریخچه روزانه
    stable_usd = sum(
        float(st.get("amount", 0)) * float(st.get("pegUsd", 1.0))
        for st in portfolio.get("stablecoins", [])
    )
    stable_toman = stable_usd * usdt_rate
    cash_toman = float(portfolio.get("cash", {}).get("amountToman", 0))
    nfts_toman = sum(float(nf.get("currentToman", 0)) for nf in portfolio.get("nfts", []))

    net_worth_toman = round(total_stocks_toman + stable_toman + cash_toman + nfts_toman)

    if net_worth_toman > 0:
        if isinstance(history, list) and len(history) > 0 and history[-1].get("date") == today_str:
            history[-1]["totalToman"] = net_worth_toman
        else:
            history.append({"date": today_str, "totalToman": net_worth_toman})
        save_json_safe(HISTORY_FILE, history)

    print(f"[OK] Updated at {now_iso}. Free Market USDT={usdt_rate:,} Toman | Net Worth={net_worth_toman:,} Toman")


if __name__ == "__main__":
    try:
        main()
    except Exception as fatal_err:
        print(f"[NON-FATAL GUARD] Script caught top-level error: {fatal_err}")
    sys.exit(0)
