"""
P&L Dashboard — Streamlit
Data source: Public Google Sheet (no credentials needed)

Sheet layout:
  LEFT BLOCK  (cols A-H): Vertical | Month | Cost | Net sales | GST | Gross sales | GP | Expense
              Rows: Retail (Jan-Dec), BD (Jan-Dec), Online (Jan-Dec)

  MIDDLE BLOCK (cols J-K): Month | Expense Others G&A AND MARKETING

  RIGHT BLOCK  (cols M-R): Month | Sales Person | SUM of Total Cost | SUM of GROSS_AMOUNT |
                            SUM of Tax Amount | SUM of NET_AMOUNT
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="P&L Dashboard", page_icon="📊", layout="wide")

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 12px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: 600; color: #FFFFFF !important; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; color: rgba(255,255,255,0.6) !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricDelta"] svg { display: none; }
[data-testid="stMetricDelta"] > div { color: #4ADE80 !important; font-size: 0.82rem; }
section[data-testid="stSidebar"] { background: rgba(255,255,255,0.04); border-right: 1px solid rgba(255,255,255,0.1); }
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
#MainMenu { visibility: hidden; } footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
COLORS       = {"Retail": "#34D399", "BD": "#60A5FA", "Online": "#FBBF24"}
MONTHS_ORDER = ["Jan_26","Feb_26","Mar_26","Apr_26","May_26","June_26",
                "Jul_26","Aug_26","Sept_26","Oct_26","Nov_26","Dec_26"]
LABEL_COLOR  = "#FFFFFF"
AXIS_COLOR   = "rgba(255,255,255,0.5)"
GRID_COLOR   = "rgba(255,255,255,0.08)"
PAPER_BG     = "rgba(0,0,0,0)"
PLOT_BG      = "rgba(255,255,255,0.03)"
FONT_FAMILY  = "Inter, sans-serif"

# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_inr(n):
    """Indian number format: 7,23,000"""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "₹0"
    n = int(round(n))
    neg = n < 0
    n = abs(n)
    s = str(n)
    if len(s) <= 3:
        result = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        result = ",".join(reversed(parts)) + "," + last3
    return f"₹{'-' if neg else ''}{result}"

def short_month(m):
    """Jan_26 → Jan"""
    return m.split("_")[0] if "_" in str(m) else str(m)

def base_layout(title="", height=300, margin=None):
    m = margin or dict(l=55, r=25, t=45, b=45)
    return dict(
        title=dict(text=f"<b>{title}</b>",
                   font=dict(size=13, color=LABEL_COLOR, family=FONT_FAMILY),
                   x=0, pad=dict(b=10)),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(family=FONT_FAMILY, color=LABEL_COLOR, size=12),
        height=height, margin=m,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=LABEL_COLOR, size=11), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="rgba(30,30,30,0.95)",
                        font=dict(color="white", size=12),
                        bordercolor="rgba(255,255,255,0.2)"),
    )

def ax_x(extra=None):
    d = dict(gridcolor=GRID_COLOR, showgrid=False, linecolor=GRID_COLOR,
             tickfont=dict(color=AXIS_COLOR, size=11), title_font=dict(color=AXIS_COLOR))
    if extra: d.update(extra)
    return d

def ax_y(extra=None):
    d = dict(gridcolor=GRID_COLOR, linecolor=GRID_COLOR,
             tickfont=dict(color=AXIS_COLOR, size=11), title_font=dict(color=AXIS_COLOR))
    if extra: d.update(extra)
    return d

def sort_months(df, col="month"):
    df = df.copy()
    df["_o"] = df[col].apply(lambda m: MONTHS_ORDER.index(m) if m in MONTHS_ORDER else 99)
    return df.sort_values("_o").drop(columns=["_o"])

# ── Sample Data (matches sheet structure) ─────────────────────────────────────
def make_sample():
    months = MONTHS_ORDER
    retail_rows, bd_rows, online_rows = [], [], []
    for mo in months:
        retail_rows.append({"month": mo, "cost": 0, "net_sales": 0, "gst": 0, "gross_sales": 0, "gp": 0, "expense": 0})
        bd_rows.append(    {"month": mo, "cost": 0, "net_sales": 0, "gst": 0, "gross_sales": 0, "gp": 0, "expense": 0})
        online_rows.append({"month": mo, "cost": 0, "net_sales": 0, "gst": 0, "gross_sales": 0, "gp": 0, "expense": 0})

    # Fill in known Q1 data
    known_retail = [
        {"month":"Jan_26","cost":414223, "net_sales":964027,  "gst":134822,"gross_sales":1098850,"gp":549805, "expense":0},
        {"month":"Feb_26","cost":975722, "net_sales":2116097, "gst":226898,"gross_sales":2342995,"gp":1140375,"expense":0},
        {"month":"Mar_26","cost":1686629,"net_sales":3640154, "gst":371991,"gross_sales":4012145,"gp":1953525,"expense":2466810},
    ]
    known_bd = [
        {"month":"Jan_26","cost":156371,"net_sales":484048,"gst":24202,"gross_sales":508250,"gp":327677,"expense":0},
        {"month":"Feb_26","cost":0,     "net_sales":0,      "gst":0,   "gross_sales":0,     "gp":0,    "expense":0},
        {"month":"Mar_26","cost":85739, "net_sales":173898, "gst":31302,"gross_sales":205200,"gp":88159,"expense":417381},
    ]
    known_online = [
        {"month":"Jan_26","cost":2467, "net_sales":5614, "gst":281, "gross_sales":5895, "gp":3147, "expense":0},
        {"month":"Feb_26","cost":31986,"net_sales":69349,"gst":11201,"gross_sales":80550,"gp":37363,"expense":0},
        {"month":"Mar_26","cost":30957,"net_sales":60000,"gst":3000,"gross_sales":63000,"gp":29043,"expense":28188},
    ]
    known = {"Retail": known_retail, "BD": known_bd, "Online": known_online}
    all_rows = {"Retail": retail_rows, "BD": bd_rows, "Online": online_rows}
    for ch, krows in known.items():
        for kr in krows:
            for row in all_rows[ch]:
                if row["month"] == kr["month"]:
                    row.update(kr)

    # G&A expense by month
    gna_rows = [{"month": mo, "expense_gna": 0} for mo in months]
    gna_rows[2]["expense_gna"] = 3727717  # Mar_26

    # Salesperson data
    sp_rows = [
        {"month":"Mar_26","salesperson":"Sana C",  "cost":933909, "gross_amount":2213445,"tax":193946,"net_amount":2213445},
        {"month":"Mar_26","salesperson":"Bhumi",   "cost":652023, "gross_amount":1554500,"tax":147562,"net_amount":1554500},
        {"month":"Mar_26","salesperson":"Gloria",  "cost":30957,  "gross_amount":63000,  "tax":3000,  "net_amount":63000},
        {"month":"Mar_26","salesperson":"Divesh",  "cost":55617,  "gross_amount":138600, "tax":19159, "net_amount":138600},
        {"month":"Jan_26","salesperson":"Sana C",  "cost":45080,  "gross_amount":105600, "tax":11324, "net_amount":105600},
        {"month":"Jan_26","salesperson":"Bhumi",   "cost":156371, "gross_amount":508250, "tax":24202, "net_amount":508250},
    ]

    return {
        "retail":  pd.DataFrame(all_rows["Retail"]),
        "bd":      pd.DataFrame(all_rows["BD"]),
        "online":  pd.DataFrame(all_rows["Online"]),
        "gna":     pd.DataFrame(gna_rows),
        "salesperson": pd.DataFrame(sp_rows),
    }

SAMPLE = make_sample()

# ── Sheet loader ──────────────────────────────────────────────────────────────
def sheet_url_to_csv(url):
    import re
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("Invalid Google Sheet URL")
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid=0"

def clean_num(series):
    """Strip commas then convert to float. Handles '2,310,202' correctly."""
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce"
    ).fillna(0)

def try_load_sheet(url):
    try:
        raw = pd.read_csv(sheet_url_to_csv(url), header=None, dtype=str)
        raw = raw.fillna("")

        # ── LEFT BLOCK: cols A(0)-H(7) ─────────────────────────────────────
        # Row 0 = header, skip it
        # Cols: Vertical | Month | Cost | Net sales | GST | Gross sales | GP | Expense
        left = raw.iloc[1:, :8].copy()
        left.columns = ["vertical","month","cost","net_sales","gst","gross_sales","gp","expense"]
        left = left[left["vertical"].isin(["Retail","BD","Online"])].copy()
        left["month"] = left["month"].str.strip()
        for c in ["cost","net_sales","gst","gross_sales","gp","expense"]:
            left[c] = clean_num(left[c])

        retail = left[left["vertical"]=="Retail"].drop(columns=["vertical"]).reset_index(drop=True)
        bd     = left[left["vertical"]=="BD"].drop(columns=["vertical"]).reset_index(drop=True)
        online = left[left["vertical"]=="Online"].drop(columns=["vertical"]).reset_index(drop=True)

        # ── MIDDLE BLOCK: cols J(9)-K(10) ──────────────────────────────────
        # Col J = Month, Col K = G&A Expense (comma-formatted numbers)
        mid = raw.iloc[1:, 9:11].copy()
        mid.columns = ["month","expense_gna"]
        mid["month"] = mid["month"].str.strip()
        mid = mid[mid["month"].isin(MONTHS_ORDER)].copy()
        mid["expense_gna"] = clean_num(mid["expense_gna"])
        gna = mid.reset_index(drop=True)

        # ── RIGHT BLOCK: cols M(12)-R(17) ──────────────────────────────────
        # Multiple salesperson blocks stacked vertically (Sana, Bhumi, Gloria, Divesh, Astha, Nitima)
        right = raw.iloc[1:, 12:18].copy()
        right.columns = ["month","salesperson","cost","gross_amount","tax","net_amount"]
        right["month"]       = right["month"].str.strip()
        right["salesperson"] = right["salesperson"].str.strip()
        right = right[
            right["month"].isin(MONTHS_ORDER) &
            (right["salesperson"] != "")
        ].copy()
        for c in ["cost","gross_amount","tax","net_amount"]:
            right[c] = clean_num(right[c])
        # Only rows with actual sales data
        salesperson = right[right["gross_amount"] > 0].reset_index(drop=True)

        return {"retail": retail, "bd": bd, "online": online,
                "gna": gna, "salesperson": salesperson}

    except Exception as e:
        st.warning(f"Could not read sheet: {e}. Showing sample data.")
        return None

@st.cache_data(ttl=300)
def load_data(url):
    if not url:
        return SAMPLE
    return try_load_sheet(url) or SAMPLE

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 P&L Dashboard")
    st.markdown("---")
    st.markdown("#### 🔗 Data source")
    sheet_url = st.text_input("Google Sheet URL", placeholder="Paste public sheet link…",
        help="Share → Anyone with the link → Viewer → Copy link")
    if sheet_url:
        st.success("✅ Sheet connected")
    else:
        st.info("Using sample data")
    st.markdown("---")
    st.markdown("#### 📋 How to connect\n1. Open Google Sheet\n2. **Share** → Anyone with the link → **Viewer**\n3. Copy link & paste above")
    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Load & prep ───────────────────────────────────────────────────────────────
data   = load_data(sheet_url)
retail = data["retail"].copy();  retail["channel"] = "Retail"
bd     = data["bd"].copy();      bd["channel"]     = "BD"
online = data["online"].copy();  online["channel"] = "Online"
all_df = pd.concat([retail, bd, online], ignore_index=True)

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown("## 📊 P&L Dashboard")
cf1, cf2, _ = st.columns([1, 1, 4])
with cf1:
    avail_months = [m for m in MONTHS_ORDER if m in all_df["month"].values]
    sel_months   = st.multiselect("📅 Month", avail_months,
                                  format_func=short_month, placeholder="All months")
with cf2:
    sel_channel = st.multiselect("🏪 Channel", ["Retail","BD","Online"], placeholder="All channels")

filtered = all_df.copy()
if sel_months:  filtered = filtered[filtered["month"].isin(sel_months)]
if sel_channel: filtered = filtered[filtered["channel"].isin(sel_channel)]

# Filter GNA
gna_df = data["gna"].copy()
if sel_months:
    gna_df = gna_df[gna_df["month"].isin(sel_months)]

# Filter salesperson
sp_df = data["salesperson"].copy()
if sel_months:
    sp_df = sp_df[sp_df["month"].isin(sel_months)]

# ── KPIs ──────────────────────────────────────────────────────────────────────
gross        = filtered["gross_sales"].sum()
net          = filtered["net_sales"].sum()
gp           = filtered["gp"].sum()
cost         = filtered["cost"].sum()
gst_sum      = filtered["gst"].sum()
expense_ch   = filtered["expense"].sum()
expense_gna  = gna_df["expense_gna"].sum()
total_expense= expense_ch + expense_gna
gp_pct       = (gp / gross * 100) if gross else 0
net_profit   = gp - total_expense

k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
k1.metric("💰 Gross Sales",   fmt_inr(gross))
k2.metric("🧾 Net Sales",     fmt_inr(net))
k3.metric("📈 Gross Profit",  fmt_inr(gp),           delta=f"GP% {gp_pct:.1f}%")
k4.metric("🏭 Total Cost",    fmt_inr(cost))
k5.metric("🏛️ GST Collected", fmt_inr(gst_sum))
k6.metric("📦 Total Expense", fmt_inr(total_expense))
k7.metric("🎯 Net Profit",    fmt_inr(net_profit))
st.divider()

# ── Row 1: Gross sales bar + GP donut ─────────────────────────────────────────
c1, c2 = st.columns([2, 1])

with c1:
    trend = sort_months(filtered.groupby(["month","channel"])[["gross_sales"]].sum().reset_index())
    trend["month_label"] = trend["month"].apply(short_month)
    fig1  = go.Figure()
    for ch in ["Retail","BD","Online"]:
        d = trend[trend["channel"]==ch]
        if d.empty: continue
        fig1.add_trace(go.Bar(
            name=ch, x=d["month_label"], y=d["gross_sales"],
            marker_color=COLORS[ch], marker_line_width=0,
            text=d["gross_sales"].apply(fmt_inr),
            textposition="outside", textfont=dict(color=LABEL_COLOR, size=10),
            hovertemplate=f"<b>{ch}</b><br>%{{x}}<br>%{{text}}<extra></extra>",
        ))
    fig1.update_layout(**base_layout("Gross Sales by Month", height=320), barmode="group")
    fig1.update_xaxes(**ax_x())
    fig1.update_yaxes(**ax_y())
    st.plotly_chart(fig1, use_container_width=True)

with c2:
    gp_ch = filtered.groupby("channel")["gp"].sum().reset_index()
    gp_ch = gp_ch[gp_ch["gp"] > 0]
    fig2  = go.Figure(go.Pie(
        labels=gp_ch["channel"], values=gp_ch["gp"], hole=0.58,
        marker_colors=[COLORS.get(c,"#888") for c in gp_ch["channel"]],
        textinfo="label+percent", textfont=dict(color=LABEL_COLOR, size=12),
        hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<extra></extra>",
    ))
    fig2.update_layout(
        **base_layout("GP by Channel", height=320), showlegend=False,
        annotations=[dict(text=f"<b>{fmt_inr(gp)}</b><br>Total GP",
                          x=0.5, y=0.5, font=dict(size=12, color=LABEL_COLOR), showarrow=False)]
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── Row 2: Monthly GP% + Funnel ───────────────────────────────────────────────
c3, c4 = st.columns(2)

with c3:
    mo_gp = sort_months(
        filtered.groupby("month").agg(gross=("gross_sales","sum"), gp=("gp","sum")).reset_index()
    )
    mo_gp["gp_pct"]     = (mo_gp["gp"] / mo_gp["gross"] * 100).fillna(0).round(1)
    mo_gp["month_label"] = mo_gp["month"].apply(short_month)
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=mo_gp["month_label"], y=mo_gp["gp_pct"],
        mode="lines+markers+text",
        text=mo_gp["gp_pct"].apply(lambda v: f"<b>{v:.1f}%</b>"),
        textposition="top center", textfont=dict(color=LABEL_COLOR, size=12),
        line=dict(color=COLORS["Retail"], width=2.5),
        marker=dict(size=9, color=COLORS["Retail"], line=dict(color="white", width=2)),
        fill="tozeroy", fillcolor="rgba(52,211,153,0.12)",
        hovertemplate="<b>%{x}</b><br>GP%: %{y:.1f}%<extra></extra>",
    ))
    fig3.update_layout(**base_layout("Monthly GP%", height=280))
    fig3.update_xaxes(**ax_x())
    fig3.update_yaxes(**ax_y(dict(ticksuffix="%")))
    st.plotly_chart(fig3, use_container_width=True)

with c4:
    after_cost = gross - cost
    after_gst  = after_cost - gst_sum
    funnel_y = [
        f"💰 Gross Sales  {fmt_inr(gross)}",
        f"🏭 Cost  {fmt_inr(cost)}",
        f"✅ After Cost  {fmt_inr(after_cost)}",
        f"🏛️ After GST  {fmt_inr(after_gst)}",
        f"📈 Gross Profit  {fmt_inr(gp)}",
    ]
    funnel_x      = [gross, cost, after_cost, after_gst, gp]
    funnel_colors = ["#60A5FA","#F87171","#FBBF24","#FB923C","#34D399"]
    pct = f"{cost/gross*100:.1f}%" if gross else "0%"
    funnel_hover  = [
        f"Total Revenue: {fmt_inr(gross)}",
        f"Total Cost: {fmt_inr(cost)} ({pct} of sales)",
        f"Remaining after cost: {fmt_inr(after_cost)}",
        f"GST deducted: -{fmt_inr(gst_sum)}",
        f"Final GP: {fmt_inr(gp)} ({gp_pct:.1f}%)",
    ]
    fig4 = go.Figure(go.Funnel(
        y=funnel_y, x=funnel_x,
        textposition="inside", textinfo="none",
        customdata=funnel_hover,
        hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
        marker=dict(color=funnel_colors,
                    line=dict(color="rgba(255,255,255,0.1)", width=1)),
        connector=dict(line=dict(color="rgba(255,255,255,0.15)", width=1),
                       fillcolor="rgba(255,255,255,0.03)"),
    ))
    fig4.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=330,
        margin=dict(l=20, r=20, t=15, b=10),
        font=dict(family=FONT_FAMILY, color=LABEL_COLOR, size=12),
        hoverlabel=dict(bgcolor="rgba(30,30,30,0.95)",
                        font=dict(color="white", size=12),
                        bordercolor="rgba(255,255,255,0.2)"),
    )
    fig4.update_yaxes(tickfont=dict(color=LABEL_COLOR, size=11))
    st.markdown("**P&L Flow — Where money goes**")
    st.plotly_chart(fig4, use_container_width=True)

# ── Row 3: Salesperson + Expense breakdown ────────────────────────────────────
c5, c6 = st.columns([2, 1])

with c5:
    if sp_df.empty:
        st.info("No salesperson data for selected filters.")
    else:
        sp_agg = sp_df.groupby("salesperson").agg(
            gross=("gross_amount","sum"), cost=("cost","sum")
        ).reset_index().sort_values("gross")
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(
            x=sp_agg["salesperson"], y=sp_agg["gross"],
            name="Gross Sales", marker_color=COLORS["BD"], marker_line_width=0,
            text=sp_agg["gross"].apply(fmt_inr),
            textposition="outside", textfont=dict(color=LABEL_COLOR, size=10),
            hovertemplate="<b>%{x}</b><br>Gross: %{text}<extra></extra>",
        ))
        fig5.add_trace(go.Bar(
            x=sp_agg["salesperson"], y=sp_agg["cost"],
            name="Cost", marker_color="#F87171", marker_line_width=0,
            text=sp_agg["cost"].apply(fmt_inr),
            textposition="outside", textfont=dict(color=LABEL_COLOR, size=10),
            hovertemplate="<b>%{x}</b><br>Cost: %{text}<extra></extra>",
        ))
        fig5.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=340,
            margin=dict(l=20, r=20, t=15, b=60),
            font=dict(family=FONT_FAMILY, color=LABEL_COLOR, size=12),
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                        font=dict(color=LABEL_COLOR, size=11), bgcolor="rgba(0,0,0,0)"),
            hoverlabel=dict(bgcolor="rgba(30,30,30,0.95)",
                            font=dict(color="white", size=12),
                            bordercolor="rgba(255,255,255,0.2)"),
        )
        fig5.update_xaxes(**ax_x(dict(tickfont=dict(color=LABEL_COLOR, size=11))))
        fig5.update_yaxes(**ax_y())
        st.markdown("**Salesperson — Gross Sales vs Cost**")
        st.plotly_chart(fig5, use_container_width=True)

with c6:
    # Expense breakdown: channel-wise + G&A
    exp_ch  = filtered.groupby("channel")["expense"].sum().reset_index()
    exp_ch  = exp_ch[exp_ch["expense"] > 0].rename(columns={"channel":"label","expense":"amount"})
    gna_val = gna_df["expense_gna"].sum()
    if gna_val > 0:
        gna_row = pd.DataFrame([{"label":"G&A & Marketing","amount": gna_val}])
        exp_all = pd.concat([exp_ch, gna_row], ignore_index=True)
    else:
        exp_all = exp_ch

    if exp_all.empty:
        st.info("No expense data for selected filters.")
    else:
        fig6 = go.Figure(go.Bar(
            x=exp_all["label"], y=exp_all["amount"],
            marker_color=["#F87171","#FB923C","#C084FC","#E879F9"][:len(exp_all)],
            marker_line_width=0,
            text=exp_all["amount"].apply(fmt_inr),
            textposition="outside", textfont=dict(color=LABEL_COLOR, size=11),
            hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
        ))
        fig6.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, height=340,
            margin=dict(l=20, r=20, t=15, b=60),
            font=dict(family=FONT_FAMILY, color=LABEL_COLOR, size=12),
            hoverlabel=dict(bgcolor="rgba(30,30,30,0.95)",
                            font=dict(color="white", size=12),
                            bordercolor="rgba(255,255,255,0.2)"),
        )
        fig6.update_xaxes(**ax_x(dict(tickfont=dict(color=LABEL_COLOR, size=11))))
        fig6.update_yaxes(**ax_y())
        st.markdown("**Expense Breakdown**")
        st.plotly_chart(fig6, use_container_width=True)

st.divider()

# ── Detail table ──────────────────────────────────────────────────────────────
st.markdown("#### 📋 Channel Detail")
tbl = filtered.groupby(["channel","month"]).agg(
    Cost=("cost","sum"), Net_Sales=("net_sales","sum"),
    GST=("gst","sum"), Gross_Sales=("gross_sales","sum"),
    GP=("gp","sum"), Expense=("expense","sum"),
).reset_index()
tbl["GP%"]       = (tbl["GP"] / tbl["Gross_Sales"] * 100).round(1).astype(str) + "%"
tbl["Net Profit"]= tbl["GP"] - tbl["Expense"]
tbl["Month_label"]= tbl["month"].apply(short_month)
tbl["_o"]        = tbl["month"].apply(lambda m: MONTHS_ORDER.index(m) if m in MONTHS_ORDER else 99)
tbl = tbl.sort_values(["channel","_o"]).drop(columns=["_o","month"])
for col in ["Cost","Net_Sales","GST","Gross_Sales","GP","Expense","Net Profit"]:
    tbl[col] = tbl[col].apply(fmt_inr)
tbl = tbl.rename(columns={
    "channel":"Channel","Month_label":"Month",
    "Net_Sales":"Net Sales","Gross_Sales":"Gross Sales"
})
st.dataframe(tbl, use_container_width=True, hide_index=True)

# ── Salesperson detail table ───────────────────────────────────────────────────
if not sp_df.empty:
    st.markdown("#### 👤 Salesperson Detail")
    sp_tbl = sp_df.groupby(["salesperson","month"]).agg(
        Cost=("cost","sum"),
        Gross_Amount=("gross_amount","sum"),
        Tax=("tax","sum"),
        Net_Amount=("net_amount","sum"),
    ).reset_index()
    sp_tbl["_o"] = sp_tbl["month"].apply(lambda m: MONTHS_ORDER.index(m) if m in MONTHS_ORDER else 99)
    sp_tbl = sp_tbl.sort_values(["salesperson","_o"]).drop(columns=["_o"])
    sp_tbl["month"] = sp_tbl["month"].apply(short_month)
    for col in ["Cost","Gross_Amount","Tax","Net_Amount"]:
        sp_tbl[col] = sp_tbl[col].apply(fmt_inr)
    sp_tbl = sp_tbl.rename(columns={
        "salesperson":"Salesperson","month":"Month",
        "Gross_Amount":"Gross Amount","Net_Amount":"Net Amount"
    })
    st.dataframe(sp_tbl, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("🔄 Data refreshes every 5 min · Built with Streamlit + Plotly")