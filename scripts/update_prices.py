#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت بروزرسانی خودکار بورس ایران (از طریق BrsApi.ir و TSETMC) + دلار آزاد ۲۶۲ هزار تومانی + کریپتو
"""
import json
import os
import sys
from datetime import datetime, timezone
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(ROOT_DIR, "data", "portfolio.json")
PRICES_FILE = os.path.join(ROOT_DIR, "data", "prices.json")
HISTORY_FILE = os.path.join(ROOT_DIR, "data", "history.json")

# هدر استاندارد مرورگر برای عبور از فایروال BrsApi و TSETMC
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Accept": "application/json, text/plain, */*"
}

BRS_API_KEY = "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG"
MIN_FREE_USD = 150000


def norm_fa(text):
    if not text:
        return ""
    return str(text).strip().replace("ي", "ی").replace("ك", "ک").replace("\u200c", "")


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_usdt():
    for url in [
        "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT",
        "https://api.tetherland.com/currencies"
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=5, verify=False)
            if r.status_code == 200:
                d = r.json()
                if "lastTradePrice" in d:
                    v = round(float(d["lastTradePrice"]) / 10.0)
                    if v >= MIN_FREE_USD:
                        return v, "nobitex"
                p = d.get("data", {}).get("currencies", {}).get("USDT", {}).get("price")
                if p and float(p) >= MIN_FREE_USD:
                    return round(float(p)), "tetherland"
        except Exception:
            pass
    return None, None


def fetch_all_bourse_via_brsapi():
    """دریافت یکجای تمام نمادهای بورس، فرابورس و صندوق‌های ETF از BrsApi.ir"""
    url = f"https://Api.BrsApi.ir/Tsetmc/AllSymbols.php?key={BRS_API_KEY}&type=1"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 50:
                result = {}
                for item in data:
                    sym = norm_fa(item.get("l18", ""))
                    rial_p = item.get("pl") or item.get("pc")
                    chg = item.get("pcp") or 0.0
                    if sym and rial_p and float(rial_p) > 0:
                        result[sym] = {
                            "priceToman": round(float(rial_p) / 10.0),
                            "dailyChangePct": round(float(chg), 2)
                        }
                return result
    except Exception as e:
        print("BrsApi skip:", e)
    return {}


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json(PORTFOLIO_FILE, {})
    prices = load_json(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}, "sources": {}})
    history = load_json(HISTORY_FILE, [])
    sources = prices.get("sources", {})

    # ۱. نرخ دلار آزاد و تتر
    usdt_val, fx_src = fetch_usdt()
    prev_usdt = prices.get("fx", {}).get("usdtToman", 262000)
    if prev_usdt < MIN_FREE_USD:
        prev_usdt = 262000
    final_usdt = usdt_val if usdt_val else prev_usdt

    prices["fx"] = {
        "usdtToman": final_usdt,
        "freeUsdToman": round(final_usdt * 0.996),
        "gold18kToman": 17850000,
        "stale": not bool(usdt_val)
    }
    if fx_src:
        sources["usdtToman"] = fx_src

    # ۲. بروزرسانی تمام نمادهای بورس ایران با BrsApi
    brs_map = fetch_all_bourse_via_brsapi()
    stocks_map = prices.get("stocks", {})
    total_stocks = 0

    for s in portfolio.get("stocks", []):
        sym = s.get("symbol", "")
        norm_sym = norm_fa(sym)
        qty = float(s.get("qty", 0))
        prev_s = stocks_map.get(sym, {"priceToman": s.get("avgBuyToman", 1000), "dailyChangePct": 0.0})

        if norm_sym in brs_map:
            stocks_map[sym] = {
                "priceToman": brs_map[norm_sym]["priceToman"],
                "dailyChangePct": brs_map[norm_sym]["dailyChangePct"],
                "stale": False,
                "updatedAt": today_str
            }
            sources[sym] = "brsapi_tsetmc"
        else:
            prev_s["stale"] = True
            stocks_map[sym] = prev_s

        total_stocks += qty * float(stocks_map[sym].get("priceToman", 0))

    prices["stocks"] = stocks_map

    # ۳. بروزرسانی بیت‌کوین، اتریوم و سولانا
    crypto_map = prices.get("crypto", {})
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd",
            headers=HEADERS, timeout=6
        )
        if r.status_code == 200:
            cg = r.json()
            for sym, cid in [("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana")]:
                p = cg.get(cid, {}).get("usd")
                if p:
                    old_c = crypto_map.get(sym, {})
                    old_c["priceUsd"] = float(p)
                    old_c["stale"] = False
                    crypto_map[sym] = old_c
                    sources[sym] = "coingecko"
    except Exception:
        pass

    prices["crypto"] = crypto_map
    prices["sources"] = sources
    prices["lastUpdated"] = now_iso
    save_json(PRICES_FILE, prices)

    # ۴. ثبت اسنپ‌شات روزانه
    stable_usd = sum(float(x.get("amount", 0)) * float(x.get("pegUsd", 1)) for x in portfolio.get("stablecoins", []))
    cash_t = float(portfolio.get("cash", {}).get("amountToman", 56000000))
    nfts_t = sum(float(x.get("currentToman", 0)) for x in portfolio.get("nfts", []))
    net_worth = round(total_stocks + (stable_usd * final_usdt) + cash_t + nfts_t)

    if net_worth > 0:
        if isinstance(history, list) and history and history[-1].get("date") == today_str:
            history[-1]["totalToman"] = net_worth
        else:
            history.append({"date": today_str, "totalToman": net_worth})
        save_json(HISTORY_FILE, history)

    print("Updated successfully! Net worth:", net_worth)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Handled error:", e)
    sys.exit(0)
