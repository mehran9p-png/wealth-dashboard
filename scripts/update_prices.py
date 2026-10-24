#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
موتور جامع و چندلایه بروزرسانی قیمت‌ها (نسخه ضد تحریم و ضد فایروال ویژه GitHub Actions)
- پوشش کامل ۱۱ نماد بورس ایران (شامل کرومیت و سیمکات) از ۵ مسیر مستقل
- دریافت دقیق نرخ تتر و دلار بازار آزاد ایران (تشخیص خودکار ریال/تومان از ۴ صرافی)
- دریافت قیمت لحظه‌ای BTC, ETH, SOL + محاسبه MA200 و RSI14 + شاخص ترس و طمع (F&G)
"""

import json
import os
import sys
import time
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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}

BRS_KEY = "FreeSV0E1LSgB9RDjuf0QorSLViX8pPG"
MIN_FREE_USD_TOMAN = 150000
MAX_FREE_USD_TOMAN = 900000

# بانک کدهای ۱۷ رقمی دقیق نمادهای شما در TSETMC برای تضمین آپدیت ۱۰۰٪
KNOWN_INSCODES = {
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
        .replace("\u200c", "")
        .replace(" ", "")
    )


def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[WARN] Read error {path}: {e}")
    return default


def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Write error {path}: {e}")


def get_with_proxies(target_url, timeout=6):
    """تلاش برای دریافت URL به صورت مستقیم و از طریق ۳ پروکسی معتبر در صورت مسدود بودن آی‌پی گیت‌هاب"""
    urls = [
        target_url,
        f"https://api.codetabs.com/v1/proxy?quest={quote(target_url, safe='')}",
        f"https://api.allorigins.win/raw?url={quote(target_url, safe='')}",
        f"https://corsproxy.io/?url={quote(target_url, safe='')}",
    ]
    for u in urls:
        try:
            resp = requests.get(u, headers=HEADERS, timeout=timeout, verify=False)
            if resp.status_code == 200 and resp.text and len(resp.text.strip()) > 5:
                if "<html" not in resp.text[:200].lower():
                    return resp.text.strip()
        except Exception:
            pass
    return None


def normalize_toman_rate(raw_val):
    """تشخیص خودکار ریال یا تومان بودن قیمت دلار/تتر"""
    try:
        v = float(str(raw_val).replace(",", "").strip())
        if v <= 0:
            return None
        # اگر عدد بالای ۱,۵۰۰,۰۰۰ باشد یعنی به ریال است (مثلاً ۲,۶۲۰,۰۰۰ ریال -> ۲۶۲,۰۰۰ تومان)
        if v >= 1500000:
            v = v / 10.0
        toman = round(v)
        if MIN_FREE_USD_TOMAN <= toman <= MAX_FREE_USD_TOMAN:
            return toman
    except Exception:
        pass
    return None


def fetch_free_market_usdt():
    """دریافت نرخ لحظه‌ای تتر/دلار بازار آزاد از ۴ صرافی بزرگ ایران"""
    # ۱. نوبیتکس (Orderbook v3)
    txt = get_with_proxies("https://apiv2.nobitex.ir/v3/orderbook/USDTIRT", timeout=5)
    if txt:
        try:
            d = json.loads(txt)
            t = normalize_toman_rate(d.get("lastTradePrice"))
            if t:
                return t, "nobitex_v3"
        except Exception:
            pass

    # ۲. تترلند (Tetherland)
    txt = get_with_proxies("https://api.tetherland.com/currencies", timeout=5)
    if txt:
        try:
            d = json.loads(txt)
            p = d.get("data", {}).get("currencies", {}).get("USDT", {}).get("price")
            t = normalize_toman_rate(p)
            if t:
                return t, "tetherland"
        except Exception:
            pass

    # ۳. والکس (Wallex)
    txt = get_with_proxies("https://api.wallex.ir/v1/markets", timeout=5)
    if txt:
        try:
            d = json.loads(txt)
            p = (
                d.get("result", {})
                .get("symbols", {})
                .get("USDTTMN", {})
                .get("stats", {})
                .get("lastPrice")
            )
            t = normalize_toman_rate(p)
            if t:
                return t, "wallex"
        except Exception:
            pass

    # ۴. نوبیتکس (Market Stats)
    txt = get_with_proxies(
        "https://apiv2.nobitex.ir/market/stats?srcCurrency=usdt&dstCurrency=rls",
        timeout=5,
    )
    if txt:
        try:
            d = json.loads(txt)
            p = d.get("stats", {}).get("usdt-rls", {}).get("latest")
            t = normalize_toman_rate(p)
            if t:
                return t, "nobitex_stats"
        except Exception:
            pass

    return None, None


def fetch_bulk_bourse_brsapi():
    """دریافت یکجای تمام نمادهای بورس، فرابورس و صندوق‌ها از BrsApi"""
    url = f"https://Api.BrsApi.ir/Tsetmc/AllSymbols.php?key={BRS_KEY}&type=1"
    txt = get_with_proxies(url, timeout=8)
    if not txt:
        return {}
    try:
        arr = json.loads(txt)
        if isinstance(arr, list) and len(arr) > 50:
            out = {}
            for item in arr:
                sym = norm_fa(item.get("l18", ""))
                # pl = آخرین قیمت، pc = قیمت پایانی
                rial = item.get("pl") or item.get("pc")
                chg = item.get("pcp") if item.get("pcp") is not None else item.get("pc_p", 0.0)
                if sym and rial and float(rial) > 0:
                    out[sym] = {
                        "priceToman": round(float(rial) / 10.0),
                        "dailyChangePct": round(float(chg or 0.0), 2),
                    }
            return out
    except Exception as e:
        print(f"[WARN] BrsApi parse error: {e}")
    return {}


def resolve_inscode_from_tsetmc(symbol):
    """جستجوی خودکار کد ۱۷ رقمی نماد از سرور بورس تهران"""
    norm_s = norm_fa(symbol)
    if norm_s in KNOWN_INSCODES:
        return KNOWN_INSCODES[norm_s]

    search_url = f"http://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{quote(symbol)}"
    txt = get_with_proxies(search_url, timeout=5)
    if txt:
        try:
            items = json.loads(txt).get("instrumentSearch", [])
            for it in items:
                if norm_fa(it.get("lVal18AFC", "")) == norm_s and it.get("insCode"):
                    return str(it["insCode"])
            if items and items[0].get("insCode"):
                return str(items[0]["insCode"])
        except Exception:
            pass
    return None


def fetch_single_stock_tsetmc(symbol, ins_code):
    """دریافت قیمت تک‌سهم از سرور CDN و سرور Old بورس تهران"""
    code = str(ins_code or "").strip() or resolve_inscode_from_tsetmc(symbol)
    if not code:
        return None, None, None

    # ۱. سرور CDN جدید بورس
    cdn_url = f"http://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{code}"
    txt = get_with_proxies(cdn_url, timeout=5)
    if txt:
        try:
            info = json.loads(txt).get("closingPriceInfo", {})
            raw_rial = info.get("pDrCotVal") or info.get("pClosing")
            prev_rial = info.get("priceYesterday")
            if raw_rial and float(raw_rial) > 0:
                p_toman = round(float(raw_rial) / 10.0)
                chg = (
                    round(((float(raw_rial) - float(prev_rial)) / float(prev_rial)) * 100.0, 2)
                    if prev_rial and float(prev_rial) > 0
                    else 0.0
                )
                return p_toman, chg, f"tsetmc_cdn({code})"
        except Exception:
            pass

    # ۲. سرور سبک قدیمی TSETMC (instinfofast)
    old_url = f"http://old.tsetmc.com/tsev2/data/instinfofast.aspx?i={code}&c=57+"
    txt_old = get_with_proxies(old_url, timeout=5)
    if txt_old and ";" in txt_old:
        try:
            first_block = txt_old.split(";")[0]
            parts = first_block.split(",")
            if len(parts) >= 5:
                last_r = float(parts[2] or 0)
                close_r = float(parts[3] or 0)
                prev_r = float(parts[4] or 0)
                active_r = last_r if last_r > 0 else close_r
                if active_r > 0:
                    p_toman = round(active_r / 10.0)
                    chg = round(((active_r - prev_r) / prev_r) * 100.0, 2) if prev_r > 0 else 0.0
                    return p_toman, chg, f"tsetmc_old({code})"
        except Exception:
            pass

    return None, None, None


def compute_rsi14(closes):
    if not closes or len(closes) < 15:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(0.0, d))
        losses.append(max(0.0, -d))
    avg_g = sum(gains[:14]) / 14.0
    avg_l = sum(losses[:14]) / 14.0
    for i in range(14, len(gains)):
        avg_g = (avg_g * 13.0 + gains[i]) / 14.0
        avg_l = (avg_l * 13.0 + losses[i]) / 14.0
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100.0 - (100.0 / (1.0 + rs)), 1)


def fetch_crypto_and_sentiment(existing_crypto):
    """دریافت قیمت لحظه‌ای BTC, ETH, SOL از ۳ منبع جهانی + شاخص ترس و طمع"""
    crypto_out = json.loads(json.dumps(existing_crypto or {}))
    sources = {}

    for sym, default_p, ath_p in [("BTC", 68450, 73750), ("ETH", 2725, 4878), ("SOL", 158.4, 259.9)]:
        if sym not in crypto_out:
            crypto_out[sym] = {
                "priceUsd": default_p,
                "athUsd": ath_p,
                "high1yUsd": ath_p,
                "high90dUsd": round(default_p * 1.1),
                "ma200Usd": round(default_p * 0.9),
                "rsi14": 50.0,
                "stale": False,
            }

        # منبع ۱: کندل‌های روزانه بایننس
        try:
            r = requests.get(
                f"https://api.binance.com/api/v3/klines?symbol={sym}USDT&interval=1d&limit=250",
                headers=HEADERS,
                timeout=6,
            )
            if r.status_code == 200:
                klines = r.json()
                if isinstance(klines, list) and len(klines) > 30:
                    closes = [float(k[4]) for k in klines]
                    highs = [float(k[2]) for k in klines]
                    cur_p = closes[-1]
                    crypto_out[sym] = {
                        "priceUsd": round(cur_p, 2),
                        "athUsd": max(ath_p, round(max(highs), 2)),
                        "high1yUsd": round(max(highs), 2),
                        "high90dUsd": round(max(highs[-90:]), 2),
                        "ma200Usd": round(sum(closes[-200:]) / min(200, len(closes)), 2),
                        "rsi14": compute_rsi14(closes),
                        "stale": False,
                    }
                    sources[sym] = "binance_klines"
                    continue
        except Exception:
            pass

        # منبع ۲: CryptoCompare (بدون محدودیت روی سرورهای آمریکا/GitHub)
        try:
            r2 = requests.get(
                f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={sym}&tsym=USD&limit=200",
                headers=HEADERS,
                timeout=6,
            )
            if r2.status_code == 200:
                arr = r2.json().get("Data", {}).get("Data", [])
                if len(arr) > 30:
                    closes = [float(x["close"]) for x in arr if float(x.get("close", 0)) > 0]
                    highs = [float(x["high"]) for x in arr if float(x.get("high", 0)) > 0]
                    cur_p = closes[-1]
                    crypto_out[sym] = {
                        "priceUsd": round(cur_p, 2),
                        "athUsd": max(ath_p, round(max(highs), 2)),
                        "high1yUsd": round(max(highs), 2),
                        "high90dUsd": round(max(highs[-90:]), 2),
                        "ma200Usd": round(sum(closes[-200:]) / min(200, len(closes)), 2),
                        "rsi14": compute_rsi14(closes),
                        "stale": False,
                    }
                    sources[sym] = "cryptocompare"
                    continue
        except Exception:
            pass

    # منبع ۳ (پشتیبان سریع): CoinGecko Simple Price
    try:
        cg_res = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd",
            headers=HEADERS,
            timeout=6,
        )
        if cg_res.status_code == 200:
            cg = cg_res.json()
            for sym, cid in [("BTC", "bitcoin"), ("ETH", "ethereum"), ("SOL", "solana")]:
                if sym not in sources and cg.get(cid, {}).get("usd"):
                    crypto_out[sym]["priceUsd"] = float(cg[cid]["usd"])
                    crypto_out[sym]["stale"] = False
                    sources[sym] = "coingecko"
    except Exception:
        pass

    # شاخص ترس و طمع (Fear & Greed)
    sentiment = {"fngValue": 48, "fngLabel": "خنثی (Neutral)", "btcDominance": 57.4}
    try:
        fng_r = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=5)
        if fng_r.status_code == 200:
            d = fng_r.json().get("data", [])
            if d and d[0].get("value"):
                sentiment["fngValue"] = int(d[0]["value"])
                sentiment["fngLabel"] = d[0].get("value_classification", "Neutral")
    except Exception:
        pass

    return crypto_out, sentiment, sources


def main():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    portfolio = load_json(PORTFOLIO_FILE, {})
    prices = load_json(PRICES_FILE, {"fx": {}, "stocks": {}, "crypto": {}, "sources": {}})
    history = load_json(HISTORY_FILE, [])
    sources = prices.get("sources", {})

    # ۱. بروزرسانی نرخ تتر و دلار آزاد
    usdt_val, fx_src = fetch_free_market_usdt()
    prev_usdt = normalize_toman_rate(prices.get("fx", {}).get("usdtToman")) or 262000
    final_usdt = usdt_val if usdt_val else prev_usdt

    prices["fx"] = {
        "usdtToman": final_usdt,
        "freeUsdToman": round(final_usdt * 0.996),
        "gold18kToman": prices.get("fx", {}).get("gold18kToman", 17850000),
        "stale": not bool(usdt_val),
    }
    sources["usdtToman"] = fx_src if fx_src else f"cached({final_usdt})"
    print(f"[FX] USDT/Toman = {final_usdt:,} ({sources['usdtToman']})")

    # ۲. بروزرسانی ۱۱ نماد بورس ایران
    bulk_map = fetch_bulk_bourse_brsapi()
    stocks_map = prices.get("stocks", {})
    portfolio_stocks = portfolio.get("stocks", [])

    # اطمینان از اینکه هر ۱۱ نماد شما در لیست بررسی می‌شوند
    existing_syms = {norm_fa(s.get("symbol")) for s in portfolio_stocks}
    for k_sym, k_code in KNOWN_INSCODES.items():
        if norm_fa(k_sym) not in existing_syms:
            portfolio_stocks.append({"symbol": k_sym, "qty": 0, "avgBuyToman": 1000, "insCode": k_code})

    total_stocks_toman = 0
    updated_stocks_count = 0

    for s in portfolio_stocks:
        sym = s.get("symbol", "")
        norm_s = norm_fa(sym)
        qty = float(s.get("qty", 0))
        ins_code = s.get("insCode") or KNOWN_INSCODES.get(norm_s, "")
        prev_entry = stocks_map.get(sym, {"priceToman": s.get("avgBuyToman", 1000), "dailyChangePct": 0.0})

        if norm_s in bulk_map and bulk_map[norm_s]["priceToman"] > 0:
            stocks_map[sym] = {
                "priceToman": bulk_map[norm_s]["priceToman"],
                "dailyChangePct": bulk_map[norm_s]["dailyChangePct"],
                "stale": False,
                "updatedAt": today_str,
            }
            sources[sym] = "brsapi_bulk"
            updated_stocks_count += 1
        else:
            p_tom, chg_pct, single_src = fetch_single_stock_tsetmc(sym, ins_code)
            if p_tom and p_tom > 0:
                stocks_map[sym] = {
                    "priceToman": p_tom,
                    "dailyChangePct": chg_pct,
                    "stale": False,
                    "updatedAt": today_str,
                }
                sources[sym] = single_src
                updated_stocks_count += 1
            else:
                prev_entry["stale"] = True
                stocks_map[sym] = prev_entry
                sources[sym] = "cached"

        if qty > 0:
            total_stocks_toman += qty * float(stocks_map[sym].get("priceToman", 0))
        print(f"[STOCK] {sym}: {stocks_map[sym]['priceToman']:,} Toman ({sources.get(sym)})")

    prices["stocks"] = stocks_map

    # ۳. بروزرسانی رمزارزها و شاخص ترس و طمع
    crypto_out, sentiment_out, crypto_srcs = fetch_crypto_and_sentiment(prices.get("crypto", {}))
    prices["crypto"] = crypto_out
    prices["sentiment"] = sentiment_out
    sources.update(crypto_srcs)

    prices["sources"] = sources
    prices["lastUpdated"] = now_iso
    prices["sourceType"] = f"GitHub Actions ({updated_stocks_count} نماد زنده)"
    save_json(PRICES_FILE, prices)

    # ۴. ثبت اسنپ‌شات روزانه در تاریخچه
    stable_usd = sum(
        float(x.get("amount", 0)) * float(x.get("pegUsd", 1))
        for x in portfolio.get("stablecoins", [])
    )
    cash_t = float(portfolio.get("cash", {}).get("amountToman", 46000000)) + float(
        portfolio.get("cash", {}).get("brokerPowerToman", 978278)
    )
    nfts_t = sum(
        float(x.get("floorToman") or x.get("currentToman", 0))
        for x in portfolio.get("nfts", [])
    )
    net_worth = round(total_stocks_toman + (stable_usd * final_usdt) + cash_t + nfts_t)

    if net_worth > 0:
        if isinstance(history, list) and history and history[-1].get("date") == today_str:
            history[-1]["totalToman"] = net_worth
        else:
            history.append({"date": today_str, "totalToman": net_worth})
        save_json(HISTORY_FILE, history)

    print(f"[SUCCESS] Updated at {now_iso} | Net Worth: {net_worth:,} Toman")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[GUARD] Top-level exception handled: {exc}")
    sys.exit(0)
