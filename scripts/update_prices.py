#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
from datetime import datetime, timezone
import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(ROOT_DIR, "data", "portfolio.json")
PRICES_FILE = os.path.join(ROOT_DIR, "data", "prices.json")
HISTORY_FILE = os.path.join(ROOT_DIR, "data", "history.json")

HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/128.0.0.0 Safari/537.36"}
MIN_FREE_USD_TOMAN = 150000


def fast_get(url, timeout=(2.5, 3.5)):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[Skip] {url}: {e}")
    return None


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json(PORTFOLIO_FILE, {})
    prices = load_json(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}, "sources": {}})
    history = load_json(HISTORY_FILE, [])
    sources = prices.get("sources", {})

    # ۱. دریافت سریع نرخ تتر و دلار آزاد (حداکثر ۳ ثانیه)
    usdt_toman = None
    nob = fast_get("https://apiv2.nobitex.ir/v3/orderbook/USDTIRT")
    if isinstance(nob, dict) and nob.get("lastTradePrice"):
        val = round(float(nob["lastTradePrice"]) / 10.0)
        if val >= MIN_FREE_USD_TOMAN:
            usdt_toman = val
            sources["usdtToman"] = "nobitex"

    if not usdt_toman:
        tl = fast_get("https://api.tetherland.com/currencies")
        if isinstance(tl, dict):
            p = tl.get("data", {}).get("currencies", {}).get("USDT", {}).get("price")
            if p and float(p) >= MIN_FREE_USD_TOMAN:
                usdt_toman = round(float(p))
                sources["usdtToman"] = "tetherland"

    prev_usdt = prices.get("fx", {}).get("usdtToman", 262000)
    if prev_usdt < MIN_FREE_USD_TOMAN:
        prev_usdt = 262000

    final_usdt = usdt_toman if usdt_toman else prev_usdt
    prices["fx"] = {
        "usdtToman": final_usdt,
        "freeUsdToman": round(final_usdt * 0.996),
        "gold18kToman": 17850000,
        "stale": not bool(usdt_toman)
    }

    # ۲. بررسی TSETMC با Circuit Breaker (اگر اولین سهم تایم‌اوت داد، بقیه را معطل نکن)
    stocks_map = prices.get("stocks", {})
    tsetmc_reachable = True
    total_stocks_toman = 0

    for s in portfolio.get("stocks", []):
        sym = s["symbol"]
        ins = s.get("insCode", "")
        qty = float(s.get("qty", 0))
        prev_s = stocks_map.get(sym, {"priceToman": s.get("avgBuyToman", 1000), "dailyChangePct": 0.0})

        if tsetmc_reachable and ins:
            d = fast_get(f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins}", timeout=(2.0, 2.5))
            if isinstance(d, dict) and "closingPriceInfo" in d:
                info = d["closingPriceInfo"]
                raw_p = info.get("pDrCotVal") or info.get("pClosing")
                if raw_p and float(raw_p) > 0:
                    stocks_map[sym] = {"priceToman": round(float(raw_p) / 10.0), "dailyChangePct": 0.0, "stale": False}
                    sources[sym] = "tsetmc"
            else:
                # آی‌پی گیت‌هاب توسط فایروال بورس ایران بلاک است؛ بقیه نمادها را بدون معطلی از کش بخوان
                tsetmc_reachable = False
                prev_s["stale"] = True
                stocks_map[sym] = prev_s
                sources[sym] = "cached_firewall_bypass"
        else:
            prev_s["stale"] = True
            stocks_map[sym] = prev_s
            sources[sym] = "cached_firewall_bypass"

        total_stocks_toman += qty * stocks_map[sym]["priceToman"]

    prices["stocks"] = stocks_map

    # ۳. دریافت سریع قیمت BTC, ETH, SOL از بایننس/کوین‌گکو
    crypto_map = prices.get("crypto", {})
    cg = fast_get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
    if isinstance(cg, dict):
        for sym, cid in [("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana")]:
            usd_p = cg.get(cid, {}).get("usd")
            if usd_p:
                old_c = crypto_map.get(sym, {})
                old_c["priceUsd"] = float(usd_p)
                old_c["stale"] = False
                crypto_map[sym] = old_c
                sources[sym] = "coingecko"

    prices["crypto"] = crypto_map
    prices["sources"] = sources
    prices["lastUpdated"] = now_iso
    save_json(PRICES_FILE, prices)

    # ۴. ثبت اسنپ‌شات روزانه
    stable_usd = sum(float(x.get("amount", 0)) * float(x.get("pegUsd", 1)) for x in portfolio.get("stablecoins", []))
    cash_t = float(portfolio.get("cash", {}).get("amountToman", 56000000))
    nfts_t = sum(float(x.get("currentToman", 0)) for x in portfolio.get("nfts", []))
    net_worth = round(total_stocks_toman + (stable_usd * final_usdt) + cash_t + nfts_t)

    if isinstance(history, list) and history and history[-1].get("date") == today_str:
        history[-1]["totalToman"] = net_worth
    else:
        history.append({"date": today_str, "totalToman": net_worth})
    save_json(HISTORY_FILE, history)
    print(f"Done in <10s! Net worth: {net_worth:,} Toman")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error:", e)
    sys.exit(0)
