import streamlit as st
import requests
import pandas as pd
import numpy as np
import json
import os
import re
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
# 4-tier system — the model assesses each coin's investment merit honestly.
# A coin can score zero (no fundamental credit) if the thesis is weak.
#
# Tier 1 — Institutional Grade  (+3): Irreplaceable, deepest institutional adoption
# Tier 2 — High Conviction      (+2): Real ecosystem traction, defensible moat
# Tier 3 — Conditional          (+1): Real use case but meaningful competitive risk
# Tier 4 — Low Conviction       ( 0): Interesting thesis, unproven at scale — no credit
#
# fundamental_verdict: the model's honest, opinionated investment case for each coin.
# This is what you should read before deciding whether to hold or add a position.
FUNDAMENTAL_TIERS = {
    "bitcoin": {
        "tier": 1,
        "tier_label": "Tier 1 — Institutional Grade",
        "tier_score": 3,
        "use_case": "Digital gold / store of value / hardest money ever created",
        "fundamental_verdict": (
            "Core holding — always accumulate. "
            "Irreplaceable store of value: hard-capped 21M supply, 15+ year unbroken track record, "
            "and accelerating institutional adoption via spot ETFs (BlackRock, Fidelity). "
            "No credible competitor for the 'digital gold' thesis. "
            "Never sell your entire position — size up on every major dip."
        ),
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
        "tier_label": "Tier 1 — Institutional Grade",
        "tier_score": 3,
        "use_case": "Smart contract platform — backbone of DeFi, NFTs, and Web3",
        "fundamental_verdict": (
            "Core holding — always accumulate. "
            "The smart contract standard with no credible challenger at scale: "
            "deepest DeFi TVL, most active developers, spot ETF approved, deflationary EIP-1559 mechanics. "
            "L2 fragmentation is a real risk but ETH remains the settlement layer. "
            "Size up on every significant dip."
        ),
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
    "solana": {
        "tier": 2,
        "tier_label": "Tier 2 — High Conviction",
        "tier_score": 2,
        "use_case": "High-performance Layer-1 blockchain for DeFi, NFTs, and payments",
        "fundamental_verdict": (
            "High conviction — accumulate on dips. "
            "The strongest L1 challenger to Ethereum: fastest throughput, best retail UX (<$0.001 fees), "
            "and real DEX volume rivalling Ethereum. Firedancer upgrade improves decentralisation further. "
            "The FTX collapse overhang has largely cleared. "
            "Execution risk remains (past outages), but the ecosystem is real and growing fast."
        ),
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
        "tier_label": "Tier 2 — High Conviction",
        "tier_score": 2,
        "use_case": "Decentralised oracle network — connects blockchains to real-world data",
        "fundamental_verdict": (
            "High conviction — often overlooked, genuinely essential. "
            "~70% oracle market share; every major DeFi protocol (Aave, Compound, Synthetix) depends on LINK. "
            "CCIP is expanding into cross-chain interoperability — a new growth vector. "
            "Token has historically underperformed in bull runs but the infrastructure moat is deep. "
            "Accumulate; the network's value grows with every new DeFi protocol that launches."
        ),
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
    "binancecoin": {
        "tier": 3,
        "tier_label": "Tier 3 — Conditional Conviction",
        "tier_score": 1,
        "use_case": "Exchange utility token powering BNB Chain (BSC) ecosystem",
        "fundamental_verdict": (
            "Conditional hold — real ecosystem, but thesis depends on Binance's survival. "
            "BNB's value is inseparable from Binance's health: if Binance faces existential regulatory action "
            "(ongoing SEC lawsuit, global restrictions), BNB's price would collapse regardless of on-chain activity. "
            "The BSC ecosystem is active but largely a centralised replica of Ethereum. "
            "Hold if you already own it, but do not size up aggressively — the regulatory overhang is real."
        ),
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
    "render-token": {
        "tier": 3,
        "tier_label": "Tier 3 — Conditional Conviction",
        "tier_score": 1,
        "use_case": "Decentralised GPU marketplace — connecting idle GPUs to 3D rendering and AI compute jobs",
        "fundamental_verdict": (
            "Moderate conviction — real product, but size conservatively. "
            "RENDER has genuine revenue: OctaneRender is used by real studios and creators, "
            "and the AI/GPU compute boom directly benefits the network. "
            "However, AWS, Google Cloud, and CoreWeave are competing for the same market with far more capital. "
            "The token must prove it captures value better than centralised alternatives at scale. "
            "Accumulate on deep dips; do not overweight — keep position small relative to core holdings."
        ),
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
    "bittensor": {
        "tier": 4,
        "tier_label": "Tier 4 — Low Conviction",
        "tier_score": 0,
        "use_case": "Decentralised AI/ML network — miners compete by training machine learning models",
        "fundamental_verdict": (
            "Low conviction — fascinating thesis, but thesis requires decentralised AI to win. "
            "The problem: OpenAI, Google, and Anthropic are winning the AI race by a wide margin, "
            "and centralised AI has structural advantages (unified training, massive capital, speed). "
            "TAO subnets produce outputs that are orders of magnitude behind frontier models. "
            "The 21M supply cap and first-mover narrative drive speculation, but speculation is not a thesis. "
            "Only hold a small position if you have genuine, researched conviction in decentralised AI long-term. "
            "Consider trimming if the AI decentralisation narrative weakens — exit thesis is unclear."
        ),
        "strengths": [
            "Unique model: mining = training AI models — aligns crypto incentives with AI",
            "Hard-capped 21M TAO supply (same as BTC) — genuine scarcity",
            "60+ active subnets covering text, image, finance, speech AI",
            "Strong mindshare at intersection of AI and crypto",
            "First-mover in decentralised AI incentive layer",
        ],
        "risks": [
            "Centralised AI (OpenAI, Google, Anthropic) is winning by a wide margin",
            "Subnet output quality far below frontier AI models",
            "Complex tokenomics still evolving — subnet economics not fully proven",
            "Highly volatile — prone to sharp 50-70% drawdowns",
            "Small ecosystem relative to valuation; dependent on continued AI narrative",
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
                   tier_score=0, tier_reason="",
                   coin_alloc_pct=None, speculative_alloc_pct=None):
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
      Tier 1 (Institutional Grade)  = +3   BTC, ETH  — irreplaceable, deepest institutional adoption
      Tier 2 (High Conviction)      = +2   SOL, LINK — real ecosystem traction, defensible moat
      Tier 3 (Conditional)          = +1   BNB, RENDER — real use case, meaningful competitive risk
      Tier 4 (Low Conviction)       =  0   TAO — interesting thesis, unproven vs centralised competitors

    Tier 4 coins receive no fundamental credit. They must earn a Buy entirely through
    price signals (cheap vs ATH, low fear, oversold RSI). This is intentional: the model
    is not convinced the investment thesis is strong enough to reward buying in neutral markets.

    PORTFOLIO COMPOSITION
      Single-coin weight         > 30% of portfolio = -1  (concentrated position, adds risk)
      Tier 3+4 combined weight   > 40% of portfolio = -1  (applied to Tier 3/4 coins — high
                                                            speculative/conditional exposure)

    CALIBRATED FOR: weeks-to-months holding period.
    Blue chips (BTC, ETH) rate Buy/Strong Buy in neutral markets — always accumulate quality.
    Speculative coins (TAO, RENDER) rate Hold/Buy in neutral markets — accumulate on dips.
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
    # Always append reason so the verdict is visible in Signals tab even for Tier 4.
    # score += 0 is a no-op for Tier 4 coins (tier_score == 0).
    if tier_reason:
        score += tier_score
        fund_reasons.append(tier_reason)

    # ── Portfolio composition ──────────────────────────────────────────────────
    if coin_alloc_pct is not None and coin_alloc_pct > 30:
        score -= 1
        fund_reasons.append(
            f"Concentrated position — {coin_alloc_pct:.0f}% of your portfolio in this coin"
        )

    if speculative_alloc_pct is not None and speculative_alloc_pct > 40 and tier_score <= 1:
        score -= 1
        fund_reasons.append(
            f"High speculative exposure — Tier 3/4 coins are {speculative_alloc_pct:.0f}% of your portfolio"
        )

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

# ── Sell signal thresholds (by tier_score) ───────────────────────────────────
# (trim_25, trim_50, major_profits, full_exit)
# Higher-tier coins need stronger signals before a sell is warranted.
# Tier 1 never triggers full exit — accumulate quality through cycles.
SELL_THRESHOLDS = {
    3: (5,  8, 10, 99),   # Tier 1 — very high bar; never "full exit"
    2: (4,  7,  9, 14),   # Tier 2 — quality; sell reluctantly
    1: (3,  5,  8, 12),   # Tier 3 — conditional; lower profit-taking bar
    0: (2,  4,  7, 10),   # Tier 4 — low conviction; exit at lower bar
}

SELL_URGENCY = {
    "⚠️ Consider Full Exit":          4,
    "📉 Take Major Profits (50–75%)": 3,
    "📤 Trim ~50%":                   2,
    "💸 Take Partial Profits (~25%)": 1,
    "✅ Hold":                        0,
}

def compute_sell_signal(pnl_pct, price_vs_ath_pct, fg_value, price_change_30d,
                        rsi, tier_score, coin_alloc_pct=None):
    """
    Determines when and how much to sell. Separate from compute_signal so that
    a coin can simultaneously be a good BUY relative to its last dip and still
    have profit-taking signals from a prior run-up.

    Score signals (additive):
      P&L ≥ 200%           = +3  |  ≥ 100% = +2  |  ≥ 50% = +1
      ATH ≥ −10%           = +3  |  ≥ −20% = +2  |  ≥ −30% = +1
      F&G > 75             = +2  |  > 60   = +1
      RSI > 70             = +1
      30d ≥ +50%           = +2  |  ≥ +30% = +1
      Concentration ≥ 40%  = +2  |  ≥ 30%  = +1
      Tier 4, P&L > 20%    = +2  (low conviction — take profits sooner)
      Tier 3, P&L > 20%    = +1  (conditional — lower bar than core holdings)

    Thresholds are tier-adjusted so blue chips only flag at peaks while
    speculative coins flag much earlier.
    """
    score   = 0
    reasons = []

    # ── Personal P&L ──────────────────────────────────────────────────────────
    if pnl_pct is not None and pnl_pct > 0:
        if   pnl_pct >= 200: score += 3; reasons.append(f"Up {pnl_pct:.0f}% on your buy price — major gains, time to de-risk")
        elif pnl_pct >= 100: score += 2; reasons.append(f"Up {pnl_pct:.0f}% on your buy price — large gains, take some off the table")
        elif pnl_pct >=  50: score += 1; reasons.append(f"Up {pnl_pct:.0f}% on your buy price — solid gains, consider partial profit")

    # ── ATH proximity ─────────────────────────────────────────────────────────
    if price_vs_ath_pct is not None:
        if   price_vs_ath_pct >= -10: score += 3; reasons.append(f"Only {abs(price_vs_ath_pct):.0f}% below ATH — near historical peak, risk/reward is poor")
        elif price_vs_ath_pct >= -20: score += 2; reasons.append(f"{abs(price_vs_ath_pct):.0f}% below ATH — approaching historical peak zone")
        elif price_vs_ath_pct >= -30: score += 1; reasons.append(f"{abs(price_vs_ath_pct):.0f}% below ATH — elevated, in upper range")

    # ── Market sentiment ──────────────────────────────────────────────────────
    if fg_value is not None:
        if   fg_value > 75: score += 2; reasons.append(f"Fear & Greed {fg_value} — Extreme Greed, market euphoric")
        elif fg_value > 60: score += 1; reasons.append(f"Fear & Greed {fg_value} — Greed, market overheated")

    # ── Short-term momentum ───────────────────────────────────────────────────
    if rsi is not None and rsi > 70:
        score += 1; reasons.append(f"RSI {rsi} — overbought short-term")

    if price_change_30d is not None:
        if   price_change_30d >= 50: score += 2; reasons.append(f"+{price_change_30d:.0f}% in 30 days — parabolic move, often mean-reverts")
        elif price_change_30d >= 30: score += 1; reasons.append(f"+{price_change_30d:.0f}% in 30 days — strong run, consider taking some off")

    # ── Portfolio concentration ───────────────────────────────────────────────
    if coin_alloc_pct is not None:
        if   coin_alloc_pct >= 40: score += 2; reasons.append(f"{coin_alloc_pct:.0f}% of your portfolio — dangerously concentrated, trim to rebalance")
        elif coin_alloc_pct >= 30: score += 1; reasons.append(f"{coin_alloc_pct:.0f}% of your portfolio — concentrated, consider trimming")

    # ── Tier-based threshold adjustment ──────────────────────────────────────
    # Low-conviction coins should be trimmed sooner once profitable
    if pnl_pct is not None and pnl_pct > 20:
        if   tier_score == 0: score += 2; reasons.append("Tier 4 (Low Conviction) — low-thesis coin in profit; take gains at lower bar than quality holdings")
        elif tier_score == 1: score += 1; reasons.append("Tier 3 (Conditional) — lower profit-taking threshold than core holdings")

    # ── Determine action ──────────────────────────────────────────────────────
    t25, t50, tmajor, tfull = SELL_THRESHOLDS.get(tier_score, SELL_THRESHOLDS[0])

    if   score >= tfull:  action = "⚠️ Consider Full Exit";          sell_pct = "100%"
    elif score >= tmajor: action = "📉 Take Major Profits (50–75%)"; sell_pct = "50–75%"
    elif score >= t50:    action = "📤 Trim ~50%";                    sell_pct = "~50%"
    elif score >= t25:    action = "💸 Take Partial Profits (~25%)";  sell_pct = "~25%"
    else:                 action = "✅ Hold";                          sell_pct = "0%"

    return action, sell_pct, reasons, score


# ── Pre-compute all coin metrics ──────────────────────────────────────────────

# Pass 1: compute raw coin values for portfolio composition signals
_raw_values = {
    cid: info["qty"] * market.get(cid, {}).get("current_price", 0)
    for cid, info in st.session_state.holdings.items()
}
_total_portfolio = sum(_raw_values.values()) or 1  # guard against empty portfolio

# Speculative combined allocation — Tier 3 (score=1) + Tier 4 (score=0) coins
# Used to penalise over-concentration in conditional/low-conviction holdings
_speculative_value = sum(
    v for cid, v in _raw_values.items()
    if FUNDAMENTAL_TIERS.get(cid, {}).get("tier_score", 3) <= 1  # 3 is default (safe fallback)
)
_speculative_alloc_pct = (_speculative_value / _total_portfolio * 100) if _total_portfolio else 0

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

    # Per-coin allocation % for portfolio composition signals
    coin_alloc_pct = (_raw_values.get(cid, 0) / _total_portfolio * 100) if _total_portfolio else 0

    signal, reasons, score = compute_signal(
        rsi, fg_value, ath_pct, ch30, pnl_pct, mcap, vol_mcap,
        tier_score=tier_score, tier_reason=tier_reason,
        coin_alloc_pct=coin_alloc_pct, speculative_alloc_pct=_speculative_alloc_pct
    )
    sell_action, sell_pct, sell_reasons, sell_score = compute_sell_signal(
        pnl_pct, ath_pct, fg_value, ch30, rsi, tier_score,
        coin_alloc_pct=coin_alloc_pct
    )
    coin_metrics[cid] = dict(
        info=info, md=md, cp=cp, ath=ath, mcap=mcap,
        vol_mcap=vol_mcap, ath_pct=ath_pct, ch30=ch30,
        pnl_pct=pnl_pct, rsi=rsi, signal=signal, reasons=reasons, score=score,
        value=info["qty"] * cp,
        tier_info=tier_info, tier_label=tier_label, tier_score=tier_score,
        sell_action=sell_action, sell_pct=sell_pct,
        sell_reasons=sell_reasons, sell_score=sell_score,
        coin_alloc_pct=coin_alloc_pct,
    )

tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🎯 Analysis", "💼 Portfolio", "🚦 Signals", "📊 Fundamentals", "👀 Watchlist", "📤 Exit Strategy"]
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
        f"""<div style="background:{bg};border-radius:12px;padding:22px 28px;margin-bottom:20px">
        <div style="font-size:1.9rem;font-weight:800;color:#ffffff;letter-spacing:-0.5px">
            {port_color} Portfolio Verdict: {port_label}
        </div>
        <div style="color:#cccccc;margin-top:8px;font-size:0.95rem;line-height:1.5">
            Average signal score: <b style="color:#fff">{avg_score:+.1f}</b>
            across <b style="color:#fff">{len(scores)} coins</b>
            &nbsp;&nbsp;·&nbsp;&nbsp;
            {fg_sent_html}
        </div></div>""",
        unsafe_allow_html=True
    )

    # ── KPI row — 4 columns, F&G gets extra width ─────────────────────────
    k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
    k1.metric("🟢  Buy / Strong Buy", buys,      help="Score ≥ 2")
    k2.metric("🟡  Hold",             holds,     help="Score 0 – 1")
    k3.metric("🟠  Caution",          cautions,  help="Score −1 to −3")
    k4.metric("🔴  Consider Selling", sell_warn, help="Score below −3")

    # Fear & Greed as a styled info box — avoids truncation entirely
    if fg_value is not None:
        fg_bar_pct = fg_value          # 0–100
        fg_color_hex = (
            "#2d6a2d" if fg_value < 25 else
            "#4a7a2d" if fg_value < 40 else
            "#7a7a2d" if fg_value < 60 else
            "#7a4a1a" if fg_value < 75 else
            "#7a1a1a"
        )
        fg_icon = "😨" if fg_value < 25 else "😟" if fg_value < 40 else "😐" if fg_value < 60 else "😏" if fg_value < 75 else "🤑"
        st.markdown(
            f"""<div style="background:{fg_color_hex};border-radius:10px;padding:14px 20px;
                            display:flex;align-items:center;gap:16px;margin-top:8px">
                <div style="font-size:2.2rem">{fg_icon}</div>
                <div>
                    <div style="color:#aaa;font-size:0.78rem;font-weight:600;
                                letter-spacing:0.08em;text-transform:uppercase">Fear &amp; Greed Index</div>
                    <div style="font-size:1.6rem;font-weight:800;color:#fff">
                        {fg_value} <span style="font-size:1rem;font-weight:400;color:#ddd">— {fg_label}</span>
                    </div>
                    <div style="background:rgba(255,255,255,0.15);border-radius:4px;height:6px;
                                margin-top:6px;width:100%">
                        <div style="background:#fff;border-radius:4px;height:6px;
                                    width:{fg_bar_pct}%"></div>
                    </div>
                    <div style="color:#bbb;font-size:0.8rem;margin-top:4px">0 = Extreme Fear &nbsp;·&nbsp; 100 = Extreme Greed</div>
                </div>
            </div>""",
            unsafe_allow_html=True
        )

    st.divider()

    # ── Per-coin rating table ──────────────────────────────────────────────
    st.subheader("Per-Coin Rating")
    rows_a = []
    for cid, m in coin_metrics.items():
        rows_a.append({
            "Coin":     f"{m['info']['name']} ({m['info']['symbol']})",
            "Rating":   m["signal"],
            "Score":    fmt_score(m["score"]),
            "Price":    fmt_price(m["cp"]),
            "P&L %":    f"{m['pnl_pct']:+.1f}%" if m["pnl_pct"] is not None else "—",
            "From ATH": f"{m['ath_pct']:.0f}%" if m["ath_pct"] else "—",
            "30d %":    f"{m['ch30']:+.1f}%" if m["ch30"] else "—",
            "RSI":      f"{m['rsi']}" if m["rsi"] else "—",
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

    if fg_value is not None:
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

    if fg_value is not None:
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
| **Qual. Tier** | Tier 1–2 = strong thesis, accumulate | Tier 4 = weak thesis, be selective |
| **Market Cap** | >$10B (large cap = stable) | <$100M (micro cap = risky) |
| **Vol/MCap %** | >3% (active, liquid) | <0.5% (illiquid, hard to exit) |
| **From ATH** | −50% to −80% (historically cheap) | Near 0% (near peak) |
| **7d / 30d %** | Moderate positive | Extreme >50% (FOMO) or deep negative |
| **RSI** | 30–50 (healthy zone) | <20 or >80 (extremes) |

**Investment tier scoring:** Tier 1 = +3 pts · Tier 2 = +2 pts · Tier 3 = +1 pt · Tier 4 = 0 pts

The model assesses each coin's investment merit — Tier 4 coins receive **no fundamental credit** and must earn a Buy purely through price signals. Read each coin's **Investment Verdict** below for the model's honest opinion on whether the coin merits a position at all.
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
    st.subheader("🏛️ Coin Profiles — Model's Investment Assessment")
    st.caption("Expand each coin to see the model's investment verdict, use case, strengths, and risks. The verdict is the model's honest opinion — read it before deciding whether to add to a position.")

    tier_colors  = {"Tier 1": "#1a3a1a", "Tier 2": "#1a2a3a", "Tier 3": "#2e2a1a", "Tier 4": "#3a1a1a"}
    tier_badges  = {"Tier 1": "🟢", "Tier 2": "🔵", "Tier 3": "🟡", "Tier 4": "🔴"}
    verdict_colors = {"Tier 1": "#1a3a1a", "Tier 2": "#1a2a3a", "Tier 3": "#2e2316", "Tier 4": "#3a1a1a"}
    verdict_borders = {"Tier 1": "#2d7a2d", "Tier 2": "#2d5fa0", "Tier 3": "#a07a2d", "Tier 4": "#a03030"}

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
            # Investment verdict — the model's honest opinion
            vbg  = verdict_colors.get(tier_key, "#1a1a1a")
            vbdr = verdict_borders.get(tier_key, "#555")
            verdict_text = tf.get("fundamental_verdict", "No assessment available for this coin.")
            st.markdown(
                f"<div style='background:{vbg};border-left:4px solid {vbdr};"
                f"border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:12px'>"
                f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:4px;letter-spacing:0.05em'>MODEL VERDICT</div>"
                f"<div style='font-size:0.92rem;line-height:1.5'>{verdict_text}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Use case
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

            score_str = f"+{tf['tier_score']}" if tf['tier_score'] > 0 else str(tf['tier_score'])
            note = "no fundamental credit added — must earn Buy on price signals alone" if tf['tier_score'] == 0 else f"adds {score_str} pts to this coin's signal score"
            st.caption(f"Signal contribution: **{tf['tier_label']}** — {note}.")

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

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: EXIT STRATEGY
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.header("📤 Exit Strategy")
    st.caption(
        "When to sell, how much, and why — based on your personal P&L, current price vs ATH, "
        "market sentiment, and each coin's investment tier. Tier 4 coins (low conviction) are trimmed "
        "at lower thresholds than blue chips. Read the reasons before acting."
    )

    # ── Global market context banner ──────────────────────────────────────────
    if fg_value is not None:
        if fg_value > 75:
            st.warning(
                f"⚠️ **Market-wide caution:** Fear & Greed is {fg_value} (Extreme Greed). "
                "Historically, extreme greed precedes corrections. Consider reducing across the board, "
                "starting with lowest-conviction holdings.",
                icon="🔴"
            )
        elif fg_value > 60:
            st.info(
                f"📊 Fear & Greed is {fg_value} (Greed). Market is running hot — favour taking "
                "partial profits on anything near ATH or significantly in the green.",
                icon="🟡"
            )
        elif fg_value < 25:
            st.success(
                f"📊 Fear & Greed is {fg_value} (Extreme Fear). Market is oversold — this is "
                "generally not the time to sell. Hold or accumulate unless you need liquidity.",
                icon="🟢"
            )

    # ── Sort coins by sell urgency (most urgent first) ─────────────────────────
    sorted_coins = sorted(
        coin_metrics.items(),
        key=lambda kv: SELL_URGENCY.get(kv[1]["sell_action"], 0),
        reverse=True
    )

    # ── Summary KPI row ────────────────────────────────────────────────────────
    urgency_counts = {"exit": 0, "major": 0, "trim": 0, "hold": 0}
    for _, m in sorted_coins:
        u = SELL_URGENCY.get(m["sell_action"], 0)
        if   u >= 4: urgency_counts["exit"]  += 1
        elif u >= 3: urgency_counts["major"] += 1
        elif u >= 1: urgency_counts["trim"]  += 1
        else:        urgency_counts["hold"]  += 1

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("✅ Hold",               urgency_counts["hold"],  help="No sell signals — no action needed")
    k2.metric("💸 Take Profits / Trim", urgency_counts["trim"],  help="Partial profit-taking recommended")
    k3.metric("📉 Major Profits",       urgency_counts["major"], help="Significant sell signal — 50–75%")
    k4.metric("⚠️ Exit Signal",         urgency_counts["exit"],  help="Strong signal to fully exit position")

    st.divider()

    # ── Per-coin sell recommendation expanders ─────────────────────────────────
    action_colors = {
        "⚠️ Consider Full Exit":          "#3a1a1a",
        "📉 Take Major Profits (50–75%)": "#2e1a1a",
        "📤 Trim ~50%":                   "#2e2316",
        "💸 Take Partial Profits (~25%)": "#1a2316",
        "✅ Hold":                        "#1a1a2e",
    }
    action_borders = {
        "⚠️ Consider Full Exit":          "#cc3333",
        "📉 Take Major Profits (50–75%)": "#cc5533",
        "📤 Trim ~50%":                   "#cc9933",
        "💸 Take Partial Profits (~25%)": "#55aa55",
        "✅ Hold":                        "#3355aa",
    }

    for cid, m in sorted_coins:
        info       = m["info"]
        sell_act   = m["sell_action"]
        sell_pct   = m["sell_pct"]
        sell_rsns  = m["sell_reasons"]
        sell_sc    = m["sell_score"]
        pnl        = m["pnl_pct"]
        alloc      = m["coin_alloc_pct"]
        tier_lbl   = m["tier_label"]

        pnl_str   = f"{pnl:+.1f}%" if pnl is not None else "—"
        alloc_str = f"{alloc:.1f}%" if alloc is not None else "—"

        abg  = action_colors.get(sell_act,  "#1a1a1a")
        abdr = action_borders.get(sell_act, "#555")

        sell_summary = "No action" if sell_act == "✅ Hold" else f"Sell {sell_pct}"
        with st.expander(
            f"{info['name']} ({info['symbol']}) — {sell_act}  ·  {sell_summary}",
            expanded=(sell_sc >= 3)   # auto-expand urgent coins
        ):
            # Action banner
            st.markdown(
                f"<div style='background:{abg};border-left:4px solid {abdr};"
                f"border-radius:0 8px 8px 0;padding:12px 16px;margin-bottom:12px'>"
                f"<div style='font-size:0.75rem;color:#aaa;margin-bottom:4px;letter-spacing:0.05em'>RECOMMENDATION</div>"
                f"<div style='font-size:1.05rem;font-weight:600'>{sell_act}</div>"
                f"<div style='font-size:0.88rem;margin-top:4px'>Suggested sell: <b>{sell_pct}</b> of your position</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Context metrics
            cx1, cx2, cx3, cx4 = st.columns(4)
            cx1.metric("Your P&L",       pnl_str)
            cx2.metric("Portfolio %",    alloc_str)
            cx3.metric("Tier",           tier_lbl.split("—")[0].strip())
            cx4.metric("Sell Score",     sell_sc)

            # Reasons
            if sell_rsns:
                st.markdown("**Why:**")
                for r in sell_rsns:
                    st.markdown(f"- {r}")
            else:
                st.markdown("_No sell signals at this time. Price, sentiment, and gains are all within normal range._")

            # Guidance note for "Hold" coins
            if sell_sc == 0:
                st.caption(
                    "Nothing to act on right now. Check back when: price approaches ATH, "
                    "Fear & Greed enters Greed/Extreme Greed, or your P&L exceeds 50%+."
                )

    # ── What to watch for ─────────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 General exit rules — when to revisit this tab", expanded=False):
        st.markdown("""
**Trigger conditions to check Exit Strategy immediately:**

| Signal | Threshold | Action |
|--------|-----------|--------|
| Fear & Greed | > 75 (Extreme Greed) | Review all positions, start trimming weakest |
| Any coin from ATH | Within 15% | Check if P&L > 50% — take partial profits |
| Single coin P&L | > 100% | Always take at least 25% off the table |
| Tier 4 coin P&L | > 30% | Take profits — low conviction, don't let gains evaporate |
| Single coin allocation | > 35% of portfolio | Trim regardless of market conditions |
| Fundamental change | Tier downgrade or thesis breaks | Exit immediately, not gradually |

**Blue chip rule (BTC, ETH):** Never sell your entire position. These are core holds — sell 25–50% at peaks to redeploy at the next dip, but always keep a base position.

**Tier 4 rule (TAO):** If the coin is profitable and the fundamental thesis has not strengthened in 6 months, reduce position. Holding a speculative coin with a weakening thesis is a trap.
""")


st.divider()
st.caption(
    f"Data: CoinGecko (free) · Alternative.me · "
    f"Prices refresh every 10 min · RSI every 2 hrs · Fear & Greed every 1 hr · "
    f"Last loaded: {datetime.now().strftime('%H:%M:%S')}"
)
