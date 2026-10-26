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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

BRS_KEY = "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG"

STOCK_INSCODES = {
    "وفیروزه": "55254206302462116",
    "فپنتا": "17914401175772326",
    "شپدیس": "44891482026867833",
    "کرومیت": "46741025610365789",
    "فهامون": "38232437866669967",
    "فکور": "66442254613568889",
    "فپردیس": "41933952242799993",
    "وسرمایه": "21963356012832211",
    "زشک": "61449234123698745",
    "سیمکات": "32469128621155732",
    "فساپ": "51617145879012365",
}


def norm_fa(text):
    if not text:
        return ""
    return (
        str(text)
        .strip()
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("ئ", "ی")
        .replace("ة", "ه")
        .replace("\u200c", "")
        .replace(" ", "")
    )


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


def http_get_text(target_url, timeout=6):
    routes = [
        target_url,
        f"https://api.codetabs.com/v1/proxy?quest={quote(target_url, safe='')}",
        f"https://api.allorigins.win/raw?url={quote(target_url, safe='')}",
    ]
    for u in routes:
        try:
            r = requests.get(u, headers=HEADERS, timeout=timeout, verify=False)
            if r.status_code == 200 and r.text and len(r.text.strip()) > 5:
                low = r.text[:200].lower()
                if "<html" not in low and "cloudflare" not in low:
                    return r.text.strip()
        except Exception:
            pass
    return None


def clean_toman(val, is_rial=False):
    try:
        n = float(str(val).replace(",", "").strip())
        if n <= 0:
            return None
        if is_rial or n >= 1000000:
            n = n / 10.0
        n = round(n)
        if 50000 <= n <= 950000:
            return n
    except Exception:
        pass
    return None


def fetch_usdt_toman():
    for url, rial, src in [
        ("https://api.tetherland.com/currencies", False, "تترلند"),
        ("https://apiv2.nobitex.ir/v3/orderbook/USDTIRT", True, "نوبیتکس"),
        ("https://api.wallex.ir/v1/markets", False, "والکس"),
    ]:
        txt = http_get_text(url, timeout=5)
        if txt:
            try:
                d = json.loads(txt)
                raw = (
                    d.get("data", {}).get("currencies", {}).get("USDT", {}).get("price")
                    if src == "تترلند"
                    else (
                        d.get("lastTradePrice")
                        if src == "نوبیتکس"
                        else d.get("result", {}).get("symbols", {}).get("USDTTMN", {}).get("stats", {}).get("lastPrice")
                    )
                )
                t = clean_toman(raw, is_rial=rial)
                if t:
                    return t, src
            except Exception:
                pass
    return None, None


def fetch_all_bourse(now_iso):
    results = {}
    bulk_map = {}

    for t_code in [1, 2]:
        txt = http_get_text(f"https://Api.BrsApi.ir/Tsetmc/AllSymbols.php?key={BRS_KEY}&type={t_code}", timeout=7)
        if txt:
            try:
                arr = json.loads(txt)
                if isinstance(arr, list):
                    for it in arr:
                        sym = norm_fa(it.get("l18", ""))
                        rial = it.get("pl") or it.get("pc")
                        chg = it.get("pcp") if it.get("pcp") is not None else it.get("pc_p", 0.0)
                        if sym and rial and float(rial) > 0:
                            bulk_map[sym] = {
                                "priceToman": round(float(rial) / 10.0),
                                "dailyChangePct": round(float(chg or 0.0), 2),
                                "source": "BrsApi",
                                "updatedAt": now_iso,
                            }
            except Exception:
                pass

    for sym in STOCK_INSCODES:
        ns = norm_fa(sym)
        if ns in bulk_map:
            results[sym] = bulk_map[ns]

    for sym, default_code in STOCK_INSCODES.items():
        if sym in results and results[sym]["priceToman"] > 0:
            continue
        ptxt = http_get_text(f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{default_code}", timeout=4)
        if ptxt:
            try:
                info = json.loads(ptxt).get("closingPriceInfo", {})
                raw_r = info.get("pDrCotVal") or info.get("pClosing")
                prev_r = info.get("priceYesterday")
                if raw_r and float(raw_r) > 0:
                    p_tmn = round(float(raw_r) / 10.0)
                    chg = round(((float(raw_r) - float(prev_r)) / float(prev_r)) * 100.0, 2) if prev_r and float(prev_r) > 0 else 0.0
                    results[sym] = {"priceToman": p_tmn, "dailyChangePct": chg, "source": "TSETMC", "updatedAt": now_iso}
            except Exception:
                pass

    return results


def fetch_crypto_reliable(existing_crypto, now_iso):
    out = json.loads(json.dumps(existing_crypto or {}))
    for sym, def_p, def_h in [("BTC", 68450.0, 70200.0), ("ETH", 2725.0, 3420.0), ("SOL", 158.4, 188.5)]:
        if sym not in out:
            out[sym] = {"priceUsd": def_p, "high90dUsd": def_h, "ma200Usd": round(def_p * 0.9), "rsi14": 50.0}

    try:
        r = requests.get("https://min-api.cryptocompare.com/data/pricemultifull?fsyms=BTC,ETH,SOL&tsyms=USD", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            raw = r.json().get("RAW", {})
            for sym in ["BTC", "ETH", "SOL"]:
                p = float(raw.get(sym, {}).get("USD", {}).get("PRICE", 0))
                if p > 0:
                    out[sym]["priceUsd"] = round(p, 2)
                    out[sym]["source"] = "CryptoCompare"
                    out[sym]["updatedAt"] = now_iso
    except Exception:
        pass

    for sym in ["BTC", "ETH", "SOL"]:
        try:
            r = requests.get(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot", headers=HEADERS, timeout=4)
            if r.status_code == 200:
                p = float(r.json().get("data", {}).get("amount", 0))
                if p > 0:
                    out[sym]["priceUsd"] = round(p, 2)
                    out[sym]["source"] = "Coinbase"
                    out[sym]["updatedAt"] = now_iso
        except Exception:
            pass

    return out


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json(PORTFOLIO_FILE, {})
    prices = load_json(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}})
    history = load_json(HISTORY_FILE, [])

    live_usdt, fx_src = fetch_usdt_toman()
    prev_usdt = clean_toman(prices.get("fx", {}).get("usdtToman")) or 262000
    final_usdt = live_usdt if live_usdt else prev_usdt
    prices["fx"] = {
        "usdtToman": final_usdt,
        "freeUsdToman": round(final_usdt * 0.996),
        "gold18kToman": prices.get("fx", {}).get("gold18kToman", 17850000),
        "source": fx_src or "گیت‌هاب",
        "updatedAt": now_iso,
        "stale": not bool(live_usdt),
    }

    live_stocks = fetch_all_bourse(now_iso)
    stocks_dict = prices.get("stocks", {})
    for sym, p_obj in live_stocks.items():
        if p_obj.get("priceToman", 0) > 0:
            stocks_dict[sym] = p_obj
    prices["stocks"] = stocks_dict

    prices["crypto"] = fetch_crypto_reliable(prices.get("crypto", {}), now_iso)
    prices["lastUpdated"] = now_iso
    save_json(PRICES_FILE, prices)

    total_stocks = sum(
        float(s.get("qty", 0)) * float(stocks_dict.get(s.get("symbol"), {}).get("priceToman", s.get("avgBuyToman", 0)))
        for s in portfolio.get("stocks", [])
    )
    stable_usd = sum(float(x.get("amount", 0)) * float(x.get("pegUsd", 1)) for x in portfolio.get("stablecoins", []))
    cash_t = float(portfolio.get("cash", {}).get("amountToman", 46000000)) + float(portfolio.get("cash", {}).get("brokerPowerToman", 978278))
    nfts_t = sum(float(x.get("floorToman") or x.get("currentToman", 0)) for x in portfolio.get("nfts", []))
    loan_inv = float(portfolio.get("loan", {}).get("currentInvestedValueToman", 34000000))
    net_worth = round(total_stocks + (stable_usd * final_usdt) + cash_t + nfts_t + loan_inv)

    if net_worth > 0:
        if isinstance(history, list) and history and history[-1].get("date") == today_str:
            history[-1]["totalToman"] = net_worth
        else:
            history.append({"date": today_str, "totalToman": net_worth})
        save_json(HISTORY_FILE, history)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
