from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go   

import report_engine as eng
from quant_modules import render_scanner, render_stability, render_pca

st.set_page_config(page_title="Neutrino Fixed Income", page_icon="📈", layout="wide")

st.markdown(
    """
<style>
/* NEUTRINO Light | solamente estilos; motores y fórmulas intactos */
:root { color-scheme: light; }
.stApp {background:#f5f8fc;color:#162a40;font-family:Inter,Arial,sans-serif}
[data-testid="stSidebar"] {background:#eef4fa;border-right:1px solid #dce5ef}
[data-testid="stHeader"] {background:#f5f8fc}
[data-testid="stToolbar"] {background:transparent}
h1,h2,h3,h4,p,label {color:#19324b}
h1 {font-size:2.15rem!important;letter-spacing:-.035em;font-weight:800!important}
h2,h3 {font-weight:750!important}
.small-note {color:#65788c;font-size:.85rem}
div[data-testid="stMetric"] {background:#fff;border:1px solid #dfe8f2;padding:14px;border-radius:13px;box-shadow:0 2px 8px #19324b08}
div[data-testid="stMetricLabel"] {color:#62758a}
div[data-testid="stMetricValue"] {color:#113f61;font-weight:750}
[data-testid="stTabs"] button[role="tab"] {color:#546b83;font-weight:650}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {color:#087d81;border-bottom-color:#087d81}
[data-testid="stDataFrame"] {background:#fff;border:1px solid #e1e8f0;border-radius:10px}
[data-testid="stExpander"] {background:#fff;border:1px solid #dfe7f0;border-radius:10px}
[data-testid="stSelectbox"], [data-testid="stNumberInput"] {color:#19324b}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {background:#087d81;border-color:#087d81;color:white;border-radius:9px}
.stButton>button, .stDownloadButton>button {border-radius:9px}
hr {border-color:#dfe8f2}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def load_ds(path: str, name: str):
    return eng.load_dataset(path, name)


def heatmap_figure(matrix, title, decimals=2, historical_ratio=None):
    """Triángulo inferior: valor numérico original, color por historia de CADA par.

    El gradiente se calcula en report_engine.compute_spread_matrices sobre la
    historia coincidente de las dos emisiones, nunca respecto de las demás celdas.
    """
    values = matrix.astype(float).copy()
    ratios = historical_ratio.astype(float).reindex_like(values) if historical_ratio is not None else values.copy() * np.nan
    for i in range(len(values)):
        for j in range(len(values.columns)):
            if j >= i:
                values.iat[i, j] = np.nan
                ratios.iat[i, j] = np.nan

    labels = np.empty(values.shape, dtype=object)
    hover = np.empty(values.shape, dtype=object)
    for i, r in enumerate(values.index):
        for j, c in enumerate(values.columns):
            v = values.iat[i, j]
            p = ratios.iat[i, j]
            labels[i, j] = (f"{v:+.{decimals}f}" if np.isfinite(v) else "")
            hover[i, j] = (f"{r} - {c}<br>Valor: {v:+.{decimals}f}<br>Posición relativa histórica: {p*100:.1f}%"
                          if np.isfinite(v) and np.isfinite(p) else "")
    fig = go.Figure(go.Heatmap(
        z=ratios.to_numpy(), x=list(values.columns), y=list(values.index),
        zmin=0, zmax=1, colorscale=[[0, '#bc3049'], [.25, '#ed9567'], [.50, '#ffe1a1'], [.75, '#84cfa1'], [1, '#087c56']],
        text=labels, texttemplate='%{text}', textfont=dict(size=10, color='#142c3d'),
        customdata=hover, hovertemplate='%{customdata}<extra></extra>',
        colorbar=dict(title='Histórico', tickvals=[0,.25,.5,.75,1], ticktext=['Mín.','25%','50%','75%','Máx.'])
    ))
    fig.update_layout(
        title=title, template='plotly_white',
        height=max(520, len(values)*29),
        xaxis=dict(side='top', tickangle=-55, showgrid=False),
        yaxis=dict(autorange='reversed', showgrid=False),
        margin=dict(l=60, r=20, t=95, b=40),
        plot_bgcolor='#ffffff', paper_bgcolor='#ffffff',
    )
    return fig

def pair_figure(hist: pd.DataFrame, s1: str, s2: str):
    vals = hist["Diferencia"]
    mu = vals.mean()
    sd = vals.std()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["Fecha"], y=vals, mode="lines", name="Spread"))
    fig.add_hline(y=mu, line_dash="dash", annotation_text=f"Media {mu:,.2f}")
    if np.isfinite(sd) and sd > 0:
        fig.add_hrect(y0=mu-sd, y1=mu+sd, opacity=.12, line_width=0, annotation_text="±1σ")
        fig.add_hline(y=mu+2*sd, line_dash="dot")
        fig.add_hline(y=mu-2*sd, line_dash="dot")
    fig.update_layout(
        title=f"Histórico: {s1} - {s2}",
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#263b50",
        height=460, hovermode="x unified"
    )
    return fig



def histogram_figure(hist: pd.DataFrame, s1: str, s2: str):
    vals = hist["Diferencia"].dropna()
    mu = vals.mean()
    sd = vals.std()
    last = vals.iloc[-1] if not vals.empty else np.nan

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=vals,
            nbinsx=30,
            histnorm="probability density",
            name="Distribución",
            opacity=0.75,
        )
    )

    if np.isfinite(mu):
        fig.add_vline(x=mu, line_dash="dash", annotation_text=f"Media {mu:,.2f}")
    if np.isfinite(sd) and sd > 0:
        fig.add_vrect(x0=mu - sd, x1=mu + sd, opacity=0.10, line_width=0, annotation_text="±1σ")
        fig.add_vline(x=mu + 2 * sd, line_dash="dot")
        fig.add_vline(x=mu - 2 * sd, line_dash="dot")
    if np.isfinite(last):
        fig.add_vline(x=last, line_dash="dash", annotation_text=f"Último {last:,.2f}")

    fig.update_layout(
        title=f"Histograma: {s1} - {s2}",
        xaxis_title="Spread",
        yaxis_title="Densidad",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=460,
        bargap=0.05,
    )
    return fig

def curve_figure(curve: pd.DataFrame, days: int):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["TENOR"], y=curve["ACTUAL"], mode="lines+markers", name="Actual", text=curve["SERIE"]))
    if curve["HACE_30D"].notna().any():
        fig.add_trace(go.Scatter(x=curve["TENOR"], y=curve["HACE_30D"], mode="lines+markers", name=f"Hace {days} días", text=curve["SERIE"]))
    fig.update_traces(hovertemplate="%{text}<br>Tenor %{x:,.2f}a<br>Tasa %{y:,.2f}%<extra></extra>")
    fig.update_layout(title="Curva de rendimiento", xaxis_title="Tenor (años)", yaxis_title="Rendimiento (%)",
                      paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#263b50", height=480)
    return fig




def curve_change_figure(curve: pd.DataFrame, days: int):
    """Visualización adicional: cambio de rendimiento (actual - previo) en pb."""
    data = curve.copy()
    data["ACTUAL"] = pd.to_numeric(data["ACTUAL"], errors="coerce")
    data["HACE_30D"] = pd.to_numeric(data["HACE_30D"], errors="coerce")
    data["TENOR"] = pd.to_numeric(data["TENOR"], errors="coerce")
    data = data.dropna(subset=["TENOR", "ACTUAL", "HACE_30D"]).sort_values("TENOR")
    if data.empty:
        return None, data
    # El motor proporciona rendimientos en porcentaje (p.ej. 7.33).
    data["CAMBIO_PB"] = (data["ACTUAL"] - data["HACE_30D"]) * 100.0
    colors = np.where(data["CAMBIO_PB"] > 0, "#e65359",
                      np.where(data["CAMBIO_PB"] < 0, "#159c79", "#8999aa"))
    fig = go.Figure(go.Bar(
        x=data["TENOR"].map(lambda v: f"{v:.2f}"),
        y=data["CAMBIO_PB"],
        marker_color=colors,
        text=data["CAMBIO_PB"].map(lambda v: f"{v:+.1f}"),
        textposition="outside",
        customdata=data[["SERIE", "ACTUAL", "HACE_30D"]].to_numpy(),
        hovertemplate=("Emisión: %{customdata[0]}<br>Tenor: %{x} años<br>"
                       "Actual: %{customdata[1]:.4f}%<br>"
                       "Anterior: %{customdata[2]:.4f}%<br>"
                       "Cambio: %{y:+.2f} pb<extra></extra>"),
        cliponaxis=False,
    ))
    fig.add_hline(y=0, line_color="#8092a5", line_width=1)
    fig.update_layout(
        title=f"Variación de la curva vs hace {days} días",
        xaxis_title="Tenor (años)", yaxis_title="Cambio (pb)",
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#263b50",
        height=375, margin=dict(l=55, r=25, t=60, b=60), showlegend=False,
        bargap=0.30, uniformtext_minsize=9,
    )
    fig.update_yaxes(zeroline=False, gridcolor="#e5ebf2")
    return fig, data


def show_curve_change_summary(curve: pd.DataFrame, days: int, key: str):
    """Solo interfaz del Resumen, sin modificar el motor ni otras pestañas."""
    fig, valid = curve_change_figure(curve, days)
    if fig is None:
        st.info("No hay cotizaciones comparables para calcular la variación de la curva.")
        return
    st.plotly_chart(fig, use_container_width=True, key=f"{key}_change_bars")
    with st.expander("Ver detalle de cambios por emisión (pb)", expanded=False):
        detail = valid[["SERIE", "TENOR", "ACTUAL", "HACE_30D", "CAMBIO_PB"]].rename(
            columns={"SERIE": "Emisión", "TENOR": "Tenor (años)",
                     "ACTUAL": "Actual (%)", "HACE_30D": f"Hace {days} días (%)",
                     "CAMBIO_PB": "Cambio (pb)"})
        st.dataframe(detail.style.format({"Tenor (años)": "{:.2f}",
                                          "Actual (%)": "{:.4f}",
                                          f"Hace {days} días (%)": "{:.4f}",
                                          "Cambio (pb)": "{:+.2f}"}),
                     use_container_width=True, hide_index=True)



def render_yield_history(dataset, asof, key_prefix: str, market_label: str):
    """Gráfico histórico aislado: no altera el pivot, los motores ni otros módulos."""
    st.subheader(f"Histórico de rendimientos · {market_label}")
    st.caption("Compara varias emisiones sobre el mismo eje. Medias móviles y Bollinger se calculan sobre observaciones disponibles, no sobre días naturales; no se interpolan cotizaciones faltantes.")

    history = dataset.pivot.copy()
    history.index = pd.to_datetime(history.index, errors="coerce")
    history = history.loc[history.index.notna() & (history.index <= pd.Timestamp(asof))]
    history = history.sort_index()
    history = history.loc[:, ~history.columns.duplicated()]
    history.columns = history.columns.map(str)
    history = history.loc[:, history.notna().any(axis=0)]
    if history.empty:
        st.warning("No hay cotizaciones históricas disponibles hasta la fecha seleccionada.")
        return

    available = history.columns.tolist()
    active = history.iloc[-1].dropna().index.tolist()
    suggested = active[:min(3, len(active))] or available[:min(3, len(available))]
    chosen = st.multiselect(
        "Selecciona las emisiones para comparar", available, default=suggested,
        key=f"{key_prefix}_hist_emissions",
    )
    if not chosen:
        st.info("Selecciona una o más emisiones para mostrar su evolución.")
        return

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        horizon = st.selectbox("Ventana histórica", ["Toda la historia", "3 meses", "6 meses", "1 año", "2 años", "3 años"],
                               index=3, key=f"{key_prefix}_hist_horizon")
    with c2:
        overlays = st.multiselect("Indicadores técnicos", ["Media móvil 14", "Media móvil 60", "Media móvil 200", "Bollinger ±2σ"],
                                  default=["Media móvil 14", "Media móvil 60", "Media móvil 200", "Bollinger ±2σ"],
                                  key=f"{key_prefix}_hist_indicators")
    with c3:
        indicator_series = st.selectbox("Indicadores sobre la emisión", chosen, key=f"{key_prefix}_hist_focus")

    boll_window = st.selectbox("Ventana Bollinger (observaciones)", [14, 20, 30, 60],
                               index=1, key=f"{key_prefix}_hist_boll_window") if "Bollinger ±2σ" in overlays else 20

    # Los indicadores se estiman con historia completa; el filtro de fechas solo limita la visualización.
    data = history[chosen].apply(pd.to_numeric, errors="coerce")
    focus = data[indicator_series].dropna()
    moving = {period: focus.rolling(period, min_periods=period).mean() for period in (14, 60, 200)}
    middle = focus.rolling(boll_window, min_periods=boll_window).mean()
    sigma = focus.rolling(boll_window, min_periods=boll_window).std(ddof=0)
    upper, lower = middle + 2 * sigma, middle - 2 * sigma
    periods = {"3 meses": 3, "6 meses": 6, "1 año": 12, "2 años": 24, "3 años": 36}
    start = data.index.min() if horizon == "Toda la historia" else data.index.max() - pd.DateOffset(months=periods[horizon])
    visible = data.loc[data.index >= start]

    fig = go.Figure()
    palette = ["#087d81", "#355e96", "#d97706", "#9c6db8", "#d05b62", "#168b61", "#754c9e", "#1c869f"]
    for i, sym in enumerate(chosen):
        part = visible[sym].dropna()
        fig.add_trace(go.Scatter(x=part.index, y=part, mode="lines", name=sym,
                                 line=dict(color=palette[i % len(palette)], width=2.4 if sym == indicator_series else 1.8),
                                 hovertemplate=f"{sym}<br>%{{x|%d-%m-%Y}}<br>Tasa %{{y:.4f}}%<extra></extra>"))

    if "Bollinger ±2σ" in overlays:
        low = lower.loc[lower.index >= start].dropna()
        high = upper.loc[upper.index >= start].dropna()
        if not low.empty and not high.empty:
            fig.add_trace(go.Scatter(x=high.index, y=high, mode="lines", line=dict(color="#7d8ea8", width=1, dash="dot"),
                                     name=f"Bollinger superior ({indicator_series})", hovertemplate="Superior %{y:.4f}%<extra></extra>"))
            fig.add_trace(go.Scatter(x=low.index, y=low, mode="lines", line=dict(color="#7d8ea8", width=1, dash="dot"),
                                     fill="tonexty", fillcolor="rgba(125,142,168,0.11)",
                                     name=f"Bollinger inferior ({indicator_series})", hovertemplate="Inferior %{y:.4f}%<extra></extra>"))
        else:
            st.caption(f"Bollinger necesita al menos {boll_window} cotizaciones válidas de {indicator_series}.")

    for period, color in [(14, "#e8a041"), (60, "#9c6db8"), (200, "#202f46")]:
        if f"Media móvil {period}" not in overlays:
            continue
        line = moving[period].loc[moving[period].index >= start].dropna()
        if line.empty:
            st.caption(f"Media móvil {period}: faltan cotizaciones suficientes de {indicator_series}.")
            continue
        fig.add_trace(go.Scatter(x=line.index, y=line, mode="lines", name=f"MM{period} · {indicator_series}",
                                 line=dict(color=color, width=2, dash="dash"),
                                 hovertemplate=f"MM{period}: %{{y:.4f}}%<extra></extra>"))

    fig.update_layout(template="plotly_white", height=550, hovermode="x unified",
                      xaxis_title="Fecha", yaxis_title="Rendimiento (%)",
                      paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#263b50",
                      legend=dict(orientation="h", y=-0.21, x=0), margin=dict(t=25, b=105, l=55, r=25))
    fig.update_xaxes(showgrid=True, gridcolor="#e9eff5")
    fig.update_yaxes(showgrid=True, gridcolor="#e9eff5")
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}_hist_figure")
    latest = focus.iloc[-1] if not focus.empty else np.nan
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Última tasa · {indicator_series}", f"{latest:.4f}%" if np.isfinite(latest) else "n/d")
    for col, period in [(m2, 14), (m3, 200)]:
        val = moving[period].iloc[-1] if not moving[period].empty else np.nan
        col.metric(f"MM{period} · {indicator_series}", f"{val:.4f}%" if np.isfinite(val) else "n/d")
    with st.expander("Ver datos históricos y descargar CSV"):
        exported = visible.copy()
        for period in (14, 60, 200):
            exported[f"MM{period} · {indicator_series}"] = moving[period].reindex(exported.index)
        exported[f"Bollinger superior · {indicator_series}"] = upper.reindex(exported.index)
        exported[f"Bollinger inferior · {indicator_series}"] = lower.reindex(exported.index)
        st.dataframe(exported.sort_index(ascending=False), use_container_width=True)
        st.download_button("Descargar histórico e indicadores", exported.to_csv(index_label="Fecha").encode("utf-8-sig"),
                           file_name=f"neutrino_{key_prefix}_historico_tasas.csv", mime="text/csv", key=f"{key_prefix}_hist_csv")

def read_market_file(path: str) -> pd.DataFrame:
    """Lee CSV o Excel probando los encodings usuales de vectores mexicanos."""
    p = Path(path)
    if p.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(p, engine="openpyxl")

    last_error = None
    for enc in ("latin1", "cp1252", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(p, encoding=enc)
        except Exception as exc:
            last_error = exc
    raise last_error


def normalize_column_lookup(df: pd.DataFrame) -> dict:
    return {str(c).strip().lower(): c for c in df.columns}


def parse_series_maturity(series_value) -> pd.Timestamp | None:
    """Extrae una fecha YYMMDD desde valores como 270603, M 270603 o BI270603."""
    return eng.parse_maturity(series_value)


def build_cetes_curve(cetes_path: str, requested_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp]:
    """
    Soporta:
    1) Base histórica con fecha, SERIE y RENDIMIENTO.
    2) Vector de mercado con TV, Serie y Rendimiento.
    """
    raw = read_market_file(cetes_path).copy()
    cols = normalize_column_lookup(raw)

    fecha_col = cols.get("fecha")
    serie_col = cols.get("serie")
    rend_col = cols.get("rendimiento")
    tv_col = cols.get("tv")

    if serie_col is None or rend_col is None:
        raise ValueError("La base CETES debe incluir las columnas SERIE y RENDIMIENTO.")

    if tv_col is not None:
        tv = raw[tv_col].astype(str).str.strip().str.upper()
        # En vectores mexicanos CETES suele identificarse como BI.
        mask = tv.isin(["BI", "CETES", "CETE"])
        if mask.any():
            raw = raw.loc[mask].copy()

    effective_date = pd.Timestamp(requested_date)

    if fecha_col is not None:
        raw[fecha_col] = pd.to_datetime(raw[fecha_col], errors="coerce")
        raw = raw.dropna(subset=[fecha_col])
        dates = pd.DatetimeIndex(raw[fecha_col].unique()).sort_values()
        if len(dates) == 0:
            raise ValueError("La columna fecha de CETES no contiene fechas válidas.")
        pos = dates.searchsorted(effective_date, side="right") - 1
        effective_date = pd.Timestamp(dates[max(pos, 0)])
        raw = raw.loc[raw[fecha_col] == effective_date].copy()

    raw[rend_col] = pd.to_numeric(raw[rend_col], errors="coerce")
    raw = raw.dropna(subset=[serie_col, rend_col])

    rows = []
    for _, row in raw.iterrows():
        maturity = parse_series_maturity(row[serie_col])
        if maturity is None:
            continue
        tenor_days = (pd.Timestamp(maturity) - effective_date).days
        if tenor_days <= 0:
            continue
        rows.append({
            "SERIE": str(row[serie_col]).strip(),
            "MATURITY": pd.Timestamp(maturity),
            "TENOR_DAYS": int(tenor_days),
            "TENOR": tenor_days / 365.0,
            "CETES": float(row[rend_col]),
        })

    curve = pd.DataFrame(rows)
    if curve.empty:
        raise ValueError("No se pudieron construir vencimientos válidos para CETES.")

    curve = (
        curve.sort_values("TENOR_DAYS")
        .drop_duplicates(subset=["TENOR_DAYS"], keep="last")
        .reset_index(drop=True)
    )
    return curve, effective_date


def build_m_zero_curve(vector_path: str, requested_date: pd.Timestamp) -> pd.DataFrame:
    """
    Bootstrap de curva cupón cero de Bonos M usando el motor original.
    Usa settlement T+2 desde la fecha efectiva seleccionada.
    """
    raw = read_market_file(vector_path).copy()
    cols = normalize_column_lookup(raw)

    required = ["tv", "serie", "rendimiento", "tasacuponvigente"]
    missing = [name for name in required if name not in cols]
    if missing:
        raise ValueError(
            "El vector debe incluir TV, Serie, Rendimiento y TasaCuponVigente. "
            f"Faltan: {', '.join(missing)}"
        )

    tv_col = cols["tv"]
    serie_col = cols["serie"]
    rend_col = cols["rendimiento"]
    coupon_col = cols["tasacuponvigente"]

    dfm = raw.loc[
        raw[tv_col].astype(str).str.strip().str.upper().eq("M")
    ].copy()

    dfm[rend_col] = pd.to_numeric(dfm[rend_col], errors="coerce")
    dfm[coupon_col] = pd.to_numeric(dfm[coupon_col], errors="coerce")
    dfm = dfm.dropna(subset=[serie_col, rend_col, coupon_col])

    settlement = pd.Timestamp(requested_date).date() + timedelta(days=2)
    instruments = []
    metadata = []

    for _, row in dfm.iterrows():
        maturity_ts = parse_series_maturity(row[serie_col])
        if maturity_ts is None:
            continue

        maturity = maturity_ts.date()
        if maturity <= settlement:
            continue

        yld = float(row[rend_col])
        coupon_raw = float(row[coupon_col])
        coupon_pct = coupon_raw * 100.0 if abs(coupon_raw) <= 1.0 else coupon_raw

        price = eng.P_bono2(
            settlement,
            maturity,
            100,
            coupon_pct,
            yld,
            182,
            0,
            182,
            182,
        )

        iid = str(row[serie_col]).strip()
        instruments.append({
            "iid": iid,
            "maturity": maturity,
            "coupon_pct": coupon_pct,
            "priceP48": float(price),
        })
        metadata.append({
            "SERIE": iid,
            "MATURITY": pd.Timestamp(maturity),
            "TENOR_DAYS": (maturity - settlement).days,
            "TENOR": (maturity - settlement).days / 365.0,
            "REND_M": yld,
        })

    if not instruments:
        raise ValueError("No se encontraron Bonos M válidos en el vector.")

    zero_map, _ = eng.bootstrap_curve_and_zero_map(settlement, instruments)
    out = pd.DataFrame(metadata)
    out["ZERO_M"] = out["SERIE"].map(zero_map)
    out = out.dropna(subset=["ZERO_M"]).sort_values("TENOR_DAYS").reset_index(drop=True)

    if out.empty:
        raise ValueError("El bootstrap no produjo tasas cupón cero válidas.")

    return out


def zero_vs_cetes_figure(aligned: pd.DataFrame, max_tenor: float):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=aligned["TENOR"],
            y=aligned["CETES"],
            mode="lines+markers",
            name="CETES",
            text=aligned["SERIE_CETE"],
            customdata=aligned[["TENOR_DAYS"]].to_numpy(),
            hovertemplate=(
                "%{text}<br>"
                "Plazo: %{customdata[0]} días<br>"
                "Tenor: %{x:,.2f} años<br>"
                "Tasa CETES: %{y:,.2f}%<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=aligned["TENOR"],
            y=aligned["ZERO_M_INTERP"],
            mode="lines+markers",
            name="Cupón cero Bonos M interpolada",
            text=aligned["SERIE_CETE"],
            customdata=aligned[["TENOR_DAYS"]].to_numpy(),
            hovertemplate=(
                "Nodo CETE: %{text}<br>"
                "Plazo: %{customdata[0]} días<br>"
                "Tenor: %{x:,.2f} años<br>"
                "Cupón cero M interpolada: %{y:,.2f}%<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Curva cupón cero Bonos M interpolada vs CETES · límite {max_tenor:,.2f} años",
        xaxis_title="Tenor (años)",
        yaxis_title="Tasa anual (%)",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=560,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    fig.update_xaxes(range=[0, max_tenor * 1.03])
    return fig

def interpolate_curve_at_tenors(source_tenor, source_rate, target_tenor):
    x = np.asarray(source_tenor, dtype=float)
    y = np.asarray(source_rate, dtype=float)
    targets = np.asarray(target_tenor, dtype=float)

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if len(x) < 2:
        return np.full(len(targets), np.nan)

    return np.interp(targets, x, y, left=np.nan, right=np.nan)


def breakeven_curve_figure(be: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=be["TENOR"],
            y=be["BREAKEVEN"],
            mode="lines+markers",
            name="Breakeven",
            text=be["UDI"],
            customdata=be[["NOMINAL_INTERP", "REAL"]].to_numpy(),
            hovertemplate=(
                "%{text}<br>"
                "Tenor: %{x:,.2f} años<br>"
                "Breakeven: %{y:,.2f}%<br>"
                "Nominal interpolada: %{customdata[0]:,.2f}%<br>"
                "Tasa real: %{customdata[1]:,.2f}%<extra></extra>"
            ),
        )
    )
    fig.add_hline(
        y=float(be["BREAKEVEN"].mean()),
        line_dash="dash",
        annotation_text=f"Promedio {be['BREAKEVEN'].mean():,.2f}%",
    )
    fig.update_layout(
        title="Curva de inflación breakeven",
        xaxis_title="Tenor (años)",
        yaxis_title="Breakeven (%)",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=500,
        hovermode="x unified",
    )
    return fig


def breakeven_history_figure(hist: pd.DataFrame, serie: str):
    vals = hist["BREAKEVEN"].dropna()
    mu = vals.mean()
    sd = vals.std()
    last = vals.iloc[-1]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist["Fecha"],
            y=hist["BREAKEVEN"],
            mode="lines",
            name="Breakeven",
        )
    )
    fig.add_hline(y=mu, line_dash="dash", annotation_text=f"Media {mu:,.2f}%")
    if np.isfinite(sd) and sd > 0:
        fig.add_hrect(
            y0=mu - sd,
            y1=mu + sd,
            opacity=0.12,
            line_width=0,
            annotation_text="±1σ",
        )
        fig.add_hline(y=mu + 2 * sd, line_dash="dot")
        fig.add_hline(y=mu - 2 * sd, line_dash="dot")
    fig.add_hline(y=last, line_dash="dash", annotation_text=f"Último {last:,.2f}%")

    fig.update_layout(
        title=f"Histórico breakeven: {serie}",
        xaxis_title="Fecha",
        yaxis_title="Breakeven (%)",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=460,
        hovermode="x unified",
    )
    return fig


def breakeven_histogram_figure(hist: pd.DataFrame, serie: str):
    vals = hist["BREAKEVEN"].dropna()
    mu = vals.mean()
    sd = vals.std()
    last = vals.iloc[-1]

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=vals,
            nbinsx=30,
            histnorm="probability density",
            name="Distribución",
            opacity=0.75,
        )
    )
    fig.add_vline(x=mu, line_dash="dash", annotation_text=f"Media {mu:,.2f}%")
    if np.isfinite(sd) and sd > 0:
        fig.add_vrect(
            x0=mu - sd,
            x1=mu + sd,
            opacity=0.10,
            line_width=0,
            annotation_text="±1σ",
        )
        fig.add_vline(x=mu + 2 * sd, line_dash="dot")
        fig.add_vline(x=mu - 2 * sd, line_dash="dot")
    fig.add_vline(x=last, line_dash="dash", annotation_text=f"Último {last:,.2f}%")

    fig.update_layout(
        title=f"Distribución breakeven: {serie}",
        xaxis_title="Breakeven (%)",
        yaxis_title="Densidad",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=460,
        bargap=0.05,
    )
    return fig


def load_cetes_dashboard_table(vector_path: str, funding_rate_pct: float, monto: float) -> pd.DataFrame:
    """Replica el dashboard General CETES del script original: TV=BI, 1D, DV0 y carry."""
    raw = read_market_file(vector_path).copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    lookup = normalize_column_lookup(raw)

    def pick(*names):
        for name in names:
            if name.lower() in lookup:
                return lookup[name.lower()]
        return None

    tv_col = pick("TV", "TipoValor", "tipo valor")
    serie_col = pick("Serie", "SERIE")
    dpv_col = pick("DiasPorVencer", "Dias por vencer", "Días por vencer", "DXV", "DiasPorVencer24Hrs")
    rend_col = pick("Rendimiento", "RENDIMIENTO", "yield")

    if not all([tv_col, serie_col, dpv_col, rend_col]):
        raise ValueError(
            "El vector debe incluir TV, Serie, DiasPorVencer/DXV y Rendimiento."
        )

    d = raw.loc[
        raw[tv_col].astype(str).str.strip().str.upper().eq("BI"),
        [serie_col, dpv_col, rend_col],
    ].copy()
    d.columns = ["Serie", "DiasPorVencer", "Rendimiento"]

    d["Serie"] = pd.to_numeric(d["Serie"], errors="coerce")
    d["DiasPorVencer"] = pd.to_numeric(d["DiasPorVencer"], errors="coerce")
    d["Rendimiento"] = pd.to_numeric(d["Rendimiento"], errors="coerce")
    d = d.dropna(subset=["Serie", "DiasPorVencer", "Rendimiento"])
    d = d.loc[d["DiasPorVencer"] > 0].copy()

    # Heurística del script original: si el rendimiento viene decimal, lo pasa a porcentaje.
    if not d.empty and d["Rendimiento"].max() <= 1.5:
        d["Rendimiento"] *= 100.0

    d["Serie"] = d["Serie"].round().astype(int).astype(str).str.zfill(6)
    d["DiasPorVencer"] = d["DiasPorVencer"].round().astype(int)

    dias = d["DiasPorVencer"].astype(float)
    rend = d["Rendimiento"].astype(float)

    d["1 DIA"] = (
        ((1.0 + (rend / 36000.0 * dias)) ** (1.0 / dias) - 1.0)
        * 360.0
        * 100.0
    )
    d["DV0"] = (
        (
            -(10.0 / (1.0 + dias * (rend / 36000.0)))
            + (10.0 / (1.0 + dias * ((rend - 0.01) / 36000.0)))
        )
        * (float(monto) / 10.0)
    )
    d["CARRY"] = (
        (d["1 DIA"] - float(funding_rate_pct))
        * float(monto)
        / 36000.0
    )
    d["DIAS_RECUP_DV0"] = np.where(
        d["CARRY"].abs() > 1e-12,
        d["DV0"] / d["CARRY"],
        np.nan,
    )
    d["PRECIO"] = 10.0 / (
        1.0 + dias * (rend / 36000.0)
    )

    return d.sort_values("DiasPorVencer").reset_index(drop=True)


def cetes_curve_figure(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["DiasPorVencer"],
            y=df["Rendimiento"],
            mode="lines+markers",
            name="Rendimiento CETES",
            text=df["Serie"],
            customdata=df[["1 DIA", "DV0", "CARRY"]].to_numpy(),
            hovertemplate=(
                "%{text}<br>"
                "Plazo: %{x:,.2f} días<br>"
                "Rendimiento: %{y:,.2f}%<br>"
                "Tasa 1D: %{customdata[0]:,.2f}%<br>"
                "DV0: %{customdata[1]:,.2f}<br>"
                "Carry: %{customdata[2]:,.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="Curva CETES",
        xaxis_title="Días por vencer",
        yaxis_title="Rendimiento (%)",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=500,
        hovermode="x unified",
    )
    return fig


def cetes_metric_figure(df: pd.DataFrame, metric: str, title: str):
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["Serie"],
            y=df[metric],
            text=df[metric].map(lambda x: f"{x:,.2f}"),
            textposition="outside",
            hovertemplate="%{x}<br>" + title + ": %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Serie",
        yaxis_title=title,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font_color="#263b50",
        height=480,
    )
    return fig


def cetes_scenario_table(
    serie: str,
    dias: int,
    rendimiento: float,
    monto: float,
    funding: float,
    shocks_bp,
):
    rows = []
    for bp in shocks_bp:
        y = rendimiento + bp / 100.0
        precio = 10.0 / (1.0 + dias * (y / 36000.0))
        tasa_1d = (
            ((1.0 + (y / 36000.0 * dias)) ** (1.0 / dias) - 1.0)
            * 360.0
            * 100.0
        )
        dv0 = (
            (
                -(10.0 / (1.0 + dias * (y / 36000.0)))
                + (10.0 / (1.0 + dias * ((y - 0.01) / 36000.0)))
            )
            * (float(monto) / 10.0)
        )
        carry = ((tasa_1d - funding) * monto) / 36000.0
        rows.append(
            {
                "Serie": serie,
                "Shock (pb)": bp,
                "Rendimiento (%)": y,
                "Precio": precio,
                "Tasa 1D (%)": tasa_1d,
                "DV0": dv0,
                "Carry": carry,
            }
        )
    return pd.DataFrame(rows)


def fmt_num(value, decimals: int = 2, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value) or not np.isfinite(float(value)):
            return "n/a"
        return f"{float(value):,.{decimals}f}{suffix}"
    except Exception:
        return str(value)


def parse_formatted_number(value: str, default: float) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return float(default)


def format_numeric_dataframe(data):
    if not isinstance(data, pd.DataFrame):
        return data
    out = data.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].map(
                lambda x: "" if pd.isna(x) else f"{float(x):,.2f}"
            )
    return out


def show_dataframe(data, *args, **kwargs):
    return st.dataframe(format_numeric_dataframe(data), *args, **kwargs)

st.title("NEUTRINO FIXED INCOME TERMINAL")
st.caption("Bonos M · Udibonos · Spreads · Z-scores · Curvas · Carry · Reporte PDF")

BASE_DIR = Path(__file__).resolve().parent

bonos_path = str(BASE_DIR / "BASE M.xlsx")
udis_path = str(BASE_DIR / "base udis.xlsx")
vector_path = str(BASE_DIR / "vector.csv")

required_files = {
    "BASE M.xlsx": Path(bonos_path),
    "base udis.xlsx": Path(udis_path),
    "vector.csv": Path(vector_path),
}

missing_files = [name for name, path in required_files.items() if not path.exists()]

with st.sidebar:
    st.header("Configuración")
    matrix_days = st.select_slider(
        "Ventana de matrices",
        options=[20, 30, 60, 90, 120, 180, 250],
        value=60,
    )
    curve_days = st.select_slider(
        "Comparación de curva",
        options=[1, 7, 15, 30, 60, 90, 180],
        value=30,
    )
    top_n = st.slider("Pares extremos", 3, 15, 5)
    funding_text = st.text_input(
        "Tasa de fondeo (%)",
        value="6.50",
        help="Ejemplo: 6.50",
    )
    amount_text = st.text_input(
        "Monto general",
        value="100,000,000.00",
        help="Ejemplo: 100,000,000.00",
    )
    funding = parse_formatted_number(funding_text, 6.50)
    amount = parse_formatted_number(amount_text, 100_000_000.00)
    st.divider()

if missing_files:
    st.error(
        "Faltan archivos de datos en el repositorio: "
        + ", ".join(missing_files)
    )
    st.stop()

try:
    bonos = load_ds(bonos_path, "Bonos M")
    udis = load_ds(udis_path, "Udibonos")
except Exception as exc:
    st.error(f"No se pudieron leer los datos: {exc}")
    st.stop()

latest_update = max(path.stat().st_mtime for path in required_files.values())
latest_update_text = datetime.fromtimestamp(latest_update).strftime("%d-%m-%Y %H:%M")
st.caption(f"Última actualización de archivos: {latest_update_text}")

available_dates = pd.DatetimeIndex(bonos.pivot.index).sort_values()
default_date = available_dates.max().date()
report_date_input = st.sidebar.date_input("Fecha del reporte", value=default_date, min_value=available_dates.min().date(), max_value=default_date)
report_date = eng.nearest_available_date(bonos.pivot, pd.Timestamp(report_date_input))

try:
    spread, zscore, filtered, spread_ratio, z_ratio, start_date, end_date = eng.compute_spread_matrices(
        bonos, report_date - pd.Timedelta(days=matrix_days), report_date
    )
    top_pairs = eng.best_pairs(zscore, spread, top_n=top_n)
    curve, curve_date, comparison_date = eng.compute_curve_table(
        bonos, report_date, report_date - pd.Timedelta(days=curve_days)
    )
    metrics = eng.curve_metrics(bonos, curve_date, comparison_date)
except Exception as exc:
    st.error(f"Error en los cálculos principales: {exc}")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Fecha efectiva", f"{report_date:%d-%m-%Y}")
m2.metric("Series activas", fmt_num(len(filtered.columns)))
m3.metric("Pares analizados", fmt_num(int(len(filtered.columns)*(len(filtered.columns)-1)/2)))
if not top_pairs.empty:
    m4.metric("Mayor |Z|", f"{top_pairs.iloc[0]['Z']:+,.2f}", top_pairs.iloc[0]["PAR"])
else:
    m4.metric("Mayor |Z|", "n/a")

main_tabs = st.tabs(["BONOS M", "UDIS", "CETES", "PCA CURVAS", "RV SCANNER", "ESTABILIDAD", "DESCARGA"])

with main_tabs[0]:
    st.subheader("Módulo Bonos M")
    bonos_tabs = st.tabs([
        "Resumen",
        "Matrices",
        "Pares extremos",
        "Curva",
        "Cupón cero vs CETES",
        "Carry",
        "Histórico de tasas",
    ])

    with bonos_tabs[0]:
        st.subheader("Lectura ejecutiva")
        c1, c2, c3 = st.columns(3)
        c1.metric("2 años", f"{metrics.get('2Y', np.nan):,.2f}%" if np.isfinite(metrics.get('2Y', np.nan)) else "n/a")
        c2.metric("5 años", f"{metrics.get('5Y', np.nan):,.2f}%" if np.isfinite(metrics.get('5Y', np.nan)) else "n/a")
        c3.metric("10 años", f"{metrics.get('10Y', np.nan):,.2f}%" if np.isfinite(metrics.get('10Y', np.nan)) else "n/a")
        st.plotly_chart(curve_figure(curve, curve_days), use_container_width=True, key="summary_curve")
        show_curve_change_summary(curve, curve_days, "bonos_summary")
        show_dataframe(top_pairs[["PAR", "SPREAD", "Z", "ABS_Z"]] if not top_pairs.empty else top_pairs, use_container_width=True, hide_index=True)


    with bonos_tabs[1]:
        st.caption("Cada celda refleja exclusivamente el histórico de ese par: el número es el spread/Z-score y el color es su posición relativa histórica. Selecciona un par para ver su evolución.")

        matrix_choice = st.radio(
            "Matriz",
            ["Z-score", "Spread"],
            horizontal=True,
            key="matrix_type_selector",
        )

        selected_matrix = zscore if matrix_choice == "Z-score" else spread
        matrix_title = (
            f"Z-score · ventana {matrix_days} días"
            if matrix_choice == "Z-score"
            else f"Spread · ventana {matrix_days} días"
        )
        decimals = 2 if matrix_choice == "Z-score" else 4

        st.plotly_chart(
            heatmap_figure(selected_matrix, matrix_title, decimals, z_ratio if matrix_choice == "Z-score" else spread_ratio),
            use_container_width=True,
            key=f"matrix_chart_{matrix_choice}",
        )

        available_series = [str(c) for c in filtered.columns]

        if len(available_series) < 2:
            st.warning("No hay suficientes series para formar combinaciones.")
        else:
            default_s1 = available_series[-1]
            default_s2 = available_series[0]

            col_a, col_b = st.columns(2)
            with col_a:
                s1 = st.selectbox(
                    "Serie 1",
                    available_series,
                    index=available_series.index(
                        st.session_state.get("selected_s1", default_s1)
                    ) if st.session_state.get("selected_s1", default_s1) in available_series else len(available_series) - 1,
                    key="selected_s1",
                )
            with col_b:
                s2_options = [s for s in available_series if s != s1]
                current_s2 = st.session_state.get("selected_s2", default_s2)
                if current_s2 not in s2_options:
                    current_s2 = s2_options[0]
                s2 = st.selectbox(
                    "Serie 2",
                    s2_options,
                    index=s2_options.index(current_s2),
                    key="selected_s2",
                )

            hist_matrix = eng.pair_history(filtered, s1, s2)

            if hist_matrix.empty:
                st.warning("El par seleccionado no tiene suficientes observaciones en la ventana elegida.")
            else:
                vals = hist_matrix["Diferencia"].dropna()
                current = vals.iloc[-1]
                mu = vals.mean()
                sd = vals.std()
                z_current = (current - mu) / sd if np.isfinite(sd) and sd > 0 else np.nan
                percentile = (vals <= current).mean() * 100

                matrix_value = selected_matrix.loc[s1, s2] if s1 in selected_matrix.index and s2 in selected_matrix.columns else np.nan

                st.subheader(f"Par seleccionado: {s1} - {s2}")

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Valor en matriz", f"{matrix_value:,.2f}" if np.isfinite(matrix_value) else "n/a")
                c2.metric("Spread actual", f"{current:,.2f}")
                c3.metric("Media", f"{mu:,.2f}")
                c4.metric("Z-score actual", f"{z_current:+,.2f}" if np.isfinite(z_current) else "n/a")
                c5.metric("Percentil", f"{percentile:,.2f}%")

                left, right = st.columns(2)
                with left:
                    st.plotly_chart(
                        pair_figure(hist_matrix, s1, s2),
                        use_container_width=True,
                        key=f"matrix_pair_history_{s1}_{s2}_{matrix_days}",
                    )
                with right:
                    st.plotly_chart(
                        histogram_figure(hist_matrix, s1, s2),
                        use_container_width=True,
                        key=f"matrix_pair_hist_{s1}_{s2}_{matrix_days}",
                    )


    with bonos_tabs[2]:
        if top_pairs.empty:
            st.warning("No hay pares suficientes para analizar.")
        else:
            labels = top_pairs["PAR"].tolist()
            selected = st.selectbox("Selecciona un par", labels)
            row = top_pairs.loc[top_pairs["PAR"] == selected].iloc[0]
            hist = eng.pair_history(filtered, row["S1"], row["S2"])
            a, b, c = st.columns(3)
            a.metric("Spread actual", f"{row['SPREAD']:,.2f}")
            b.metric("Z-score", f"{row['Z']:+,.2f}")
            pct = (hist["Diferencia"] <= hist["Diferencia"].iloc[-1]).mean()*100 if not hist.empty else np.nan
            c.metric("Percentil histórico", f"{pct:,.2f}%")
            st.plotly_chart(pair_figure(hist, row["S1"], row["S2"]), use_container_width=True, key="top_pair_history")
            st.bar_chart(hist.set_index("Fecha")[["Diferencia"]], height=240)


    with bonos_tabs[3]:
        st.plotly_chart(curve_figure(curve, curve_days), use_container_width=True, key="curve_tab_main")
        display_curve = curve.copy()
        display_curve["DIF_PB"] = display_curve["DIF"] * 100
        show_dataframe(display_curve[["SERIE", "TENOR", "ACTUAL", "HACE_30D", "DIF_PB"]], use_container_width=True, hide_index=True)



    with bonos_tabs[4]:
        st.subheader("Curva cupón cero de Bonos M vs curva CETES")
        st.caption(
            "Ambas curvas se construyen desde el mismo vector.csv. Se muestran todos los CETES "
            "y la curva cupón cero de Bonos M se interpola en cada nodo usando la curva M completa, "
            "incluyendo Bonos M con vencimiento posterior al CETE más largo."
        )

        if not vector_path:
            st.info(
                "Carga `vector.csv`. Del mismo archivo se tomarán CETES con TV = BI "
                "y Bonos M con TV = M."
            )
        else:
            try:
                cetes_curve, cetes_effective_date = build_cetes_curve(vector_path, report_date)
                m_zero_curve = build_m_zero_curve(vector_path, report_date)

                max_cetes_tenor = float(cetes_curve["TENOR"].max())
                max_cetes_days = int(cetes_curve["TENOR_DAYS"].max())

                # Curva completa de Bonos M como soporte de interpolación.
                m_zero_support = m_zero_curve.copy().sort_values("TENOR").reset_index(drop=True)

                if len(m_zero_support) < 2:
                    st.warning(
                        "Se necesitan al menos dos nodos válidos de Bonos M para interpolar "
                        "la curva cupón cero."
                    )
                else:
                    aligned = cetes_curve[
                        ["SERIE", "MATURITY", "TENOR_DAYS", "TENOR", "CETES"]
                    ].copy()
                    aligned = aligned.rename(columns={"SERIE": "SERIE_CETE"})

                    aligned["ZERO_M_INTERP"] = interpolate_curve_at_tenors(
                        m_zero_support["TENOR"],
                        m_zero_support["ZERO_M"],
                        aligned["TENOR"],
                    )

                    aligned["SPREAD_ZERO_CETES_PB"] = (
                        aligned["ZERO_M_INTERP"] - aligned["CETES"]
                    ) * 100

                    valid_aligned = aligned.dropna(subset=["ZERO_M_INTERP"]).copy()

                    if float(m_zero_support["TENOR"].max()) < max_cetes_tenor:
                        st.warning(
                            "La curva de Bonos M no alcanza el vencimiento del CETE más largo. "
                            "Todos los CETES se muestran en la tabla, pero los que queden fuera "
                            "del rango de M no tendrán tasa cupón cero interpolada."
                        )

                    if valid_aligned.empty:
                        st.error(
                            "No fue posible interpolar ningún nodo CETE con la curva de Bonos M."
                        )
                    else:
                        st.plotly_chart(
                            zero_vs_cetes_figure(
                                valid_aligned,
                                max_cetes_tenor,
                            ),
                            use_container_width=True,
                            key="zero_coupon_vs_cetes",
                        )

                    comparison = aligned.copy()

                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Fecha CETES", f"{cetes_effective_date:%d-%m-%Y}")
                    k2.metric("Máximo CETES", f"{max_cetes_days:,.2f} días")
                    k3.metric("Máximo CETES", f"{max_cetes_tenor:,.2f} años")
                    k4.metric(
                        "CETES interpolados",
                        fmt_num(int(comparison["ZERO_M_INTERP"].notna().sum())),
                    )

                    show_dataframe(
                        comparison.rename(
                            columns={
                                "SERIE_CETE": "CETE",
                                "MATURITY": "Vencimiento",
                                "TENOR_DAYS": "Días",
                                "TENOR": "Años",
                                "CETES": "CETES (%)",
                                "ZERO_M_INTERP": "Cupón cero M interpolada (%)",
                                "SPREAD_ZERO_CETES_PB": "Spread cero-CETES (pb)",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    with st.expander("Ver nodos originales de la curva cupón cero de Bonos M"):
                        show_dataframe(
                            m_zero_support.rename(
                                columns={
                                    "SERIE": "Bono M",
                                    "MATURITY": "Vencimiento",
                                    "TENOR_DAYS": "Días",
                                    "TENOR": "Años",
                                    "REND_M": "YTM M (%)",
                                    "ZERO_M": "Cupón cero M (%)",
                                }
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                    with st.expander("Ver nodos originales de CETES"):
                        show_dataframe(
                            cetes_curve.rename(
                                columns={
                                    "SERIE": "CETE",
                                    "MATURITY": "Vencimiento",
                                    "TENOR_DAYS": "Días",
                                    "TENOR": "Años",
                                    "CETES": "Tasa CETES (%)",
                                }
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

            except Exception as exc:
                st.error(f"No fue posible construir la comparación: {exc}")



    with bonos_tabs[5]:
        if not vector_path:
            st.info("Carga `vector.csv` para calcular carry, DV01, theta y costo de fondeo.")
        else:
            try:
                carry = eng.load_carry_table(vector_path, funding_rate_pct=funding, monto=amount)
                if carry.empty:
                    st.warning("El vector no contiene registros M válidos o faltan columnas requeridas.")
                else:
                    show_dataframe(carry, use_container_width=True, hide_index=True)
                    best = carry.sort_values("Carry", ascending=False).iloc[0]
                    st.success(f"Mayor carry estimado: {best['Serie']} · ${best['Carry']:,.2f} diarios para el monto seleccionado.")
            except Exception as exc:
                st.error(f"No fue posible calcular carry: {exc}")

    with bonos_tabs[6]:
        render_yield_history(bonos, report_date, "bonos", "Bonos M")


with main_tabs[1]:
    st.subheader("Módulo integral de Udibonos")
    st.caption(
        "Matrices de tasas reales, pares, curva real, inflación breakeven y carry de Udibonos. "
        "Los cálculos utilizan la misma metodología del reporte original."
    )

    if udis is None:
        st.info("Carga `base udis.xlsx` para habilitar este módulo.")
    else:
        udi_tabs = st.tabs(
            [
                "Resumen UDIS",
                "Matrices UDIS",
                "Curva real",
                "Breakeven",
                "Detalle BE",
                "Carry UDIS",
                "Histórico de tasas",
            ]
        )

        # Cálculos comunes del módulo
        try:
            udi_report_date = eng.nearest_available_date(udis.pivot, report_date)
            (
                udi_spread,
                udi_zscore,
                udi_filtered,
                udi_spread_ratio,
                udi_z_ratio,
                udi_start,
                udi_end,
            ) = eng.compute_spread_matrices(
                udis,
                udi_report_date - pd.Timedelta(days=matrix_days),
                udi_report_date,
            )
            udi_pairs = eng.best_pairs(udi_zscore, udi_spread, top_n=top_n)
            udi_curve, udi_curve_date, udi_comparison_date = eng.compute_curve_table(
                udis,
                udi_report_date,
                udi_report_date - pd.Timedelta(days=curve_days),
            )
            be_snapshot, be_date = eng.compute_breakeven_snapshot(
                bonos,
                udis,
                report_date,
            )
            be_extremes, be_histories, be_start, be_end = eng.compute_breakeven_extremes(
                bonos,
                udis,
                report_date,
                matrix_days,
                top_n=top_n,
            )
        except Exception as exc:
            st.error(f"No fue posible calcular el módulo UDIS: {exc}")
            udi_spread = pd.DataFrame()
            udi_zscore = pd.DataFrame()
            udi_filtered = pd.DataFrame()
            udi_pairs = pd.DataFrame()
            udi_curve = pd.DataFrame()
            be_snapshot = pd.DataFrame()
            be_extremes = pd.DataFrame()
            be_histories = {}

        with udi_tabs[0]:
            if udi_filtered.empty:
                st.warning("No hay datos suficientes para el resumen de Udibonos.")
            else:
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Fecha UDIS", f"{udi_report_date:%d-%m-%Y}")
                r2.metric("Series reales", fmt_num(len(udi_filtered.columns)))
                r3.metric(
                    "Pares UDIS",
                    fmt_num(int(len(udi_filtered.columns) * (len(udi_filtered.columns) - 1) / 2)),
                )
                if not udi_pairs.empty:
                    r4.metric(
                        "Mayor |Z| real",
                        f"{udi_pairs.iloc[0]['Z']:+,.2f}",
                        udi_pairs.iloc[0]["PAR"],
                    )
                else:
                    r4.metric("Mayor |Z| real", "n/a")

                if not udi_curve.empty:
                    st.plotly_chart(
                        curve_figure(udi_curve, curve_days),
                        use_container_width=True,
                        key="udi_summary_curve",
                    )
                    show_curve_change_summary(udi_curve, curve_days, "udi_summary")

                if not udi_pairs.empty:
                    show_dataframe(
                        udi_pairs[["PAR", "SPREAD", "Z", "ABS_Z"]],
                        use_container_width=True,
                        hide_index=True,
                    )

        with udi_tabs[1]:
            if udi_filtered.empty:
                st.warning("No hay datos suficientes para construir matrices UDIS.")
            else:
                udi_matrix_choice = st.radio(
                    "Matriz UDIS",
                    ["Z-score", "Spread"],
                    horizontal=True,
                    key="udi_matrix_choice",
                )

                udi_selected_matrix = (
                    udi_zscore if udi_matrix_choice == "Z-score" else udi_spread
                )
                udi_decimals = 2 if udi_matrix_choice == "Z-score" else 4

                st.plotly_chart(
                    heatmap_figure(
                        udi_selected_matrix,
                        f"{udi_matrix_choice} UDIS · ventana {matrix_days} días",
                        udi_decimals,
                        udi_z_ratio if udi_matrix_choice == "Z-score" else udi_spread_ratio,
                    ),
                    use_container_width=True,
                    key=f"udi_matrix_{udi_matrix_choice}",
                )

                udi_series = [str(c) for c in udi_filtered.columns]
                if len(udi_series) >= 2:
                    u1, u2 = st.columns(2)
                    with u1:
                        udi_s1 = st.selectbox(
                            "Udिबono 1",
                            udi_series,
                            index=len(udi_series) - 1,
                            key="udi_s1",
                        )
                    with u2:
                        udi_s2_options = [s for s in udi_series if s != udi_s1]
                        udi_s2 = st.selectbox(
                            "Udibono 2",
                            udi_s2_options,
                            index=0,
                            key="udi_s2",
                        )

                    udi_hist = eng.pair_history(udi_filtered, udi_s1, udi_s2)

                    if not udi_hist.empty:
                        vals = udi_hist["Diferencia"].dropna()
                        last = vals.iloc[-1]
                        mu = vals.mean()
                        sd = vals.std()
                        z_now = (last - mu) / sd if np.isfinite(sd) and sd > 0 else np.nan
                        pct = (vals <= last).mean() * 100

                        q1, q2, q3, q4 = st.columns(4)
                        q1.metric("Spread real", f"{last:,.2f}")
                        q2.metric("Media", f"{mu:,.2f}")
                        q3.metric(
                            "Z-score",
                            f"{z_now:+,.2f}" if np.isfinite(z_now) else "n/a",
                        )
                        q4.metric("Percentil", f"{pct:,.2f}%")

                        left, right = st.columns(2)
                        with left:
                            st.plotly_chart(
                                pair_figure(udi_hist, udi_s1, udi_s2),
                                use_container_width=True,
                                key=f"udi_pair_history_{udi_s1}_{udi_s2}_{matrix_days}",
                            )
                        with right:
                            st.plotly_chart(
                                histogram_figure(udi_hist, udi_s1, udi_s2),
                                use_container_width=True,
                                key=f"udi_pair_hist_{udi_s1}_{udi_s2}_{matrix_days}",
                            )

        with udi_tabs[2]:
            if udi_curve.empty:
                st.warning("No fue posible construir la curva real de Udibonos.")
            else:
                st.plotly_chart(
                    curve_figure(udi_curve, curve_days),
                    use_container_width=True,
                    key="udi_real_curve",
                )
                udi_curve_display = udi_curve.copy()
                udi_curve_display["DIF_PB"] = udi_curve_display["DIF"] * 100
                show_dataframe(
                    udi_curve_display[
                        ["SERIE", "TENOR", "ACTUAL", "HACE_30D", "DIF_PB"]
                    ].rename(
                        columns={
                            "ACTUAL": "Tasa real actual (%)",
                            "HACE_30D": f"Tasa real hace {curve_days}d (%)",
                            "DIF_PB": "Cambio (pb)",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        with udi_tabs[3]:
            if be_snapshot.empty:
                st.warning(
                    "No se pudo construir el breakeven. Verifica que BASE M y base udis "
                    "tengan fechas compatibles."
                )
            else:
                st.plotly_chart(
                    breakeven_curve_figure(be_snapshot),
                    use_container_width=True,
                    key="udi_be_curve",
                )

                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Fecha BE", f"{be_date:%d-%m-%Y}")
                b2.metric("Breakevens", fmt_num(len(be_snapshot)))
                b3.metric("BE promedio", f"{be_snapshot['BREAKEVEN'].mean():,.2f}%")
                b4.metric(
                    "BE máximo",
                    f"{be_snapshot['BREAKEVEN'].max():,.2f}%",
                )

                show_dataframe(
                    be_snapshot.rename(
                        columns={
                            "UDI": "Udibono",
                            "TENOR": "Tenor (años)",
                            "NOMINAL_INTERP": "Nominal interpolada (%)",
                            "REAL": "Tasa real (%)",
                            "BREAKEVEN": "Breakeven (%)",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

                if not be_extremes.empty:
                    st.subheader("Breakevens más extremos por Z-score")
                    show_dataframe(
                        be_extremes.rename(
                            columns={
                                "UDI": "Udibono",
                                "TENOR": "Tenor",
                                "BREAKEVEN": "BE actual",
                                "MEAN": "Media",
                                "STD": "Desv. estándar",
                                "Z": "Z-score",
                                "ABS_Z": "|Z|",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

        with udi_tabs[4]:
            if be_snapshot.empty:
                st.warning("No hay breakevens disponibles.")
            else:
                be_series = be_snapshot["UDI"].astype(str).tolist()
                selected_be = st.selectbox(
                    "Selecciona un Udibono",
                    be_series,
                    key="selected_be_udi",
                )

                be_hist = eng.breakeven_history(
                    bonos,
                    udis,
                    selected_be,
                    report_date - pd.Timedelta(days=matrix_days),
                    report_date,
                )

                if be_hist.empty:
                    st.warning("No hay histórico suficiente para este breakeven.")
                else:
                    vals = be_hist["BREAKEVEN"].dropna()
                    be_last = vals.iloc[-1]
                    be_mu = vals.mean()
                    be_sd = vals.std()
                    be_z = (
                        (be_last - be_mu) / be_sd
                        if np.isfinite(be_sd) and be_sd > 0
                        else np.nan
                    )
                    be_pct = (vals <= be_last).mean() * 100

                    d1, d2, d3, d4 = st.columns(4)
                    d1.metric("BE actual", f"{be_last:,.2f}%")
                    d2.metric("Media", f"{be_mu:,.2f}%")
                    d3.metric(
                        "Z-score",
                        f"{be_z:+,.2f}" if np.isfinite(be_z) else "n/a",
                    )
                    d4.metric("Percentil", f"{be_pct:,.2f}%")

                    left, right = st.columns(2)
                    with left:
                        st.plotly_chart(
                            breakeven_history_figure(be_hist, selected_be),
                            use_container_width=True,
                            key=f"be_history_{selected_be}_{matrix_days}",
                        )
                    with right:
                        st.plotly_chart(
                            breakeven_histogram_figure(be_hist, selected_be),
                            use_container_width=True,
                            key=f"be_histogram_{selected_be}_{matrix_days}",
                        )

        with udi_tabs[5]:
            if not vector_path:
                st.info(
                    "Carga `vector.csv` para calcular carry de Udibonos con TV = S."
                )
            else:
                try:
                    udi_carry = eng.load_udibono_carry_table(
                        vector_path,
                        funding_rate_pct=funding,
                        monto=amount,
                    )
                    if udi_carry.empty:
                        st.warning(
                            "No se encontraron Udibonos TV=S válidos o faltan columnas "
                            "de precio, duración o días por vencer."
                        )
                    else:
                        c1, c2, c3 = st.columns(3)
                        best_carry = udi_carry.sort_values(
                            "Carry Neto",
                            ascending=False,
                        ).iloc[0]
                        c1.metric("Mejor carry UDI", str(best_carry["Serie"]))
                        c2.metric("Carry neto", f"${best_carry['Carry Neto']:,.2f}")
                        c3.metric(
                            "Tasa 1 día",
                            f"{best_carry['T.1Dia (%)']:,.2f}%",
                        )

                        show_dataframe(
                            udi_carry,
                            use_container_width=True,
                            hide_index=True,
                        )
                except Exception as exc:
                    st.error(f"No fue posible calcular carry UDIS: {exc}")


        with udi_tabs[6]:
            render_yield_history(udis, report_date, "udis", "Udibonos")



with main_tabs[2]:
    st.subheader("Dashboard CETES")
    st.caption(
        "Versión web del dashboard original: TV=BI, rendimiento, tasa de un día, "
        "DV0, carry, curva y simulación de escenarios."
    )

    if not vector_path:
        st.info("Carga `vector.csv` para habilitar el dashboard CETES.")
    else:
        try:
            cetes_dash = load_cetes_dashboard_table(
                vector_path,
                funding_rate_pct=funding,
                monto=amount,
            )
        except Exception as exc:
            st.error(f"No fue posible construir el dashboard CETES: {exc}")
            cetes_dash = pd.DataFrame()

        if cetes_dash.empty:
            st.warning("No se encontraron registros CETES con TV = BI.")
        else:
            cetes_tabs = st.tabs(
                [
                    "General",
                    "Curva",
                    "Carry y DV0",
                    "Ranking",
                    "Comparación cero M",
                ]
            )

            with cetes_tabs[0]:
                k1, k2, k3, k4, k5, k6 = st.columns(6)
                k1.metric("CETES activos", fmt_num(len(cetes_dash)))
                k2.metric("Fondeo", f"{funding:,.2f}%")
                k3.metric("Monto", f"${amount:,.2f}")
                k4.metric("Carry total", f"${cetes_dash['CARRY'].sum():,.2f}")
                k5.metric("Mejor carry", f"${cetes_dash['CARRY'].max():,.2f}")
                k6.metric("Peor carry", f"${cetes_dash['CARRY'].min():,.2f}")

                show_dataframe(
                    cetes_dash,
                    use_container_width=True,
                    hide_index=True,
                )

            with cetes_tabs[1]:
                st.plotly_chart(
                    cetes_curve_figure(cetes_dash),
                    use_container_width=True,
                    key="cetes_curve_main",
                )

                curve_metric = st.radio(
                    "Variable secundaria",
                    ["1 DIA", "DV0", "CARRY"],
                    horizontal=True,
                    key="cetes_curve_metric",
                )
                st.plotly_chart(
                    cetes_metric_figure(
                        cetes_dash,
                        curve_metric,
                        f"CETES · {curve_metric}",
                    ),
                    use_container_width=True,
                    key=f"cetes_metric_{curve_metric}",
                )

            with cetes_tabs[2]:
                left, right = st.columns(2)
                with left:
                    st.plotly_chart(
                        cetes_metric_figure(
                            cetes_dash,
                            "CARRY",
                            "Carry diario por CETE",
                        ),
                        use_container_width=True,
                        key="cetes_carry_bar",
                    )
                with right:
                    st.plotly_chart(
                        cetes_metric_figure(
                            cetes_dash,
                            "DV0",
                            "DV0 por CETE",
                        ),
                        use_container_width=True,
                        key="cetes_dv0_bar",
                    )

                show_dataframe(
                    cetes_dash[
                        [
                            "Serie",
                            "DiasPorVencer",
                            "Rendimiento",
                            "1 DIA",
                            "DV0",
                            "CARRY",
                            "DIAS_RECUP_DV0",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            with cetes_tabs[3]:
                ranking_metric = st.selectbox(
                    "Ordenar por",
                    ["CARRY", "DV0", "1 DIA", "Rendimiento"],
                    key="cetes_rank_metric",
                )
                ascending = st.toggle(
                    "Orden ascendente",
                    value=False,
                    key="cetes_rank_ascending",
                )
                ranked = cetes_dash.sort_values(
                    ranking_metric,
                    ascending=ascending,
                )

                top_count = st.slider(
                    "Número de CETES",
                    3,
                    min(20, len(ranked)),
                    min(10, len(ranked)),
                    key="cetes_rank_count",
                )
                show_dataframe(
                    ranked.head(top_count),
                    use_container_width=True,
                    hide_index=True,
                )


            with cetes_tabs[4]:
                try:
                    cetes_curve_cmp, _ = build_cetes_curve(
                        vector_path,
                        report_date,
                    )
                    m_zero = build_m_zero_curve(
                        vector_path,
                        report_date,
                    )

                    aligned = cetes_curve_cmp[
                        ["SERIE", "MATURITY", "TENOR_DAYS", "TENOR", "CETES"]
                    ].copy()
                    aligned["ZERO_M_INTERP"] = interpolate_curve_at_tenors(
                        m_zero["TENOR"],
                        m_zero["ZERO_M"],
                        aligned["TENOR"],
                    )
                    aligned["SPREAD_CETE_ZERO_M_PB"] = (
                        aligned["CETES"] - aligned["ZERO_M_INTERP"]
                    ) * 100

                    valid = aligned.dropna(subset=["ZERO_M_INTERP"])
                    st.plotly_chart(
                        zero_vs_cetes_figure(
                            valid.rename(columns={"SERIE": "SERIE_CETE"}),
                            float(aligned["TENOR"].max()),
                        ),
                        use_container_width=True,
                        key="cetes_dashboard_zero_compare",
                    )
                    show_dataframe(
                        aligned.rename(
                            columns={
                                "SERIE": "CETE",
                                "MATURITY": "Vencimiento",
                                "TENOR_DAYS": "Días",
                                "TENOR": "Años",
                                "CETES": "Rendimiento CETE (%)",
                                "ZERO_M_INTERP": "Cupón cero M interpolada (%)",
                                "SPREAD_CETE_ZERO_M_PB": "Spread CETE-cero M (pb)",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                except Exception as exc:
                    st.error(f"No fue posible comparar CETES contra cero M: {exc}")


with main_tabs[3]:
    render_pca(bonos, udis, report_date)

with main_tabs[4]:
    render_scanner(bonos, udis, report_date)

with main_tabs[5]:
    render_stability(bonos, udis, report_date)

with main_tabs[6]:
    st.subheader("Informe institucional | NEUTRINO Fixed Income")
    st.caption("Resumen ejecutivo, curvas, matrices y RV, estabilidad, PCA y semáforo, breakeven por Udibono, carry, préstamos teóricos y CETES. Se respetan las fórmulas de los motores existentes.")
    from institutional_report import build_report
    p1,p2,p3=st.columns(3)
    pdf_pca_window=p1.selectbox("Ventana PCA (cambios diarios)",[60,120,250,500],index=1,key="pdf_pca_window")
    pdf_pca_mode=p2.selectbox("Escalamiento PCA",["Covarianza (pb)","Correlación (estandarizado)"],key="pdf_pca_method")
    pdf_rv_window=p3.selectbox("Ventana RV (observaciones)",[30,60,120,250],index=2,key="pdf_rv_window")
    st.info("Las estadísticas históricas respetan la fecha elegida. El módulo de carry y las métricas de precios usan la fecha del vector disponible, que puede ser diferente.")
    if st.button("Generar reporte institucional PDF",type="primary",use_container_width=True):
        try:
            with st.spinner("Generando informe de mercado..."):
                out_dir=Path(tempfile.mkdtemp(prefix="neutrino_report_"))
                out_path=out_dir / f"NEUTRINO_REPORTE_{report_date:%Y%m%d}.pdf"
                build_report(bonos,udis,vector_path,out_path,report_date,
                    matrix_days=matrix_days,curve_days=curve_days,top_n=top_n,
                    funding=funding,amount=amount,pca_window=pdf_pca_window,
                    pca_mode=pdf_pca_mode,rv_window=pdf_rv_window)
                st.session_state["institutional_pdf_bytes"]=out_path.read_bytes()
                st.session_state["institutional_pdf_name"]=out_path.name
            st.success("Informe generado correctamente.")
        except Exception as exc:
            st.exception(exc)
    if "institutional_pdf_bytes" in st.session_state:
        st.download_button("Descargar informe PDF",data=st.session_state["institutional_pdf_bytes"],
            file_name=st.session_state["institutional_pdf_name"],mime="application/pdf",
            use_container_width=True)


st.markdown('<p class="small-note">Versión MVP · Los cálculos provienen del motor original del reporte.</p>', unsafe_allow_html=True)