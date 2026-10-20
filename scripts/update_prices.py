#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO_FILE = os.path.join(ROOT_DIR, "data", "portfolio.json")
PRICES_FILE = os.path.join(ROOT_DIR, "data", "prices.json")
HISTORY_FILE = os.path.join(ROOT_DIR, "data", "history.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}
MIN_FREE_USD = 150000


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Write error:", e)


def fetch_usdt():
    for url in [
        "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT",
        "https://api.tetherland.com/currencies"
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=4, verify=False)
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


def fetch_tse_stock(symbol, ins_code):
    codes = []
    if ins_code:
        codes.append(str(ins_code))
    try:
        sr = requests.get(
            f"http://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{quote(symbol)}",
            headers=HEADERS, timeout=3, verify=False
        )
        if sr.status_code == 200:
            items = sr.json().get("instrumentSearch", [])
            if items and items[0].get("insCode"):
                c = str(items[0]["insCode"])
                if c not in codes:
                    codes.insert(0, c)
    except Exception:
        pass

    for c in codes:
        try:
            r = requests.get(
                f"http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{c}",
                headers=HEADERS, timeout=3, verify=False
            )
            if r.status_code == 200:
                info = r.json().get("closingPriceInfo", {})
                raw = info.get("pDrCotVal") or info.get("pClosing")
                prev = info.get("priceYesterday")
                if raw and float(raw) > 0:
                    pt = round(float(raw) / 10.0)
                    chg = round(((float(raw) - float(prev)) / float(prev)) * 100.0, 2) if prev and float(prev) > 0 else 0.0
                    return pt, chg, "tsetmc"
        except Exception:
            pass
    return None, None, None


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json(PORTFOLIO_FILE, {})
    prices = load_json(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}, "sources": {}})
    history = load_json(HISTORY_FILE, [])
    sources = prices.get("sources", {})

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

    stocks_map = prices.get("stocks", {})
    total_stocks = 0
    tse_ok = True

    for s in portfolio.get("stocks", []):
        sym = s.get("symbol", "")
        qty = float(s.get("qty", 0))
        prev_s = stocks_map.get(sym, {"priceToman": s.get("avgBuyToman", 1000), "dailyChangePct": 0.0})

        if tse_ok:
            pt, chg, src = fetch_tse_stock(sym, s.get("insCode", ""))
            if pt and pt > 0:
                stocks_map[sym] = {"priceToman": pt, "dailyChangePct": chg, "stale": False, "updatedAt": today_str}
                sources[sym] = src
            else:
                tse_ok = False
                prev_s["stale"] = True
                stocks_map[sym] = prev_s
        else:
            prev_s["stale"] = True
            stocks_map[sym] = prev_s

        total_stocks += qty * float(stocks_map[sym].get("priceToman", 0))

    prices["stocks"] = stocks_map

    crypto_map = prices.get("crypto", {})
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd",
            headers=HEADERS, timeout=5
        )
        if r.status_code == 200:
            cg = r.json()
            for sym, cid in [("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana")]:
                p = cg.get(cid, {}).get("usd")
                if p:
                    old_c = crypto_map.get(sym, {})
                    old_c["priceUsd"] = float(p)
                    crypto_map[sym] = old_c
                    sources[sym] = "coingecko"
    except Exception:
        pass

    prices["crypto"] = crypto_map
    prices["sources"] = sources
    prices["lastUpdated"] = now_iso
    save_json(PRICES_FILE, prices)

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

    print("Success! Net worth:", net_worth)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Handled error:", e)
    sys.exit(0)
