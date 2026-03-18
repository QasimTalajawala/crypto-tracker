import streamlit as st
import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime

st.set_page_config(page_title="Crypto Tracker", page_icon="📈", layout="wide")

# ── Default Holdings ────────────────────────────────────────────────────────
DEFAULT_HOLDINGS = {
    # qty from screenshot; buy_price = screenshot value ÷ qty (price at time of screenshot)
    "bitcoin":     {"symbol": "BTC",    "name": "Bitcoin",   "qty": 0.00477973,  "buy_price": round(356.08   / 0.00477973,  2)},   # ~$74,497
    "solana":      {"symbol": "SOL",    "name": "Solana",    "qty": 1.20181095,  "buy_price": round(113.73   / 1.20181095,  2)},   # ~$94.63
    "ethereum":    {"symbol": "ETH",    "name": "Ethereum",  "qty": 0.04647102,  "buy_price": round(108.00   / 0.04647102,  2)},   # ~$2,324
    "bittensor":   {"symbol": "TAO",    "name": "Bittensor", "qty": 0.35218514,  "buy_price": round(99.42    / 0.35218514,  2)},   # ~$282
    "chainlink":   {"symbol": "LINK",   "name": "ChainLink", "qty": 10.13085837, "buy_price": round(99.28    / 10.13085837, 2)},   # ~$9.80
    "binancecoin": {"symbol": "BNB",    "name": "BNB",       "qty": 0.14611512,  "buy_price": round(98.10    / 0.14611512,  2)},   # ~$671
    "render-token":{"symbol": "RENDER", "name": "Render",    "qty": 43.50722321, "buy_price": round(78.70    / 43.50722321, 2)},   # ~$1.81
}

COINGECKO_IDS = list(DEFAULT_HOLDINGS.keys())

# ── Session state init ───────────────────────────────────────────────────────
if "holdings" not in st.session_state:
    st.session_state.holdings = {
        cid: {**info}
        for cid, info in DEFAULT_HOLDINGS.items()
    }
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# ── API helpers ──────────────────────────────────────────────────────────────
def _get_with_retry(url: str, timeout: int = 10, retries: int = 3) -> requests.Response:
    """GET with exponential backoff on 429 rate-limit responses."""
    for attempt in range(retries):
        r = requests.get(url, timeout=timeout)
        if r.status_code == 429:
            wait = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()  # raise after all retries exhausted
    return r

@st.cache_data(ttl=600)   # 10-min cache — reduces calls by 2×
def fetch_market_data(coin_ids: tuple):
    ids_str = ",".join(coin_ids)
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids_str}"
        "&order=market_cap_desc&per_page=50&page=1"
        "&price_change_percentage=7d,30d&sparkline=false"
    )
    try:
        r = _get_with_retry(url)
        return {c["id"]: c for c in r.json()}
    except Exception:
        return None  # None = use stale cache

@st.cache_data(ttl=7200)  # 2-hour cache for RSI (daily data, changes slowly)
def fetch_rsi(coin_id: str, days: int = 30):
    """Fetch 30-day daily closes and compute 14-day RSI."""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    try:
        r = _get_with_retry(url)
        prices = [p[1] for p in r.json().get("prices", [])]
        if len(prices) < 15:
            return None
        closes = pd.Series(prices)
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return round(float(rsi.iloc[-1]), 1)
    except Exception:
        return None

@st.cache_data(ttl=3600)
def fetch_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:
        return None, "Unknown"

@st.cache_data(ttl=600)
def search_coin(query: str):
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/search?query={query}", timeout=10
        )
        return r.json().get("coins", [])[:5]
    except Exception:
        return []

# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_price(p):
    """Smart price: no trailing zeros, right number of decimals for the magnitude."""
    if p is None or p == 0:
        return "—"
    if p >= 1_000:
        return f"${p:,.0f}"
    if p >= 1:
        return f"${p:,.2f}"
    if p >= 0.01:
        return f"${p:.4f}"
    return f"${p:.6f}"

def fmt_qty(q):
    """Show quantity with up to 6 significant figures, no trailing zeros."""
    if q is None:
        return "—"
    return f"{q:.6g}"

# ── Signal logic ─────────────────────────────────────────────────────────────
def score_to_label(score):
    if score >= 4:   return "Strong Buy",       "🟢"
    if score >= 2:   return "Buy",               "🟩"
    if score >= 0:   return "Hold",              "🟡"
    if score >= -3:  return "Caution",           "🟠"
    return               "Consider Selling",     "🔴"

def compute_signal(rsi, fg_value, price_vs_ath_pct, price_change_30d, pnl_pct,
                   market_cap=None, vol_mcap_pct=None):
    """
    Returns (label_string, reasons_list, raw_score).
    Price signals  (max +7 / min -6)
    Fundamental signals  (max +2 / min -2)
    """
    score = 0
    price_reasons = []
    fund_reasons  = []

    # ── Price signals ──────────────────────────────────────────────────────
    if rsi is not None:
        if rsi < 30:
            score += 2; price_reasons.append(f"RSI {rsi} — oversold (buy zone)")
        elif rsi < 40:
            score += 1; price_reasons.append(f"RSI {rsi} — leaning oversold")
        elif rsi > 70:
            score -= 2; price_reasons.append(f"RSI {rsi} — overbought (sell zone)")
        elif rsi > 60:
            score -= 1; price_reasons.append(f"RSI {rsi} — leaning overbought")

    if fg_value is not None:
        if fg_value < 25:
            score += 2; price_reasons.append(f"Fear & Greed {fg_value} — extreme fear (buy zone)")
        elif fg_value < 40:
            score += 1; price_reasons.append(f"Fear & Greed {fg_value} — fear")
        elif fg_value > 75:
            score -= 2; price_reasons.append(f"Fear & Greed {fg_value} — extreme greed (sell zone)")
        elif fg_value > 60:
            score -= 1; price_reasons.append(f"Fear & Greed {fg_value} — greed")

    if price_vs_ath_pct is not None:
        if price_vs_ath_pct <= -70:
            score += 2; price_reasons.append(f"{abs(price_vs_ath_pct):.0f}% below ATH — historically cheap")
        elif price_vs_ath_pct <= -50:
            score += 1; price_reasons.append(f"{abs(price_vs_ath_pct):.0f}% below ATH — discounted")
        elif price_vs_ath_pct >= -10:
            score -= 1; price_reasons.append(f"Near ATH — limited upside at current price")

    if price_change_30d is not None:
        if price_change_30d < -25:
            score += 1; price_reasons.append(f"Down {abs(price_change_30d):.0f}% in 30d — potential dip entry")
        elif price_change_30d > 30:
            score -= 1; price_reasons.append(f"Up {price_change_30d:.0f}% in 30d — short-term momentum high")

    if pnl_pct is not None and pnl_pct > 50:
        score -= 1; price_reasons.append(f"Up {pnl_pct:.0f}% from your buy price — consider taking partial profit")

    # ── Fundamental signals ────────────────────────────────────────────────
    if market_cap is not None:
        if market_cap >= 10_000_000_000:
            score += 1; fund_reasons.append("Large cap (>$10B) — established, lower risk")
        elif market_cap >= 1_000_000_000:
            pass  # mid cap: neutral
        elif market_cap < 500_000_000:
            score -= 1; fund_reasons.append("Small/micro cap (<$500M) — higher risk, higher volatility")

    if vol_mcap_pct is not None:
        if vol_mcap_pct >= 5:
            score += 1; fund_reasons.append(f"Vol/MCap {vol_mcap_pct:.1f}% — strong liquidity")
        elif vol_mcap_pct < 1:
            score -= 1; fund_reasons.append(f"Vol/MCap {vol_mcap_pct:.1f}% — low liquidity, harder to exit")

    label, color = score_to_label(score)
    reasons = price_reasons + fund_reasons
    return f"{color} {label}", reasons, score

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Crypto Tracker")
    st.caption("Prices refresh every 5 min")

    st.subheader("Your Buy Prices")
    for cid, info in st.session_state.holdings.items():
        bp = st.number_input(
            f"{info['symbol']} buy price (USD)",
            min_value=0.0,
            value=float(info["buy_price"]),
            format="%.2f",
            key=f"bp_{cid}",
        )
        st.session_state.holdings[cid]["buy_price"] = bp

    st.divider()
    st.subheader("Add to Watchlist")
    wl_query = st.text_input("Search coin", placeholder="e.g. Pepe")
    if wl_query:
        results = search_coin(wl_query)
        for coin in results:
            if st.button(f"+ {coin['name']} ({coin['symbol'].upper()})", key=f"add_{coin['id']}"):
                if coin["id"] not in st.session_state.watchlist:
                    st.session_state.watchlist.append(coin["id"])
                    st.rerun()

    if st.session_state.watchlist:
        st.caption("Watching:")
        for wid in st.session_state.watchlist:
            col1, col2 = st.columns([3, 1])
            col1.write(wid)
            if col2.button("✕", key=f"rm_{wid}"):
                st.session_state.watchlist.remove(wid)
                st.rerun()

# ── Fetch data ────────────────────────────────────────────────────────────────
all_ids = tuple(COINGECKO_IDS + st.session_state.watchlist)
market_result = fetch_market_data(all_ids)
if market_result is not None:
    st.session_state["last_market"] = market_result  # save last good data
market = st.session_state.get("last_market", {})
if market_result is None:
    st.warning("⚠️ CoinGecko rate limit — showing last known prices. Auto-refreshes in ~10 min.", icon="⏳")
fg_value, fg_label = fetch_fear_greed()

# ── Pre-compute all coin metrics (used by Analysis + Signals tabs) ────────────
coin_metrics = {}
for cid, info in st.session_state.holdings.items():
    md = market.get(cid, {})
    cp          = md.get("current_price", 0)
    ath         = md.get("ath", 0)
    market_cap  = md.get("market_cap", 0)
    volume_24h  = md.get("total_volume", 0)
    vol_mcap    = (volume_24h / market_cap * 100) if market_cap else None
    ath_pct     = ((cp - ath) / ath * 100) if ath else None
    ch30        = md.get("price_change_percentage_30d_in_currency")
    bp          = info["buy_price"]
    pnl_pct     = ((cp - bp) / bp * 100) if bp > 0 and cp else None
    rsi         = fetch_rsi(cid)
    signal, reasons, score = compute_signal(
        rsi, fg_value, ath_pct, ch30, pnl_pct, market_cap, vol_mcap
    )
    coin_metrics[cid] = dict(
        info=info, md=md, cp=cp, ath=ath, market_cap=market_cap,
        vol_mcap=vol_mcap, ath_pct=ath_pct, ch30=ch30,
        pnl_pct=pnl_pct, rsi=rsi, signal=signal, reasons=reasons, score=score
    )

tab0, tab1, tab2, tab3, tab4 = st.tabs(
    ["🎯 Analysis", "💼 Portfolio", "🚦 Signals", "📊 Fundamentals", "👀 Watchlist"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 0: OVERALL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab0:
    st.header("🎯 Overall Analysis")
    st.caption("Combined rating using price signals (RSI, momentum, ATH distance) + fundamentals (market cap, liquidity).")

    # ── Overall portfolio score ────────────────────────────────────────────
    scores = [m["score"] for m in coin_metrics.values()]
    avg_score = sum(scores) / len(scores) if scores else 0
    port_label, port_color = score_to_label(round(avg_score))

    buys      = sum(1 for s in scores if s >= 2)
    holds     = sum(1 for s in scores if -1 <= s < 2)
    cautions  = sum(1 for s in scores if s < -1)

    # Overall verdict banner
    fg_sentiment = ""
    if fg_value is not None:
        if fg_value < 25:   fg_sentiment = "Market is in **Extreme Fear** — historically a good time to accumulate."
        elif fg_value < 40: fg_sentiment = "Market is in **Fear** — cautious accumulation may be appropriate."
        elif fg_value < 60: fg_sentiment = "Market is **Neutral** — no strong macro signal either way."
        elif fg_value < 75: fg_sentiment = "Market is in **Greed** — be selective, avoid chasing pumps."
        else:               fg_sentiment = "Market is in **Extreme Greed** — consider reducing exposure."

    verdict_bg = {"Strong Buy":"#1a3a1a","Buy":"#1a2e1a","Hold":"#2e2a1a",
                  "Caution":"#2e1f0a","Consider Selling":"#2e0a0a"}
    bg = verdict_bg.get(port_label, "#1a1a1a")

    st.markdown(
        f"""<div style="background:{bg};border-radius:12px;padding:20px 24px;margin-bottom:16px">
        <div style="font-size:2rem;font-weight:700">{port_color} Portfolio Verdict: {port_label}</div>
        <div style="color:#aaa;margin-top:6px">Average signal score: <b>{avg_score:+.1f}</b> across {len(scores)} coins
        &nbsp;·&nbsp; {fg_sentiment}</div>
        </div>""",
        unsafe_allow_html=True
    )

    # Breakdown KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Coins to Buy",    buys,     help="Score ≥ 2")
    k2.metric("Coins to Hold",   holds,    help="Score −1 to +1")
    k3.metric("Coins to Caution",cautions, help="Score < −1")
    k4.metric("Fear & Greed",    f"{fg_value} — {fg_label}" if fg_value else "—")

    st.divider()

    # ── Per-coin summary table ─────────────────────────────────────────────
    st.subheader("Per-Coin Rating")
    rows_a = []
    for cid, m in coin_metrics.items():
        rows_a.append({
            "Coin":        f"{m['info']['name']} ({m['info']['symbol']})",
            "Price":       fmt_price(m["cp"]),
            "RSI":         f"{m['rsi']}" if m["rsi"] else "—",
            "From ATH":    f"{m['ath_pct']:.0f}%" if m["ath_pct"] else "—",
            "30d %":       f"{m['ch30']:+.1f}%" if m["ch30"] else "—",
            "P&L %":       f"{m['pnl_pct']:+.1f}%" if m["pnl_pct"] is not None else "—",
            "Score":       f"{m['score']:+d}",
            "Rating":      m["signal"],
        })
    st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)

    # ── Key insights ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Key Insights")

    # Best opportunity (highest score)
    best = max(coin_metrics.items(), key=lambda x: x[1]["score"])
    worst = min(coin_metrics.items(), key=lambda x: x[1]["score"])
    most_discounted = min(
        ((cid, m) for cid, m in coin_metrics.items() if m["ath_pct"] is not None),
        key=lambda x: x[1]["ath_pct"], default=None
    )

    insights = []
    insights.append(f"**Best opportunity:** {best[1]['info']['name']} ({best[1]['info']['symbol']}) — score {best[1]['score']:+d}, rated {best[1]['signal']}")
    if worst[1]["score"] < 0:
        insights.append(f"**Most cautious:** {worst[1]['info']['name']} ({worst[1]['info']['symbol']}) — score {worst[1]['score']:+d}, rated {worst[1]['signal']}")
    if most_discounted:
        cid, m = most_discounted
        insights.append(f"**Most discounted from ATH:** {m['info']['name']} ({m['info']['symbol']}) at {m['ath_pct']:.0f}% below its all-time high of {fmt_price(m['ath'])}")

    # Portfolio-level narrative
    if avg_score >= 3:
        insights.append("**Overall:** Strong buying conditions across the portfolio. Consider adding to positions if you have available capital.")
    elif avg_score >= 1:
        insights.append("**Overall:** Mild buying conditions. Gradual accumulation (DCA) may be appropriate rather than a lump-sum entry.")
    elif avg_score >= -1:
        insights.append("**Overall:** Mixed signals. Hold current positions and wait for a clearer direction before adding.")
    elif avg_score >= -3:
        insights.append("**Overall:** Caution warranted. Review positions — consider whether any have exceeded your risk tolerance.")
    else:
        insights.append("**Overall:** Bearish signals across most coins. Review your risk exposure and consider whether to reduce positions.")

    for ins in insights:
        st.markdown(f"- {ins}")

    st.caption("⚠️ This is not financial advice. Always do your own research before making investment decisions.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("💼 Portfolio")

    if fg_value:
        fg_color = (
            "🟢" if fg_value < 25 else
            "🟡" if fg_value < 50 else
            "🟠" if fg_value < 75 else "🔴"
        )
        st.info(f"**Market Sentiment:** {fg_color} Fear & Greed Index = **{fg_value}** ({fg_label})")

    rows = []
    total_value = 0.0
    total_cost = 0.0

    for cid, info in st.session_state.holdings.items():
        md = market.get(cid, {})
        current_price = md.get("current_price", 0)
        qty = info["qty"]
        buy_price = info["buy_price"]
        value = qty * current_price
        cost = qty * buy_price if buy_price > 0 else None
        pnl = value - cost if cost else None
        pnl_pct = (pnl / cost * 100) if cost else None

        total_value += value
        if cost:
            total_cost += cost

        rows.append({
            "Coin": f"{info['name']} ({info['symbol']})",
            "Qty": fmt_qty(qty),
            "Buy Price": fmt_price(buy_price) if buy_price > 0 else "—",
            "Current Price": fmt_price(current_price),
            "Value": f"${value:,.2f}",
            "P&L $": f"${pnl:+,.2f}" if pnl is not None else "—",
            "P&L %": f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
        })

    df = pd.DataFrame(rows)

    # KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Portfolio Value", f"${total_value:,.2f}")
    if total_cost > 0:
        total_pnl = total_value - total_cost
        total_pnl_pct = total_pnl / total_cost * 100
        k2.metric("Total Cost Basis", f"${total_cost:,.2f}")
        k3.metric("Total P&L", f"${total_pnl:+,.2f}", delta=f"{total_pnl_pct:+.1f}%")

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Allocation pie
    st.subheader("Allocation")
    alloc = {
        st.session_state.holdings[cid]["symbol"]: market.get(cid, {}).get("current_price", 0) * info["qty"]
        for cid, info in st.session_state.holdings.items()
    }
    alloc_df = pd.DataFrame({"Coin": list(alloc.keys()), "Value": list(alloc.values())})
    alloc_df = alloc_df[alloc_df["Value"] > 0]
    st.bar_chart(alloc_df.set_index("Coin"))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: SIGNALS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🚦 Buy / Sell Signals")
    st.caption("Based on RSI, Fear & Greed Index, distance from ATH, and 30-day momentum.")

    if fg_value:
        st.info(f"**Fear & Greed Index: {fg_value} — {fg_label}**  |  <25 = buy zone · >75 = sell zone")

    for cid, m in coin_metrics.items():
        info = m["info"]
        with st.expander(f"**{info['name']} ({info['symbol']})** — {m['signal']}  (score {m['score']:+d})", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", fmt_price(m["cp"]))
            c2.metric("RSI (14d)", f"{m['rsi']}" if m["rsi"] else "—",
                      help="<30 oversold (buy) · >70 overbought (sell)")
            c3.metric("From ATH", f"{m['ath_pct']:.1f}%" if m["ath_pct"] else "—")
            c4.metric("30d Change", f"{m['ch30']:+.1f}%" if m["ch30"] else "—")

            if m["reasons"]:
                st.write("**Factors:**")
                for r in m["reasons"]:
                    st.write(f"  • {r}")
            else:
                st.write("No strong signals at this time.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: FUNDAMENTALS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("📊 Fundamentals")
    st.caption("Key on-chain and market metrics to assess each coin's health.")

    with st.expander("📖 How to read these metrics", expanded=False):
        st.markdown("""
| Metric | Good sign | Red flag |
|---|---|---|
| **Market Cap** | >$10B (large cap = stable) | <$100M (micro cap = risky) |
| **24h Volume / Market Cap** | >3% (active, liquid) | <0.5% (illiquid) |
| **% from ATH** | -50% to -80% (historically cheap) | Near 0% (near peak) |
| **7d Change** | Moderate positive | Extreme >50% (FOMO) |
| **30d Change** | Positive trend | Extreme negative (collapse) |
| **RSI** | 30–50 (healthy) | <20 or >80 (extremes) |
""")

    rows_f = []
    for cid, info in st.session_state.holdings.items():
        md = market.get(cid, {})
        current_price = md.get("current_price", 0)
        ath = md.get("ath", 0)
        market_cap = md.get("market_cap", 0)
        volume_24h = md.get("total_volume", 0)
        vol_mcap = (volume_24h / market_cap * 100) if market_cap else None
        price_vs_ath = ((current_price - ath) / ath * 100) if ath else None
        rsi = fetch_rsi(cid)

        def mcap_label(mc):
            if mc >= 10_000_000_000: return f"${mc/1e9:.1f}B (Large)"
            if mc >= 1_000_000_000:  return f"${mc/1e9:.1f}B (Mid)"
            if mc >= 100_000_000:    return f"${mc/1e6:.0f}M (Small)"
            return f"${mc/1e6:.1f}M (Micro)"

        rows_f.append({
            "Coin": f"{info['symbol']}",
            "Price": fmt_price(current_price),
            "Market Cap": mcap_label(market_cap) if market_cap else "—",
            "Vol/MCap %": f"{vol_mcap:.1f}%" if vol_mcap else "—",
            "ATH": fmt_price(ath),
            "From ATH": f"{price_vs_ath:.0f}%" if price_vs_ath else "—",
            "7d %": f"{md.get('price_change_percentage_7d_in_currency', 0):+.1f}%",
            "30d %": f"{md.get('price_change_percentage_30d_in_currency', 0):+.1f}%",
            "RSI": f"{rsi}" if rsi else "—",
        })

    st.dataframe(pd.DataFrame(rows_f), use_container_width=True, hide_index=True)

    st.subheader("Market Cap Comparison")
    mcap_data = {
        st.session_state.holdings[cid]["symbol"]: market.get(cid, {}).get("market_cap", 0)
        for cid in COINGECKO_IDS
    }
    mcap_df = pd.DataFrame({"Coin": list(mcap_data.keys()), "Market Cap": list(mcap_data.values())})
    mcap_df = mcap_df[mcap_df["Market Cap"] > 0].sort_values("Market Cap", ascending=False)
    st.bar_chart(mcap_df.set_index("Coin"))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("👀 Watchlist")
    st.caption("Track coins you don't own yet. Add them via the sidebar.")

    if not st.session_state.watchlist:
        st.info("No coins on your watchlist yet. Use the sidebar to search and add coins.")
    else:
        rows_w = []
        for cid in st.session_state.watchlist:
            md = market.get(cid, {})
            if not md:
                continue
            current_price = md.get("current_price", 0)
            ath = md.get("ath", 0)
            price_vs_ath = ((current_price - ath) / ath * 100) if ath else None
            mc  = md.get("market_cap", 0)
            vol = md.get("total_volume", 0)
            vmp = (vol / mc * 100) if mc else None
            rsi = fetch_rsi(cid)
            signal, _, _s = compute_signal(
                rsi, fg_value, price_vs_ath,
                md.get("price_change_percentage_30d_in_currency"), None, mc, vmp
            )
            rows_w.append({
                "Coin": f"{md.get('name', cid)} ({md.get('symbol', '').upper()})",
                "Price": fmt_price(current_price),
                "Market Cap": f"${md.get('market_cap', 0)/1e9:.1f}B",
                "From ATH": f"{price_vs_ath:.0f}%" if price_vs_ath else "—",
                "7d %": f"{md.get('price_change_percentage_7d_in_currency', 0):+.1f}%",
                "RSI": f"{rsi}" if rsi else "—",
                "Signal": signal,
            })
        st.dataframe(pd.DataFrame(rows_w), use_container_width=True, hide_index=True)

st.divider()
st.caption(f"Data: CoinGecko (free) · Alternative.me · Last updated: {datetime.now().strftime('%H:%M:%S')} · Prices refresh every 5 min")
