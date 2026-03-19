import streamlit as st
import requests
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime

st.set_page_config(page_title="Crypto Tracker", page_icon="📈", layout="wide")

# ── Default Holdings ────────────────────────────────────────────────────────
DEFAULT_HOLDINGS = {
    "bitcoin":     {"symbol": "BTC",    "name": "Bitcoin",   "qty": 0.00477973,  "buy_price": round(356.08   / 0.00477973,  2)},
    "solana":      {"symbol": "SOL",    "name": "Solana",    "qty": 1.20181095,  "buy_price": round(113.73   / 1.20181095,  2)},
    "ethereum":    {"symbol": "ETH",    "name": "Ethereum",  "qty": 0.04647102,  "buy_price": round(108.00   / 0.04647102,  2)},
    "bittensor":   {"symbol": "TAO",    "name": "Bittensor", "qty": 0.35218514,  "buy_price": round(99.42    / 0.35218514,  2)},
    "chainlink":   {"symbol": "LINK",   "name": "ChainLink", "qty": 10.13085837, "buy_price": round(99.28    / 10.13085837, 2)},
    "binancecoin": {"symbol": "BNB",    "name": "BNB",       "qty": 0.14611512,  "buy_price": round(98.10    / 0.14611512,  2)},
    "render-token":{"symbol": "RENDER", "name": "Render",    "qty": 43.50722321, "buy_price": round(78.70    / 43.50722321, 2)},
}

COINGECKO_IDS = list(DEFAULT_HOLDINGS.keys())
HOLDINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holdings.json")

# ── Qualitative Fundamental Profiles ─────────────────────────────────────────
# Tier 1 = Blue Chip (+3):  Proven, institutional-grade, irreplaceable infrastructure
# Tier 2 = Established (+2): Solid use case, growing ecosystem, meaningful execution risk
# Tier 3 = Speculative (0):  Genuine innovation but early-stage and unproven at scale
#
# These scores add to the signal score so that strong fundamentals require fewer
# price signals to reach "Buy", and speculative coins need a deeper dip to qualify.
FUNDAMENTAL_TIERS = {
    "bitcoin": {
        "tier": 1,
        "tier_label": "Tier 1 — Blue Chip",
        "tier_score": 3,
        "use_case": "Digital gold / store of value / hardest money ever created",
        "strengths": [
            "Hard-capped 21M supply — mathematically scarce",
            "15+ year unbroken track record — no hacks, no downtime",
            "Spot ETFs approved (BlackRock, Fidelity) — institutional gateway",
            "Most decentralised network — 15,000+ nodes globally",
            "Legal tender in El Salvador & Central African Republic",
            "Lightning Network enables near-instant, near-free payments",
        ],
        "risks": [
            "Slow on-chain feature development by design",
            "Energy usage attracts ESG criticism",
            "Minimal programmability vs. smart-contract platforms",
        ],
    },
    "ethereum": {
        "tier": 1,
        "tier_label": "Tier 1 — Blue Chip",
        "tier_score": 3,
        "use_case": "Smart contract platform — backbone of DeFi, NFTs, and Web3",
        "strengths": [
            "Largest DeFi ecosystem ($40B+ TVL — Aave, Uniswap, Lido)",
            "Proof of Stake since 2022 — 99.95% energy reduction",
            "EIP-1559 burns ETH on every transaction — deflationary mechanics",
            "Spot ETF approved — institutional adoption accelerating",
            "4,000+ monthly active developers — most in crypto",
            "Layer-2 ecosystem (Arbitrum, Base, Optimism) scales throughput",
        ],
        "risks": [
            "Layer-2 fragmentation can dilute ETH fee revenue",
            "Competition from faster/cheaper L1s (Solana, Aptos, Sui)",
            "Complex upgrades carry execution risk",
        ],
    },
    "binancecoin": {
        "tier": 2,
        "tier_label": "Tier 2 — Established",
        "tier_score": 2,
        "use_case": "Exchange utility token powering BNB Chain (BSC) ecosystem",
        "strengths": [
            "Quarterly token burns reduce supply systematically",
            "Backed by Binance — world's largest crypto exchange by volume",
            "BNB Chain hosts active DeFi/GameFi ecosystem",
            "Low transaction fees on BSC make it accessible for retail",
            "Used for trading fee discounts, Launchpad access",
        ],
        "risks": [
            "Highly centralised — Binance controls large token supply",
            "Regulatory risk directly tied to Binance's legal standing",
            "SEC has named BNB as unregistered security in lawsuits",
            "BSC often criticised as centralised copy of Ethereum",
        ],
    },
    "solana": {
        "tier": 2,
        "tier_label": "Tier 2 — Established",
        "tier_score": 2,
        "use_case": "High-performance Layer-1 blockchain for DeFi, NFTs, and payments",
        "strengths": [
            "65,000+ TPS throughput with sub-second finality",
            "Transaction fees typically <$0.001 — best UX for retail",
            "Strong DeFi momentum (Jupiter DEX, Marinade, Raydium)",
            "Firedancer client incoming — further decentralisation & speed",
            "Growing developer base — 2nd largest in crypto after Ethereum",
            "Solana Pay adopted by Shopify, Stripe for commerce",
        ],
        "risks": [
            "Multiple network outages in 2022 damaged trust",
            "Significant VC allocation — early investors still hold large supply",
            "More centralised validator set than BTC or ETH",
            "FTX collapse damaged reputation (FTX was major backer)",
        ],
    },
    "chainlink": {
        "tier": 2,
        "tier_label": "Tier 2 — Established",
        "tier_score": 2,
        "use_case": "Decentralised oracle network — connects blockchains to real-world data",
        "strengths": [
            "~70% market share in DeFi oracles — Aave, Compound, Synthetix rely on it",
            "Google Cloud and Swift official partnerships",
            "CCIP (Cross-Chain Interoperability Protocol) expanding use case",
            "Staking v0.2 launched — token utility growing",
            "First-mover advantage — deeply embedded in DeFi infrastructure",
        ],
        "risks": [
            "Competition from Pyth Network (faster, used by Solana DeFi) and API3",
            "Growth closely tied to overall DeFi adoption",
            "Token price has historically lagged behind BTC/ETH in bull runs",
            "Oracle manipulation remains an industry-wide risk",
        ],
    },
    "bittensor": {
        "tier": 3,
        "tier_label": "Tier 3 — Speculative / High Potential",
        "tier_score": 0,
        "use_case": "Decentralised AI/ML network — miners compete by training machine learning models",
        "strengths": [
            "Unique model: mining = training AI models — aligns crypto incentives with AI",
            "Hard-capped 21M TAO supply (same as BTC) — genuine scarcity",
            "60+ active subnets covering text, image, finance, speech AI",
            "Strong mindshare at intersection of AI and crypto",
            "First-mover in decentralised AI incentive layer",
        ],
        "risks": [
            "Early stage — subnet quality and output varies widely",
            "Highly volatile — prone to sharp 50-70% drawdowns",
            "Complex tokenomics still evolving",
            "Dependent on continued AI narrative momentum",
            "Small ecosystem relative to valuation",
        ],
    },
    "render-token": {
        "tier": 3,
        "tier_label": "Tier 3 — Speculative / High Potential",
        "tier_score": 0,
        "use_case": "Decentralised GPU marketplace — connecting idle GPUs to 3D rendering and AI compute jobs",
        "strengths": [
            "Real, tangible use case — creators pay GPU providers for rendering",
            "OctaneRender (industry-leading 3D tool) integration",
            "Apple partnership — Metal GPU support",
            "Migrated to Solana — lower fees, faster settlement",
            "AI training demand growing rapidly, underpins GPU market",
        ],
        "risks": [
            "Dependent on AI/3D rendering narrative staying strong",
            "Competition from AWS, Google Cloud, and Vast.ai GPU services",
            "Token economics still evolving post-Solana migration",
            "Relatively small core team",
            "Revenue model not yet fully proven at scale",
        ],
    },
}

# ── Holdings persistence ──────────────────────────────────────────────────────
def load_holdings():
    if os.path.exists(HOLDINGS_FILE):
        try:
            with open(HOLDINGS_FILE) as f:
                saved = json.load(f)
            # Start from defaults, overlay saved values
            result = {cid: {**info} for cid, info in DEFAULT_HOLDINGS.items()}
            for cid, h in saved.items():
                if cid in result:
                    result[cid].update(h)
                else:
                    result[cid] = h  # new coin not in defaults
            return result
        except Exception:
            pass
    return {cid: {**info} for cid, info in DEFAULT_HOLDINGS.items()}

def save_holdings():
    try:
        with open(HOLDINGS_FILE, "w") as f:
            json.dump(st.session_state.holdings, f, indent=2)
    except Exception:
        pass  # Streamlit Cloud has no write access — silent fail

# ── Session state init ───────────────────────────────────────────────────────
if "holdings" not in st.session_state:
    st.session_state.holdings = load_holdings()
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# ── API helpers ──────────────────────────────────────────────────────────────
def _get_with_retry(url, timeout=10, retries=3):
    for attempt in range(retries):
        r = requests.get(url, timeout=timeout)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r

@st.cache_data(ttl=600)
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
        return None

@st.cache_data(ttl=7200)
def fetch_rsi(coin_id: str, days: int = 100):
    """
    Fetch daily closes and compute RSI using Wilder's true smoothing method:
      1. Seed: simple mean of first 14 up-moves / down-moves
      2. Smoothing: avg = (prev_avg * 13 + current) / 14  (Wilder's EMA)
    100 days gives ~86 stable RSI readings after the 14-period seed.
    """
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    try:
        r = _get_with_retry(url)
        prices = [p[1] for p in r.json().get("prices", [])]
        if len(prices) < 16:   # need at least 15 deltas for 1 seed RSI value
            return None

        closes   = pd.Series(prices)
        delta    = closes.diff().dropna()           # day-over-day changes
        gains    = delta.clip(lower=0).values       # up-moves (0 on down days)
        losses   = (-delta.clip(upper=0)).values    # down-moves (0 on up days)

        period   = 14

        # ── Step 1: seed average (simple mean of first 14 changes) ──────────
        avg_gain = gains[:period].mean()
        avg_loss = losses[:period].mean()

        # ── Step 2: Wilder's smoothing for every subsequent candle ──────────
        for g, l in zip(gains[period:], losses[period:]):
            avg_gain = (avg_gain * (period - 1) + g) / period
            avg_loss = (avg_loss * (period - 1) + l) / period

        if avg_loss == 0:
            return 100.0                            # all gains, no losses
        rs  = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 1)
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
    if p is None or p == 0: return "—"
    if p >= 1_000:  return f"${p:,.0f}"
    if p >= 1:      return f"${p:,.2f}"
    if p >= 0.01:   return f"${p:.4f}"
    return f"${p:.6f}"

def fmt_qty(q):
    if q is None: return "—"
    return f"{q:.6g}"

def fmt_score(s):
    """Show score as +5, -2, or plain 0 (not '+0')."""
    return "0" if s == 0 else f"{s:+d}"

def md_to_html_bold(text):
    """Convert **word** markdown to <b>word</b> for use inside HTML strings."""
    import re
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

# ── Signal logic ─────────────────────────────────────────────────────────────
def score_to_label(score):
    if score >= 4:  return "Strong Buy",      "🟢"
    if score >= 2:  return "Buy",              "🟩"
    if score >= 0:  return "Hold",             "🟡"
    if score >= -3: return "Caution",          "🟠"
    return              "Consider Selling",    "🔴"

def compute_signal(rsi, fg_value, price_vs_ath_pct, price_change_30d, pnl_pct,
                   market_cap=None, vol_mcap_pct=None,
                   tier_score=0, tier_reason=""):
    """
    Score breakdown (all additive):

    PRICE SIGNALS
      RSI          < 30 = +1  |  < 40 = +1  |  > 60 = -1  |  > 70 = -1
        (capped at ±1 — RSI is a 14-day signal, too noisy for weeks/months decisions)
      Fear & Greed < 25 = +2  |  < 40 = +1  |  > 60 = -1  |  > 75 = -2
        (market sentiment cycles matter even over months — full weight kept)
      ATH distance ≤-70% = +2 |  ≤-50% = +1 |  ≥-10% = -1
        (best long-term value signal — full weight kept)
      30d momentum < -25% = +1 |  > +30% = -1
      Personal P&L > +50% = -1 (partial profit nudge)

    FINANCIAL FUNDAMENTALS
      Market cap   ≥$10B = +1  |  <$500M = -1
      Vol/MCap     ≥ 5%  = +1  |  <  1%  = -1

    QUALITATIVE FUNDAMENTALS (via FUNDAMENTAL_TIERS)
      Tier 1 (Blue Chip)             = +3   e.g. BTC, ETH  — dominant factor for long-term
      Tier 2 (Established)           = +2   e.g. BNB, SOL, LINK
      Tier 3 (Speculative/Potential) =  0   e.g. TAO, RENDER — need strong price signals

    CALIBRATED FOR: weeks-to-months holding period.
    Blue chips (BTC, ETH) rate Buy/Strong Buy in neutral markets — always accumulate quality.
    Speculative coins (TAO, RENDER) require deeper discounts to trigger Buy.
    At bull tops: blue chips → Caution (don't add); speculative → Consider Selling (trim).

    LABELS: Strong Buy ≥+4 | Buy ≥+2 | Hold ≥0 | Caution ≥-3 | Consider Selling <-3
    """
    score = 0
    price_reasons = []
    fund_reasons  = []

    # ── Price signals ─────────────────────────────────────────────────────────
    # RSI weight reduced to ±1 at extremes (from ±2) because RSI is a 14-day
    # indicator — too short-term to dominate decisions made every few weeks/months.
    if rsi is not None:
        if rsi < 30:    score += 1; price_reasons.append(f"RSI {rsi} — oversold (potential entry)")
        elif rsi < 40:  score += 1; price_reasons.append(f"RSI {rsi} — leaning oversold")
        elif rsi > 70:  score -= 1; price_reasons.append(f"RSI {rsi} — overbought (caution on adding)")
        elif rsi > 60:  score -= 1; price_reasons.append(f"RSI {rsi} — leaning overbought")

    if fg_value is not None:
        if fg_value < 25:   score += 2; price_reasons.append(f"Fear & Greed {fg_value} — extreme fear (buy zone)")
        elif fg_value < 40: score += 1; price_reasons.append(f"Fear & Greed {fg_value} — fear")
        elif fg_value > 75: score -= 2; price_reasons.append(f"Fear & Greed {fg_value} — extreme greed (sell zone)")
        elif fg_value > 60: score -= 1; price_reasons.append(f"Fear & Greed {fg_value} — greed")

    if price_vs_ath_pct is not None:
        if price_vs_ath_pct <= -70:   score += 2; price_reasons.append(f"{abs(price_vs_ath_pct):.0f}% below ATH — historically cheap")
        elif price_vs_ath_pct <= -50: score += 1; price_reasons.append(f"{abs(price_vs_ath_pct):.0f}% below ATH — discounted")
        elif price_vs_ath_pct >= -10: score -= 1; price_reasons.append("Near ATH — limited upside at current price")

    if price_change_30d is not None:
        if price_change_30d < -25:  score += 1; price_reasons.append(f"Down {abs(price_change_30d):.0f}% in 30d — potential dip entry")
        elif price_change_30d > 30: score -= 1; price_reasons.append(f"Up {price_change_30d:.0f}% in 30d — short-term momentum high")

    if pnl_pct is not None and pnl_pct > 50:
        score -= 1; price_reasons.append(f"Up {pnl_pct:.0f}% from your buy — consider taking partial profit")

    # ── Financial fundamentals ────────────────────────────────────────────────
    if market_cap is not None:
        if market_cap >= 10_000_000_000:  score += 1; fund_reasons.append("Large cap (>$10B) — established, lower risk")
        elif market_cap < 500_000_000:    score -= 1; fund_reasons.append("Small/micro cap (<$500M) — higher risk")

    if vol_mcap_pct is not None:
        if vol_mcap_pct >= 5:   score += 1; fund_reasons.append(f"Vol/MCap {vol_mcap_pct:.1f}% — strong liquidity")
        elif vol_mcap_pct < 1:  score -= 1; fund_reasons.append(f"Vol/MCap {vol_mcap_pct:.1f}% — low liquidity")

    # ── Qualitative fundamentals (tier) ───────────────────────────────────────
    if tier_score != 0 and tier_reason:
        score += tier_score
        fund_reasons.append(tier_reason)

    label, color = score_to_label(score)
    return f"{color} {label}", price_reasons + fund_reasons, score

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 Crypto Tracker")

    # ── Section 1: Log a purchase ────────────────────────────────────────
    st.subheader("➕ Log a Purchase")
    st.caption("Add a new buy — qty and avg price update automatically.")

    holding_options = {
        info["name"]: cid
        for cid, info in st.session_state.holdings.items()
    }
    selected_name = st.selectbox("Coin", list(holding_options.keys()), key="buy_coin")
    selected_cid  = holding_options[selected_name]

    col_q, col_p = st.columns(2)
    new_qty   = col_q.number_input("Qty bought", min_value=0.0, value=0.0, format="%.6f", key="new_qty")
    new_price = col_p.number_input("Price paid ($)", min_value=0.0, value=0.0, format="%.2f", key="new_price")

    if st.button("✅ Add to Portfolio", use_container_width=True):
        if new_qty > 0 and new_price > 0:
            h = st.session_state.holdings[selected_cid]
            old_qty   = h["qty"]
            old_price = h["buy_price"]
            total_qty = old_qty + new_qty
            # Weighted average buy price
            avg_price = (old_qty * old_price + new_qty * new_price) / total_qty
            st.session_state.holdings[selected_cid]["qty"]       = round(total_qty, 8)
            st.session_state.holdings[selected_cid]["buy_price"] = round(avg_price, 2)
            save_holdings()
            st.success(f"Added {fmt_qty(new_qty)} {h['symbol']} @ {fmt_price(new_price)}. New avg: {fmt_price(avg_price)}")
            st.rerun()
        else:
            st.warning("Enter qty and price > 0")

    st.divider()

    # ── Section 2: Edit buy prices ───────────────────────────────────────
    with st.expander("✏️ Edit Buy Prices / Qty", expanded=False):
        st.caption("Manually adjust any holding. Changes save automatically.")
        for cid, info in st.session_state.holdings.items():
            st.markdown(f"**{info['symbol']}**")
            c1, c2 = st.columns(2)
            new_q = c1.number_input("Qty", min_value=0.0, value=float(info["qty"]),
                                    format="%.6f", key=f"eq_{cid}")
            new_b = c2.number_input("Avg buy $", min_value=0.0, value=float(info["buy_price"]),
                                    format="%.2f", key=f"eb_{cid}")
            if new_q != info["qty"] or new_b != info["buy_price"]:
                st.session_state.holdings[cid]["qty"]       = new_q
                st.session_state.holdings[cid]["buy_price"] = new_b
                save_holdings()

    st.divider()

    # ── Section 3: Watchlist ─────────────────────────────────────────────
    st.subheader("👀 Watchlist")
    st.caption("Track coins you don't own yet.")
    wl_query = st.text_input("Search coin", placeholder="e.g. Pepe", key="wl_search")
    if wl_query:
        results = search_coin(wl_query)
        for coin in results:
            if st.button(f"+ {coin['name']} ({coin['symbol'].upper()})", key=f"add_{coin['id']}"):
                if coin["id"] not in st.session_state.watchlist:
                    st.session_state.watchlist.append(coin["id"])
                    st.rerun()

    if st.session_state.watchlist:
        for wid in st.session_state.watchlist:
            # Show name from market data if available, else ID
            wname = st.session_state.get("last_market", {}).get(wid, {}).get("name", wid)
            wsym  = st.session_state.get("last_market", {}).get(wid, {}).get("symbol", "").upper()
            label = f"{wname} ({wsym})" if wsym else wname
            c1, c2 = st.columns([4, 1])
            c1.caption(label)
            if c2.button("✕", key=f"rm_{wid}"):
                st.session_state.watchlist.remove(wid)
                st.rerun()

# ── Fetch data ────────────────────────────────────────────────────────────────
all_ids = tuple(list(st.session_state.holdings.keys()) + st.session_state.watchlist)
market_result = fetch_market_data(all_ids)
if market_result is not None:
    st.session_state["last_market"] = market_result
market = st.session_state.get("last_market", {})
if market_result is None:
    st.warning("⚠️ CoinGecko rate limit — showing last known prices. Refreshes in ~10 min.", icon="⏳")
fg_value, fg_label = fetch_fear_greed()

# ── Pre-compute all coin metrics ──────────────────────────────────────────────
coin_metrics = {}
for cid, info in st.session_state.holdings.items():
    md         = market.get(cid, {})
    cp         = md.get("current_price", 0)
    ath        = md.get("ath", 0)
    mcap       = md.get("market_cap", 0)
    vol        = md.get("total_volume", 0)
    vol_mcap   = (vol / mcap * 100) if mcap else None
    ath_pct    = ((cp - ath) / ath * 100) if ath else None
    ch30       = md.get("price_change_percentage_30d_in_currency")
    bp         = info["buy_price"]
    pnl_pct    = ((cp - bp) / bp * 100) if bp > 0 and cp else None
    rsi        = fetch_rsi(cid)

    # Pull qualitative tier profile (falls back gracefully for unknown coins)
    tier_info  = FUNDAMENTAL_TIERS.get(cid, {})
    tier_score = tier_info.get("tier_score", 0)
    tier_label = tier_info.get("tier_label", "Unrated")
    tier_reason = (
        f"{tier_label} — {tier_info['use_case']}"
        if tier_info else ""
    )

    signal, reasons, score = compute_signal(
        rsi, fg_value, ath_pct, ch30, pnl_pct, mcap, vol_mcap,
        tier_score=tier_score, tier_reason=tier_reason
    )
    coin_metrics[cid] = dict(
        info=info, md=md, cp=cp, ath=ath, mcap=mcap,
        vol_mcap=vol_mcap, ath_pct=ath_pct, ch30=ch30,
        pnl_pct=pnl_pct, rsi=rsi, signal=signal, reasons=reasons, score=score,
        value=info["qty"] * cp,
        tier_info=tier_info, tier_label=tier_label, tier_score=tier_score
    )

tab0, tab1, tab2, tab3, tab4 = st.tabs(
    ["🎯 Analysis", "💼 Portfolio", "🚦 Signals", "📊 Fundamentals", "👀 Watchlist"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 0: OVERALL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab0:
    st.header("🎯 Overall Analysis")
    st.caption("Combined score calibrated for weeks-to-months investing: qualitative fundamentals (technology tier) carry the most weight, followed by market sentiment (Fear & Greed) and ATH distance. RSI is intentionally down-weighted — it's a 14-day signal, too noisy for your timeframe.")

    scores    = [m["score"] for m in coin_metrics.values()]
    avg_score = sum(scores) / len(scores) if scores else 0
    port_label, port_color = score_to_label(round(avg_score))

    buys      = sum(1 for s in scores if s >= 2)
    holds     = sum(1 for s in scores if 0 <= s < 2)
    cautions  = sum(1 for s in scores if -3 <= s < 0)
    sell_warn = sum(1 for s in scores if s < -3)

    if fg_value is not None:
        if fg_value < 25:   fg_sent = "Market is in **Extreme Fear** — historically a good time to accumulate."
        elif fg_value < 40: fg_sent = "Market is in **Fear** — cautious accumulation may be appropriate."
        elif fg_value < 60: fg_sent = "Market is **Neutral** — no strong macro signal either way."
        elif fg_value < 75: fg_sent = "Market is in **Greed** — be selective, avoid chasing pumps."
        else:               fg_sent = "Market is in **Extreme Greed** — consider reducing exposure."
    else:
        fg_sent = ""

    verdict_bg = {"Strong Buy": "#1a3a1a", "Buy": "#1a2e1a", "Hold": "#2e2a1a",
                  "Caution": "#2e1f0a", "Consider Selling": "#2e0a0a"}
    bg = verdict_bg.get(port_label, "#1a1a1a")

    fg_sent_html = md_to_html_bold(fg_sent)
    st.markdown(
        f"""<div style="background:{bg};border-radius:12px;padding:20px 24px;margin-bottom:16px">
        <div style="font-size:2rem;font-weight:700">{port_color} Portfolio Verdict: {port_label}</div>
        <div style="color:#ccc;margin-top:6px">Average score: <b>{avg_score:+.1f}</b> across {len(scores)} coins
        &nbsp;·&nbsp; {fg_sent_html}</div></div>""",
        unsafe_allow_html=True
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("🟢 Buy / Strong Buy", buys,      help="Score ≥ 2")
    k2.metric("🟡 Hold",             holds,     help="Score 0–1")
    k3.metric("🟠 Caution",          cautions,  help="Score −1 to −3")
    k4.metric("🔴 Consider Selling", sell_warn, help="Score below −3")
    fg_display = f"{fg_value} ({fg_label})" if fg_value else "—"
    fg_delta   = "Extreme Fear ↓" if fg_value and fg_value < 25 else ("Extreme Greed ↑" if fg_value and fg_value > 75 else None)
    k5.metric("😨 Fear & Greed", fg_display, delta=fg_delta,
              delta_color="inverse" if fg_delta and "Greed" in fg_delta else "normal")

    st.divider()

    # ── Per-coin rating table ──────────────────────────────────────────────
    st.subheader("Per-Coin Rating")
    rows_a = []
    for cid, m in coin_metrics.items():
        rows_a.append({
            "Coin":       f"{m['info']['name']} ({m['info']['symbol']})",
            "Qual. Tier": m["tier_label"],
            "Price":      fmt_price(m["cp"]),
            "RSI":        f"{m['rsi']}" if m["rsi"] else "—",
            "From ATH":   f"{m['ath_pct']:.0f}%" if m["ath_pct"] else "—",
            "30d %":      f"{m['ch30']:+.1f}%" if m["ch30"] else "—",
            "P&L %":      f"{m['pnl_pct']:+.1f}%" if m["pnl_pct"] is not None else "—",
            "Score":      fmt_score(m["score"]),
            "Rating":     m["signal"],
        })
    st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)

    st.divider()

    # ── Investment allocator ───────────────────────────────────────────────
    st.subheader("💡 How Should I Allocate My Next Buy?")
    st.caption("Score-weighted allocation across coins rated Buy or above. Adjust the amount to see suggested split.")

    invest_amt = st.number_input("Amount I want to invest ($)", min_value=0.0,
                                 value=500.0, step=100.0, format="%.0f")

    buyable = {cid: m for cid, m in coin_metrics.items() if m["score"] >= 2}

    if not buyable:
        st.info("No coins currently rated Buy or above. Consider waiting for better entry conditions.")
    else:
        # Weights proportional to score (min score shifted to 1)
        min_score  = min(m["score"] for m in buyable.values())
        shift      = max(0, 1 - min_score)
        raw_weights = {cid: m["score"] + shift for cid, m in buyable.items()}
        total_w    = sum(raw_weights.values())
        alloc_rows = []
        # Build ratio string: normalize relative to lowest weight
        min_w = min(raw_weights.values())
        for cid, w in raw_weights.items():
            m       = buyable[cid]
            pct     = w / total_w
            dollars = invest_amt * pct
            ratio   = round(w / min_w, 1)
            alloc_rows.append({
                "Coin":        f"{m['info']['name']} ({m['info']['symbol']})",
                "Rating":      m["signal"],
                "Score":       fmt_score(m["score"]),
                "Weight":      f"{pct*100:.0f}%",
                "Suggested $": f"${dollars:,.0f}",
                "Est. Qty":    fmt_qty(dollars / m["cp"]) if m["cp"] and m["cp"] > 0 else "—",
                "Ratio":       f"{ratio:.1g}x",
            })
        st.dataframe(pd.DataFrame(alloc_rows), use_container_width=True, hide_index=True)

        # Ratio string e.g. "BTC : ETH : SOL = 2 : 1.5 : 1"
        ratio_parts = [
            f"{buyable[cid]['info']['symbol']} {round(raw_weights[cid]/min_w, 1):.1g}"
            for cid in buyable
        ]
        st.caption(f"Suggested ratio: **{' : '.join(ratio_parts)}**  (based on signal scores)")

        if avg_score >= 2:
            st.caption("💬 Buying conditions are positive. You can deploy the full amount or split into 2–3 entries (DCA).")
        else:
            st.caption("💬 Mixed market conditions. Consider splitting into smaller entries over time rather than one lump sum.")

    st.divider()

    # ── Key insights ───────────────────────────────────────────────────────
    st.subheader("Key Insights")

    best = max(coin_metrics.items(), key=lambda x: x[1]["score"])
    worst = min(coin_metrics.items(), key=lambda x: x[1]["score"])
    most_disc = min(
        ((cid, m) for cid, m in coin_metrics.items() if m["ath_pct"] is not None),
        key=lambda x: x[1]["ath_pct"], default=None
    )

    insights = []
    insights.append(f"**Best opportunity:** {best[1]['info']['name']} ({best[1]['info']['symbol']}) — score {best[1]['score']:+d}, rated {best[1]['signal']}")
    if worst[1]["score"] < 0:
        insights.append(f"**Most cautious:** {worst[1]['info']['name']} ({worst[1]['info']['symbol']}) — score {worst[1]['score']:+d}, rated {worst[1]['signal']}")
    if most_disc:
        cid, m = most_disc
        insights.append(f"**Most discounted:** {m['info']['name']} ({m['info']['symbol']}) is {m['ath_pct']:.0f}% below its ATH of {fmt_price(m['ath'])}")
    if avg_score >= 3:
        insights.append("**Overall:** Strong buying conditions. Consider adding to positions if capital is available.")
    elif avg_score >= 1:
        insights.append("**Overall:** Mild buying conditions. DCA (spreading buys over time) is a prudent approach.")
    elif avg_score >= -1:
        insights.append("**Overall:** Mixed signals. Hold current positions and wait for a clearer direction.")
    elif avg_score >= -3:
        insights.append("**Overall:** Caution warranted. Review positions and risk tolerance before adding.")
    else:
        insights.append("**Overall:** Bearish signals. Consider reducing exposure if you're uncomfortable with current volatility.")

    for ins in insights:
        st.markdown(f"- {ins}")

    st.caption("⚠️ Not financial advice. Always do your own research before making investment decisions.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("💼 Portfolio")

    if fg_value:
        fg_color = "🟢" if fg_value < 25 else "🟡" if fg_value < 50 else "🟠" if fg_value < 75 else "🔴"
        st.info(f"**Market Sentiment:** {fg_color} Fear & Greed = **{fg_value}** ({fg_label})  ·  Rating column shows current Buy/Sell signal for each holding.")

    rows = []
    total_value = total_cost = 0.0

    for cid, info in st.session_state.holdings.items():
        md         = market.get(cid, {})
        cp         = md.get("current_price", 0)
        qty        = info["qty"]
        bp         = info["buy_price"]
        value      = qty * cp
        cost       = qty * bp if bp > 0 else None
        pnl        = value - cost if cost else None
        pnl_pct    = (pnl / cost * 100) if cost else None
        ch24       = md.get("price_change_percentage_24h")
        total_value += value
        if cost: total_cost += cost
        m_signal   = coin_metrics.get(cid, {}).get("signal", "—")
        rows.append({
            "Coin":          f"{info['name']} ({info['symbol']})",
            "Rating":        m_signal,
            "Qty":           fmt_qty(qty),
            "Avg Buy":       fmt_price(bp) if bp > 0 else "—",
            "Price":         fmt_price(cp),
            "24h %":         f"{ch24:+.1f}%" if ch24 is not None else "—",
            "Value":         f"${value:,.2f}",
            "P&L $":         f"${pnl:+,.2f}" if pnl is not None else "—",
            "P&L %":         f"{pnl_pct:+.1f}%" if pnl_pct is not None else "—",
        })

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Value", f"${total_value:,.2f}")
    if total_cost > 0:
        total_pnl = total_value - total_cost
        k2.metric("Total Cost Basis", f"${total_cost:,.2f}")
        k3.metric("Total P&L", f"${total_pnl:+,.2f}", delta=f"{total_pnl/total_cost*100:+.1f}%")

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Allocation by Value")
    alloc = {
        st.session_state.holdings[cid]["symbol"]: coin_metrics[cid]["value"]
        for cid in st.session_state.holdings
        if cid in coin_metrics and coin_metrics[cid]["value"] > 0
    }
    if alloc:
        alloc_df = pd.DataFrame({"Coin": list(alloc.keys()), "Value ($)": list(alloc.values())})
        st.bar_chart(alloc_df.set_index("Coin"))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: SIGNALS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🚦 Buy / Sell Signals")
    st.caption("Expand any coin to see the detailed factors behind its rating.")

    if fg_value:
        st.info(f"**Fear & Greed: {fg_value} — {fg_label}** · <25 = buy zone · >75 = sell zone")

    # Quick summary table — all key numbers at a glance
    sig_rows = []
    for cid, m in coin_metrics.items():
        sig_rows.append({
            "Coin":       m["info"]["symbol"],
            "Rating":     m["signal"],
            "Score":      fmt_score(m["score"]),
            "Price":      fmt_price(m["cp"]),
            "RSI":        f"{m['rsi']}" if m["rsi"] else "—",
            "From ATH":   f"{m['ath_pct']:.0f}%" if m["ath_pct"] else "—",
            "30d %":      f"{m['ch30']:+.1f}%" if m["ch30"] else "—",
            "P&L %":      f"{m['pnl_pct']:+.1f}%" if m["pnl_pct"] is not None else "—",
        })
    st.dataframe(pd.DataFrame(sig_rows), use_container_width=True, hide_index=True)
    st.divider()

    for cid, m in coin_metrics.items():
        info = m["info"]
        with st.expander(
            f"{info['name']} ({info['symbol']}) — {m['signal']} (score {fmt_score(m['score'])})",
            expanded=False
        ):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Price",      fmt_price(m["cp"]))
            c2.metric("P&L",        f"{m['pnl_pct']:+.1f}%" if m["pnl_pct"] is not None else "—")
            c3.metric("RSI (14d)",  f"{m['rsi']}" if m["rsi"] else "—",
                      help="<30 oversold · >70 overbought")
            c4.metric("From ATH",   f"{m['ath_pct']:.1f}%" if m["ath_pct"] else "—")
            c5.metric("30d Change", f"{m['ch30']:+.1f}%" if m["ch30"] else "—")

            if m["tier_info"]:
                st.caption(f"🏛️ **{m['tier_label']}** — {m['tier_info'].get('use_case', '')}")

            if m["reasons"]:
                # Split into price signals vs fundamental signals for clarity
                price_rs = [r for r in m["reasons"] if any(k in r for k in ["RSI", "Fear", "ATH", "30d", "Down", "Up ", "Near ATH"])]
                fund_rs  = [r for r in m["reasons"] if r not in price_rs]
                if price_rs:
                    st.markdown("**📈 Price signals:**")
                    for r in price_rs:
                        st.markdown(f"- {r}")
                if fund_rs:
                    st.markdown("**🏛️ Fundamental signals:**")
                    for r in fund_rs:
                        st.markdown(f"- {r}")
            else:
                st.info("No strong signals in either direction at this time.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: FUNDAMENTALS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("📊 Fundamentals")
    st.caption("Market metrics + qualitative coin profiles — what each coin does, why it matters, and what risks to watch.")

    with st.expander("📖 How to read these metrics", expanded=False):
        st.markdown("""
| Metric | Good sign | Red flag |
|---|---|---|
| **Qual. Tier** | Tier 1 = Blue Chip (proven, institutional) | Tier 3 = Speculative (early-stage) |
| **Market Cap** | >$10B (large cap = stable) | <$100M (micro cap = risky) |
| **Vol/MCap %** | >3% (active, liquid) | <0.5% (illiquid, hard to exit) |
| **From ATH** | −50% to −80% (historically cheap) | Near 0% (near peak) |
| **7d / 30d %** | Moderate positive | Extreme >50% (FOMO) or deep negative |
| **RSI** | 30–50 (healthy zone) | <20 or >80 (extremes) |

**Qual. Tier scoring in signal:** Tier 1 = +3 pts · Tier 2 = +2 pts · Tier 3 = 0 pts
Calibrated for a weeks-to-months holding style: blue chips (BTC, ETH) rate Buy/Strong Buy even in neutral markets — you should always be accumulating quality assets. Speculative coins (TAO, RENDER) need a genuine price dip to trigger Buy. At bull tops: blue chips → Caution (pause buying); speculative coins → Consider Selling (trim positions).
""")

    def mcap_label(mc):
        if mc >= 10_000_000_000: return f"${mc/1e9:.1f}B (Large)"
        if mc >= 1_000_000_000:  return f"${mc/1e9:.1f}B (Mid)"
        if mc >= 100_000_000:    return f"${mc/1e6:.0f}M (Small)"
        return f"${mc/1e6:.1f}M (Micro)"

    rows_f = []
    for cid, m in coin_metrics.items():
        md = m["md"]
        rows_f.append({
            "Coin":        m["info"]["symbol"],
            "Qual. Tier":  m["tier_label"],
            "Price":       fmt_price(m["cp"]),
            "Market Cap":  mcap_label(m["mcap"]) if m["mcap"] else "—",
            "Vol/MCap %":  f"{m['vol_mcap']:.1f}%" if m["vol_mcap"] else "—",
            "ATH":         fmt_price(m["ath"]),
            "From ATH":    f"{m['ath_pct']:.0f}%" if m["ath_pct"] else "—",
            "7d %":        f"{md.get('price_change_percentage_7d_in_currency', 0):+.1f}%",
            "30d %":       f"{m['ch30']:+.1f}%" if m["ch30"] else "—",
            "RSI":         f"{m['rsi']}" if m["rsi"] else "—",
        })
    st.dataframe(pd.DataFrame(rows_f), use_container_width=True, hide_index=True)

    st.subheader("Market Cap Comparison")
    mcap_df = pd.DataFrame({
        "Coin": [m["info"]["symbol"] for m in coin_metrics.values()],
        "Market Cap ($B)": [m["mcap"] / 1e9 for m in coin_metrics.values()],
    }).query("`Market Cap ($B)` > 0").sort_values("Market Cap ($B)", ascending=False)
    st.bar_chart(mcap_df.set_index("Coin"))

    st.divider()

    # ── Qualitative Coin Profiles ──────────────────────────────────────────
    st.subheader("🏛️ Coin Profiles — What You're Investing In")
    st.caption("Expand each coin to see its use case, competitive strengths, and key risks. This is the qualitative layer behind the signal score.")

    tier_colors = {"Tier 1": "#1a3a1a", "Tier 2": "#1a2a3a", "Tier 3": "#2e2a1a"}
    tier_badges = {"Tier 1": "🟢", "Tier 2": "🔵", "Tier 3": "🟡"}

    for cid, m in coin_metrics.items():
        tf = m["tier_info"]
        if not tf:
            continue
        info      = m["info"]
        tier_key  = f"Tier {tf['tier']}"
        badge     = tier_badges.get(tier_key, "⚪")
        bg_color  = tier_colors.get(tier_key, "#1a1a1a")

        with st.expander(
            f"{badge} **{info['name']} ({info['symbol']})** — {tf['tier_label']}",
            expanded=False
        ):
            st.markdown(
                f"<div style='background:{bg_color};border-radius:8px;padding:10px 16px;margin-bottom:10px'>"
                f"<b>Use case:</b> {tf['use_case']}</div>",
                unsafe_allow_html=True
            )

            col_s, col_r = st.columns(2)
            with col_s:
                st.markdown("**✅ Key Strengths**")
                for s in tf["strengths"]:
                    st.markdown(f"- {s}")
            with col_r:
                st.markdown("**⚠️ Key Risks**")
                for r in tf["risks"]:
                    st.markdown(f"- {r}")

            st.caption(
                f"Signal contribution: **{tf['tier_label']}** adds "
                f"**{'+' if tf['tier_score'] > 0 else ''}{tf['tier_score']} pts** to this coin's overall score."
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("👀 Watchlist")
    st.caption("Coins you're monitoring. Add them via the sidebar search.")

    if not st.session_state.watchlist:
        st.info("Nothing on your watchlist yet — use the sidebar to search and add coins.")
    else:
        rows_w = []
        for cid in st.session_state.watchlist:
            md = market.get(cid, {})
            if not md:
                continue
            cp       = md.get("current_price", 0)
            ath      = md.get("ath", 0)
            ath_pct  = ((cp - ath) / ath * 100) if ath else None
            mc       = md.get("market_cap", 0)
            vol      = md.get("total_volume", 0)
            vmp      = (vol / mc * 100) if mc else None
            rsi      = fetch_rsi(cid)
            signal, _, _s = compute_signal(
                rsi, fg_value, ath_pct,
                md.get("price_change_percentage_30d_in_currency"), None, mc, vmp
            )
            rows_w.append({
                "Coin":       f"{md.get('name', cid)} ({md.get('symbol', '').upper()})",
                "Price":      fmt_price(cp),
                "Market Cap": f"${mc/1e9:.1f}B" if mc else "—",
                "From ATH":   f"{ath_pct:.0f}%" if ath_pct else "—",
                "7d %":       f"{md.get('price_change_percentage_7d_in_currency', 0):+.1f}%",
                "RSI":        f"{rsi}" if rsi else "—",
                "Signal":     signal,
            })
        st.dataframe(pd.DataFrame(rows_w), use_container_width=True, hide_index=True)

st.divider()
st.caption(
    f"Data: CoinGecko (free) · Alternative.me · "
    f"Prices refresh every 10 min · RSI every 2 hrs · Fear & Greed every 1 hr · "
    f"Last loaded: {datetime.now().strftime('%H:%M:%S')}"
)
