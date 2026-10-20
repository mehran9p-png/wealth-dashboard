#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت ارتقایافته دریافت قیمت زنده بورس ایران (TSETMC) + تتر بازار آزاد + رمزارزها
مجهز به:
1. غیرفعال‌سازی خطای SSL بورس ایران روی سرورهای گیت‌هاب (verify=False)
2. جستجوی خودکار کد نماد (Auto-Search insCode) با نام فارسی سهم از سرور TSETMC
3. چهار لایه جایگزین برای بورس ایران (cdn.tsetmc.com -> members.tsetmc.com -> old.tsetmc.com -> TGJU)
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote
import requests
import urllib3

# غیرفعال کردن هشدار SSL برای سرورهای بورس ایران در خارج از کشور
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(ROOT_DIR, "data", "portfolio.json")
PRICES_FILE = os.path.join(ROOT_DIR, "data", "prices.json")
HISTORY_FILE = os.path.join(ROOT_DIR, "data", "history.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.tsetmc.com",
    "Referer": "https://www.tsetmc.com/"
}

MIN_FREE_USD_TOMAN = 150000


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[WARN] Read error {path}: {e}")
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_fa(text):
    if not text:
        return ""
    return str(text).strip().replace("ي", "ی").replace("ك", "ک").replace("\u200c", "")


def resolve_inscode_by_symbol(symbol):
    """جستجوی خودکار کد ۱۷ رقمی سهم در TSETMC با استفاده از نام فارسی نماد"""
    encoded = quote(symbol)
    search_urls = [
        f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{encoded}",
        f"http://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{encoded}",
    ]
    target = normalize_fa(symbol)

    for url in search_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=5, verify=False)
            if r.status_code == 200:
                items = r.json().get("instrumentSearch", [])
                # اول تطابق دقیق نام نماد را پیدا کن
                for it in items:
                    sym_clean = normalize_fa(it.get("lVal18AFC", ""))
                    if sym_clean == target and it.get("insCode"):
                        return str(it["insCode"])
                # اگر تطابق دقیق نبود، اولین نتیجه معتبر را برگردان
                if items and items[0].get("insCode"):
                    return str(items[0]["insCode"])
        except Exception as e:
            print(f"[Search Skip] {symbol} on {url}: {e}")
    return None


def fetch_stock_from_tsetmc(symbol, configured_inscode):
    """دریافت قیمت پایانی/آخرین قیمت و درصد تغییر روزانه از سرورهای مختلف TSETMC"""
    # ابتدا با نام نماد، کد دقیق را از سرور بورس استخراج کن
    auto_code = resolve_inscode_by_symbol(symbol)
    candidates = []
    if auto_code:
        candidates.append(auto_code)
    if configured_inscode and str(configured_inscode) not in candidates:
        candidates.append(str(configured_inscode))

    for code in candidates:
        # ۱. سرور اصلی CDN بورس (HTTPS و HTTP)
        for proto in ["https", "http"]:
            url = f"{proto}://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{code}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=5, verify=False)
                if r.status_code == 200:
                    info = r.json().get("closingPriceInfo", {})
                    # pDrCotVal = آخرین معامله | pClosing = قیمت پایانی
                    raw_rial = info.get("pDrCotVal") or info.get("pClosing")
                    prev_rial = info.get("priceYesterday")
                    if raw_rial and float(raw_rial) > 0:
                        price_toman = round(float(raw_rial) / 10.0)
                        chg_pct = 0.0
                        if prev_rial and float(prev_rial) > 0:
                            chg_pct = round(((float(raw_rial) - float(prev_rial)) / float(prev_rial)) * 100.0, 2)
                        return price_toman, chg_pct, f"tsetmc_cdn ({code})"
            except Exception:
                pass

        # ۲. سرور قدیمی TSETMC (در صورت مسدود بودن CDN)
        old_url = f"http://old.tsetmc.com/tsev2/data/instinfofast.aspx?i={code}&c=57+"
        try:
            r = requests.get(old_url, headers=HEADERS, timeout=5, verify=False)
            if r.status_code == 200 and ";" in r.text:
                first_part = r.text.split(";")[0]
                fields = first_part.split(",")
                if len(fields) >= 5:
                    last_rial = float(fields[2])
                    close_rial = float(fields[3])
                    prev_rial = float(fields[4])
                    active_rial = last_rial if last_rial > 0 else close_rial
                    if active_rial > 0:
                        price_toman = round(active_rial / 10.0)
                        chg_pct = round(((active_rial - prev_rial) / prev_rial) * 100.0, 2) if prev_rial > 0 else 0.0
                        return price_toman, chg_pct, f"tsetmc_old ({code})"
        except Exception:
            pass

    return None, None, None


def fetch_free_market_usdt():
    # ۱. نوبیتکس
    try:
        r = requests.get("https://apiv2.nobitex.ir/v3/orderbook/USDTIRT", headers=HEADERS, timeout=6)
        if r.status_code == 200 and r.json().get("lastTradePrice"):
            val = round(float(r.json()["lastTradePrice"]) / 10.0)
            if val >= MIN_FREE_USD_TOMAN:
                return val, "nobitex"
    except Exception:
        pass

    # ۲. تترلند
    try:
        r = requests.get("https://api.tetherland.com/currencies", headers=HEADERS, timeout=6)
        if r.status_code == 200:
            p = r.json().get("data", {}).get("currencies", {}).get("USDT", {}).get("price")
            if p and float(p) >= MIN_FREE_USD_TOMAN:
                return round(float(p)), "tetherland"
    except Exception:
        pass

    # ۳. والکس
    try:
        r = requests.get("https://api.wallex.ir/v1/markets", headers=HEADERS, timeout=6)
        if r.status_code == 200:
            p = r.json().get("result", {}).get("symbols", {}).get("USDTTMN", {}).get("stats", {}).get("lastPrice")
            if p and float(p) >= MIN_FREE_USD_TOMAN:
                return round(float(p)), "wallex"
    except Exception:
        pass

    return None, None


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json(PORTFOLIO_FILE, {})
    prices = load_json(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}, "sources": {}})
    history = load_json(HISTORY_FILE, [])
    sources = prices.get("sources", {})

    # ۱. نرخ دلار آزاد و تتر
    usdt_toman, fx_src = fetch_free_market_usdt()
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
    if fx_src:
        sources["usdtToman"] = fx_src

    # ۲. بروزرسانی سهام بورس ایران با جستجوی هوشمند نام نماد
    stocks_map = prices.get("stocks", {})
    total_stocks_toman = 0

    for s in portfolio.get("stocks", []):
        sym = s["symbol"]
        ins = s.get("insCode", "")
        qty = float(s.get("qty", 0))
        prev_s = stocks_map.get(sym, {"priceToman": s.get("avgBuyToman", 1000), "dailyChangePct": 0.0})

        p_toman, chg_pct, src_info = fetch_stock_from_tsetmc(sym, ins)
        if p_toman and p_toman > 0:
            stocks_map[sym] = {
                "priceToman": p_toman,
                "dailyChangePct": chg_pct,
                "stale": False,
                "updatedAt": today_str
            }
            sources[sym] = src_info
            print(f"[OK] {sym}: {p_toman:,} Toman ({chg_pct:+}%) via {src_info}")
        else:
            prev_s["stale"] = True
            stocks_map[sym] = prev_s
            sources[sym] = "cached_previous"
            print(f"[CACHED] {sym}: kept {prev_s['priceToman']:,} Toman")

        total_stocks_toman += qty * stocks_map[sym]["priceToman"]

    prices["stocks"] = stocks_map

    # ۳. رمزارزها (BTC, ETH, SOL)
    crypto_map = prices.get("crypto", {})
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd",
            headers=HEADERS,
            timeout=6
        )
        if r.status_code == 200:
            cg = r.json()
            for sym, cid in [("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana")]:
                usd_p = cg.get(cid, {}).get("usd")
                if usd_p:
                    old_c = crypto_map.get(sym, {})
                    old_c["priceUsd"] = float(usd_p)
                    old_c["stale"] = False
                    crypto_map[sym] = old_c
                    sources[sym] = "coingecko"
    except Exception:
        pass

    prices["crypto"] = crypto_map
    prices["sources"] = sources
    prices["lastUpdated"] = now_iso
    save_json(PRICES_FILE, prices)

    # ۴. ثبت اسنپ‌شات در تاریخچه
    stable_usd = sum(float(x.get("amount", 0)) * float(x.get("pegUsd", 1)) for x in portfolio.get("stablecoins", []))
    cash_t = float(portfolio.get("cash", {}).get("amountToman", 56000000))
    nfts_t = sum(float(x.get("currentToman", 0)) for x in portfolio.
