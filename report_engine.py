# -*- coding: utf-8 -*-
r"""
REPORTE BONOS M 3.0 - PDF PREMIUM TK STYLE

Basado visual y metodologicamente en tu archivo BONOS M 3.0.py:
- Misma paleta dark/cyan/violet/green/amber.
- Misma funcion de gradiente get_gradient_color(ratio): rojo bajo, azul alto.
- Misma logica de matriz: spread = s1 - s2, Z = (ultimo-media)/std.
- Misma vista triangular inferior j < i de la matriz Tkinter.
- Graficas de historico e histograma con look tipo app original.

Incluye:
1) Portada premium tipo hedge fund terminal.
2) Resumen ejecutivo con KPIs.
3) Matriz SPREAD estilo Tk con ventana de 60 dias.
4) Matriz Z-SCORE estilo Tk con ventana de 60 dias.
5) Top 5 Z-scores mas extremos, rank 1-5.
6) Para cada par extremo: grafica historica + histograma.
7) Curva actual vs curva hace 30 dias + diferencia por serie.
8) Tabla de carry / fondeo Bonos M con tasa de fondeo configurable.
8b) Tasas equivalentes Bonos M a 1, 28 y 90 dias.
9) Opcionalmente repite el bloque para Udibonos si existe la base.

Instalacion:
    "C:/Users/car_j/AppData/Local/Microsoft/WindowsApps/python3.13.exe" -m pip install reportlab pandas numpy matplotlib scipy openpyxl pillow

Uso recomendado:
    & C:/Users/car_j/AppData/Local/Microsoft/WindowsApps/python3.13.exe c:/Users/car_j/Downloads/reporte_bonos_m_3_0_premium_tk_pdf.py --source-script "C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\BONOS M 3.0.py"

Uso directo:
    & C:/Users/car_j/AppData/Local/Microsoft/WindowsApps/python3.13.exe c:/Users/car_j/Downloads/reporte_bonos_m_3_0_premium_tk_pdf.py --bonos "C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\BASE M.xlsx" --udis "C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\base udis.xlsx"
"""
from __future__ import annotations

import argparse
import ast
import csv
import math
import unicodedata
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.dates import DateFormatter
from scipy import stats

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate, Flowable, Frame, Image, KeepTogether, PageBreak, PageTemplate,
        Paragraph, Spacer, Table, TableStyle
    )
except ModuleNotFoundError as e:
    print("ERROR: falta una libreria para generar PDF:", getattr(e, "name", "reportlab"))
    print("Instalala con este mismo Python:")
    print(f'  "{sys.executable}" -m pip install reportlab pandas numpy matplotlib scipy openpyxl pillow')
    raise SystemExit(1)

# -----------------------------------------------------------------------------
# Defaults del archivo original subido
# -----------------------------------------------------------------------------
DEFAULT_BONOS = r"C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\BASE M.xlsx"
DEFAULT_UDIS = r"C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\base udis.xlsx"
DEFAULT_TODAY = datetime(2025, 9, 17)
DEFAULT_VECTOR = r"C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\vector.csv"
DEFAULT_LF = r"C:\Users\car_j\OneDrive\Desktop\proyectos\PYTHON PROGRAMA\LF_PYTHON.csv"
FREQ = 182
DC = 360.0
NV = 100.0


# Paleta original Tk
BG_MAIN = "#020617"
BG_PANEL = "#050816"
BG_CARD = "#0b1220"
BG_HEADER = "#111827"
BG_MATRIX = "#020617"
FG_MAIN = "#e5e7eb"
FG_SOFT = "#9ca3af"
ACCENT_CYAN = "#22d3ee"
ACCENT_VIOLET = "#a855f7"
ACCENT_GREEN = "#22c55e"
ACCENT_AMBER = "#f59e0b"
ERR_RED = "#ef4444"
HIGHLIGHT_ROW_BG = "#1f2937"
GRID_LINE = "#1f2933"

# ReportLab colors
R_BG_MAIN = colors.HexColor(BG_MAIN)
R_BG_PANEL = colors.HexColor(BG_PANEL)
R_BG_CARD = colors.HexColor(BG_CARD)
R_BG_HEADER = colors.HexColor(BG_HEADER)
R_FG_MAIN = colors.HexColor(FG_MAIN)
R_FG_SOFT = colors.HexColor(FG_SOFT)
R_ACCENT_CYAN = colors.HexColor(ACCENT_CYAN)
R_ACCENT_VIOLET = colors.HexColor(ACCENT_VIOLET)
R_ACCENT_GREEN = colors.HexColor(ACCENT_GREEN)
R_ACCENT_AMBER = colors.HexColor(ACCENT_AMBER)
R_ERR_RED = colors.HexColor(ERR_RED)


@dataclass
class Dataset:
    name: str
    path: Path
    raw: pd.DataFrame
    pivot: pd.DataFrame
    last_date: pd.Timestamp


# -----------------------------------------------------------------------------
# Misma funcion visual del original: rojo para ratio bajo, azul para alto
# -----------------------------------------------------------------------------
def get_gradient_color(ratio):
    if ratio is None or pd.isna(ratio) or not np.isfinite(float(ratio)):
        return "#2b2b2b"
    ratio = max(0.0, min(1.0, float(ratio)))
    r = int(255 * (1 - ratio))
    g = 0
    b = int(255 * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def parse_literal_paths_from_script(script_path: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not script_path:
        return out
    p = Path(script_path)
    if not p.exists():
        return out
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"FILE_PATH", "FILE_PATH_UDI"}:
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            out[target.id] = node.value.value
    except Exception:
        pass
    return out


def parse_maturity(serie) -> Optional[pd.Timestamp]:
    serie_str = str(serie).strip()
    m = re.search(r"(\d{6})", serie_str)
    if not m:
        return None
    token = m.group(1)
    yy, mm, dd = int(token[:2]), int(token[2:4]), int(token[4:6])
    try:
        return pd.Timestamp(datetime(2000 + yy, mm, dd))
    except ValueError:
        return None


def tenor_years(serie, ref_date: pd.Timestamp) -> float:
    mat = parse_maturity(serie)
    if mat is None:
        return np.nan
    return (pd.Timestamp(mat) - pd.Timestamp(ref_date)).days / 365.25


def compact_series_order(series: Iterable, ref_date: pd.Timestamp) -> List[str]:
    def key(s):
        t = tenor_years(s, ref_date)
        if not np.isfinite(t):
            t = 9999
        return (t, str(s))
    return sorted([str(s) for s in series], key=key)


def normalize_date_column(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    if "fecha" not in df.columns:
        raise ValueError(f"{path.name}: falta columna 'fecha'.")
    if not pd.api.types.is_datetime64_any_dtype(df["fecha"]):
        tmp = pd.to_datetime(df["fecha"], errors="coerce")
        if tmp.isna().all():
            tmp = pd.to_timedelta(df["fecha"], unit="d") + pd.Timestamp("1899-12-30")
        df["fecha"] = tmp
    return df.dropna(subset=["fecha"]).copy()


def load_dataset(path: str, name: str) -> Dataset:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo de {name}: {p}")
    df = pd.read_excel(p, engine="openpyxl")
    df = normalize_date_column(df, p)
    missing = {"SERIE", "RENDIMIENTO"} - set(df.columns)
    if missing:
        raise ValueError(f"{p.name}: faltan columnas {sorted(missing)}")
    df["SERIE"] = df["SERIE"].astype(str).str.strip()
    df["RENDIMIENTO"] = pd.to_numeric(df["RENDIMIENTO"], errors="coerce")
    df = df.dropna(subset=["SERIE", "RENDIMIENTO"])
    pivot = df.pivot_table(index="fecha", columns="SERIE", values="RENDIMIENTO", aggfunc="last").sort_index()
    if pivot.empty:
        raise ValueError(f"{p.name}: no hay datos utiles.")
    return Dataset(name=name, path=p, raw=df, pivot=pivot, last_date=pd.Timestamp(pivot.index.max()))


def nearest_available_date(pivot: pd.DataFrame, target: pd.Timestamp) -> pd.Timestamp:
    idx = pd.DatetimeIndex(pivot.index).dropna().sort_values()
    if len(idx) == 0:
        raise ValueError("No hay fechas disponibles.")
    pos = idx.searchsorted(pd.Timestamp(target), side="right") - 1
    if pos < 0:
        pos = 0
    return pd.Timestamp(idx[pos])


def nearest_yield(yields: pd.Series, ref_date: pd.Timestamp, target_years: float) -> Tuple[float, Optional[str]]:
    best = (np.nan, None, np.inf)
    for s, val in yields.dropna().items():
        t = tenor_years(s, ref_date)
        if np.isfinite(t):
            d = abs(t - target_years)
            if d < best[2]:
                best = (float(val), str(s), d)
    return best[0], best[1]


# -----------------------------------------------------------------------------
# Calculos replicando el modulo matriz original
# -----------------------------------------------------------------------------
def compute_spread_matrices(ds: Dataset, start: pd.Timestamp, end: pd.Timestamp):
    start = nearest_available_date(ds.pivot, start)
    end = nearest_available_date(ds.pivot, end)
    if start > end:
        start, end = end, start
    df_filtrado = ds.pivot.loc[start:end].dropna(axis=1, how="all")
    cols = compact_series_order(df_filtrado.columns, end)
    df_filtrado = df_filtrado[cols]

    spread_matrix = pd.DataFrame(index=cols, columns=cols, dtype=float)
    zscore_matrix = pd.DataFrame(index=cols, columns=cols, dtype=float)
    color_ratio_spread = pd.DataFrame(index=cols, columns=cols, dtype=float)
    color_ratio_z = pd.DataFrame(index=cols, columns=cols, dtype=float)

    for s1 in cols:
        for s2 in cols:
            if s1 == s2:
                continue
            diff = (df_filtrado[s1] - df_filtrado[s2]).dropna()
            if diff.empty:
                continue
            last_spread = diff.iloc[-1]
            min_diff = diff.min()
            max_diff = diff.max()
            if pd.isna(min_diff) or pd.isna(max_diff) or max_diff == min_diff:
                spread_ratio = 0.5
            else:
                spread_ratio = (last_spread - min_diff) / (max_diff - min_diff)
            spread_matrix.loc[s1, s2] = float(last_spread)
            color_ratio_spread.loc[s1, s2] = float(spread_ratio)

            mean_diff = diff.mean()
            std_diff = diff.std()
            if pd.isna(std_diff) or std_diff == 0:
                last_z = np.nan
                z_ratio = np.nan
            else:
                z_series = (diff - mean_diff) / std_diff
                last_z = z_series.iloc[-1]
                z_min, z_max = z_series.min(), z_series.max()
                if pd.isna(z_min) or pd.isna(z_max) or z_max == z_min:
                    z_ratio = 0.5
                else:
                    z_ratio = (last_z - z_min) / (z_max - z_min)
            zscore_matrix.loc[s1, s2] = float(last_z) if pd.notna(last_z) else np.nan
            color_ratio_z.loc[s1, s2] = float(z_ratio) if pd.notna(z_ratio) else np.nan

    return spread_matrix, zscore_matrix, df_filtrado, color_ratio_spread, color_ratio_z, start, end


def best_pairs(zscore: pd.DataFrame, spread: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    rows = []
    cols = list(zscore.columns)
    # Solo triangular inferior, igual que update_matrix_grid j < i
    for i, s1 in enumerate(cols):
        for j, s2 in enumerate(cols):
            if j >= i:
                continue
            z = zscore.loc[s1, s2]
            sp = spread.loc[s1, s2]
            if pd.notna(z):
                rows.append({"PAR": f"{s1} - {s2}", "S1": s1, "S2": s2, "SPREAD": sp, "Z": z, "ABS_Z": abs(z)})
    if not rows:
        return pd.DataFrame(columns=["PAR", "S1", "S2", "SPREAD", "Z", "ABS_Z"])
    return pd.DataFrame(rows).sort_values("ABS_Z", ascending=False).head(top_n).reset_index(drop=True)


def pair_history(df_filtrado: pd.DataFrame, s1: str, s2: str) -> pd.DataFrame:
    diff = (df_filtrado[s1] - df_filtrado[s2]).dropna()
    return pd.DataFrame({"Fecha": diff.index, "Diferencia": diff.values}).dropna()


def compute_curve_table(ds: Dataset, date1: pd.Timestamp, date2: pd.Timestamp) -> Tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    d1 = nearest_available_date(ds.pivot, date1)
    d2 = nearest_available_date(ds.pivot, date2)
    y1 = ds.pivot.loc[d1].dropna()
    y2 = ds.pivot.loc[d2].dropna()
    rows = []
    for s in compact_series_order(set(y1.index) | set(y2.index), d1):
        t = tenor_years(s, d1)
        if not np.isfinite(t) or t <= 0:
            continue
        a = y1.get(s, np.nan)
        b = y2.get(s, np.nan)
        rows.append({
            "SERIE": str(s),
            "TENOR": t,
            "ACTUAL": float(a) if pd.notna(a) else np.nan,
            "HACE_30D": float(b) if pd.notna(b) else np.nan,
            "DIF": float(a - b) if pd.notna(a) and pd.notna(b) else np.nan,
        })
    return pd.DataFrame(rows), d1, d2


def curve_metrics(ds: Dataset, report_date: pd.Timestamp, comp_date: pd.Timestamp) -> Dict[str, float]:
    d1 = nearest_available_date(ds.pivot, report_date)
    y1 = ds.pivot.loc[d1].dropna()
    y2, _ = nearest_yield(y1, d1, 2.0)
    y5, _ = nearest_yield(y1, d1, 5.0)
    y10, _ = nearest_yield(y1, d1, 10.0)
    out = {
        "2Y": y2,
        "5Y": y5,
        "10Y": y10,
        "2s10s": y2 - y10 if np.isfinite(y2) and np.isfinite(y10) else np.nan,
        "5s10s": y5 - y10 if np.isfinite(y5) and np.isfinite(y10) else np.nan,
        "fly_2_5_10": 2*y5 - y2 - y10 if all(np.isfinite(v) for v in [y2, y5, y10]) else np.nan,
    }
    d2 = nearest_available_date(ds.pivot, comp_date)
    yc = ds.pivot.loc[d2].dropna()
    c2, _ = nearest_yield(yc, d2, 2.0)
    c5, _ = nearest_yield(yc, d2, 5.0)
    c10, _ = nearest_yield(yc, d2, 10.0)
    c_2s10s = c2 - c10 if np.isfinite(c2) and np.isfinite(c10) else np.nan
    c_5s10s = c5 - c10 if np.isfinite(c5) and np.isfinite(c10) else np.nan
    out["delta_2s10s"] = out["2s10s"] - c_2s10s if np.isfinite(out["2s10s"]) and np.isfinite(c_2s10s) else np.nan
    out["delta_5s10s"] = out["5s10s"] - c_5s10s if np.isfinite(out["5s10s"]) and np.isfinite(c_5s10s) else np.nan
    return out


# -----------------------------------------------------------------------------
# Charts con estilo app original
# -----------------------------------------------------------------------------
def _style_quant_ax(ax, title: str = ""):
    ax.set_facecolor(BG_MAIN)
    ax.tick_params(axis="both", colors=FG_MAIN, labelsize=9)
    for sp in ax.spines.values():
        sp.set_color(FG_SOFT)
    ax.grid(True, linestyle="--", alpha=0.22, color="#4b5563")
    if title:
        ax.set_title(title, fontsize=13, pad=12, color=FG_MAIN, fontweight="bold")


def add_terminal_header(fig, title: str, subtitle: str, mode: str, mode_color: str, status: str = "READY"):
    # Header similar al Tkinter original
    axh = fig.add_axes([0.02, 0.91, 0.96, 0.075])
    axh.set_axis_off()
    axh.add_patch(Rectangle((0, 0), 1, 1, transform=axh.transAxes, facecolor=BG_MAIN, edgecolor="none"))
    axh.text(0.015, 0.58, title, color=FG_MAIN, fontsize=17, fontweight="bold", va="center", ha="left")
    axh.text(0.015, 0.20, subtitle, color=ACCENT_CYAN, fontsize=8.5, family="monospace", va="center", ha="left")
    # badges
    axh.add_patch(FancyBboxPatch((0.70, 0.27), 0.13, 0.48, boxstyle="round,pad=0.015,rounding_size=0.02",
                                 facecolor=mode_color, edgecolor=mode_color, transform=axh.transAxes))
    axh.text(0.765, 0.51, mode, color=BG_MAIN, fontsize=8.5, fontweight="bold", family="monospace", ha="center", va="center")
    axh.add_patch(FancyBboxPatch((0.845, 0.27), 0.11, 0.48, boxstyle="round,pad=0.015,rounding_size=0.02",
                                 facecolor=BG_HEADER, edgecolor=GRID_LINE, transform=axh.transAxes))
    axh.text(0.90, 0.51, "ENGINE v1.0", color=FG_SOFT, fontsize=8, family="monospace", ha="center", va="center")
    axh.text(0.975, 0.52, "●", color=ACCENT_GREEN, fontsize=15, ha="right", va="center")
    axh.text(0.965, 0.52, status, color=FG_SOFT, fontsize=8, ha="right", va="center")


def save_tk_matrix_image(matrix: pd.DataFrame, ratio_matrix: pd.DataFrame, title: str, mode: str, mode_color: str,
                         dataset_name: str, start: pd.Timestamp, end: pd.Timestamp, path: Path, is_z: bool = False) -> Optional[Path]:
    if matrix.empty:
        return None
    cols = list(matrix.columns)
    rows = list(matrix.index)
    n = len(cols)
    if n == 0:
        return None

    # Figura suficientemente ancha para parecer screenshot de Tk
    cell = 0.48 if n <= 24 else max(0.28, 11 / n)
    fig_w = max(13, min(26, 2.8 + cell * (n + 1)))
    fig_h = max(8.5, min(21, 2.0 + cell * (n + 1)))
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=170)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, title, "> Cross-Sectional Spread Engine · Bonos / Udibonos", mode, mode_color)

    # Info cards
    axi = fig.add_axes([0.035, 0.835, 0.93, 0.055])
    axi.set_axis_off()
    axi.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012",
                                 facecolor=BG_PANEL, edgecolor=GRID_LINE, linewidth=1, transform=axi.transAxes))
    valid_pairs = int(np.isfinite(matrix.astype(float).values).sum() // 2)
    info = f"Rango: {start:%Y-%m-%d} a {end:%Y-%m-%d}     Diferencia en dias: {(end-start).days}     Series activas: {n} · Pares con datos: {valid_pairs} · Dataset: {dataset_name}"
    axi.text(0.015, 0.55, info, color=ACCENT_CYAN, fontsize=8.7, va="center", family="monospace")
    axi.text(0.015, 0.18, "Matriz estilo Tkinter: triangular inferior, headers cyan/violeta y gradiente original rojo-azul.", color=FG_SOFT, fontsize=7.3, va="center")

    # Matrix area
    ax = fig.add_axes([0.035, 0.105, 0.93, 0.705])
    ax.set_facecolor(BG_CARD)
    ax.set_xlim(0, n + 1)
    ax.set_ylim(n + 1, 0)
    ax.set_aspect("equal")
    ax.axis("off")

    # Border panel
    ax.add_patch(Rectangle((0, 0), n + 1, n + 1, facecolor=BG_MATRIX, edgecolor=ACCENT_CYAN, linewidth=1.2))

    # Header corner
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=BG_HEADER, edgecolor=GRID_LINE, linewidth=0.5))
    ax.text(0.5, 0.5, "SERIE", ha="center", va="center", color=FG_MAIN, fontsize=7.0, fontweight="bold")

    # Column headers
    for j, col in enumerate(cols):
        x = j + 1
        ax.add_patch(Rectangle((x, 0), 1, 1, facecolor=BG_HEADER, edgecolor=GRID_LINE, linewidth=0.5))
        ax.text(x + 0.5, 0.5, str(col), ha="center", va="center", rotation=90, color=ACCENT_CYAN, fontsize=6.3, fontweight="bold")

    # Row headers and cells
    for i, row in enumerate(rows):
        y = i + 1
        ax.add_patch(Rectangle((0, y), 1, 1, facecolor=BG_HEADER, edgecolor=GRID_LINE, linewidth=0.5))
        ax.text(0.5, y + 0.5, str(row), ha="center", va="center", color=ACCENT_VIOLET, fontsize=6.6, fontweight="bold")
        for j, col in enumerate(cols):
            x = j + 1
            if j < i:
                val = matrix.loc[row, col]
                if pd.notna(val):
                    ratio = ratio_matrix.loc[row, col]
                    fc = get_gradient_color(ratio)
                    txt = f"{float(val):.2f}" if is_z else f"{float(val):.4f}"
                    ax.add_patch(Rectangle((x, y), 1, 1, facecolor=fc, edgecolor=GRID_LINE, linewidth=0.45))
                    ax.text(x + 0.5, y + 0.5, txt, ha="center", va="center", color="#f9fafb", fontsize=5.8, family="monospace")
                else:
                    ax.add_patch(Rectangle((x, y), 1, 1, facecolor=BG_MATRIX, edgecolor=GRID_LINE, linewidth=0.25))
            else:
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor=BG_MATRIX, edgecolor=GRID_LINE, linewidth=0.20))

    # Legend like original
    axl = fig.add_axes([0.035, 0.035, 0.93, 0.045])
    axl.set_axis_off()
    axl.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.01",
                                 facecolor=BG_PANEL, edgecolor=GRID_LINE, linewidth=1, transform=axl.transAxes))
    axl.text(0.015, 0.5, "Heatmap (segun gradiente original):", color=FG_SOFT, fontsize=8, va="center")
    axl.add_patch(FancyBboxPatch((0.245, 0.22), 0.13, 0.56, boxstyle="round,pad=0.01,rounding_size=0.01",
                                 facecolor="#2563eb", edgecolor="#2563eb", transform=axl.transAxes))
    axl.text(0.31, 0.50, "Spread amplio (Azul)", color="#f9fafb", fontsize=7.2, family="monospace", ha="center", va="center")
    axl.add_patch(FancyBboxPatch((0.39, 0.22), 0.13, 0.56, boxstyle="round,pad=0.01,rounding_size=0.01",
                                 facecolor="#ef4444", edgecolor="#ef4444", transform=axl.transAxes))
    axl.text(0.455, 0.50, "Spread cerrado (Rojo)", color="#f9fafb", fontsize=7.2, family="monospace", ha="center", va="center")

    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_pair_timeseries(diff_df: pd.DataFrame, s1: str, s2: str, path: Path) -> Optional[Path]:
    if diff_df.empty:
        return None
    min_val = diff_df["Diferencia"].min()
    max_val = diff_df["Diferencia"].max()
    mean_val = diff_df["Diferencia"].mean()
    last_val = diff_df["Diferencia"].iloc[-1]
    sigma = diff_df["Diferencia"].std()
    z_last = (last_val - mean_val) / sigma if sigma and np.isfinite(sigma) else np.nan
    n_obs = len(diff_df)

    fig = plt.figure(figsize=(13.5, 7.2), dpi=160)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, f"SPREAD TIME SERIES: {s1} - {s2}", "> Spread vs tiempo · bandas ±1σ · ultimo valor y Z-Score", "MODE: HISTORIC", ACCENT_CYAN)

    # Stats bar
    axs = fig.add_axes([0.035, 0.825, 0.93, 0.06])
    axs.set_axis_off()
    axs.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012", facecolor=BG_PANEL, edgecolor=GRID_LINE, transform=axs.transAxes))
    stats_txt = f"N: {n_obs}     Min: {min_val:.4f}     Max: {max_val:.4f}     Media: {mean_val:.4f}     Ultimo: {last_val:.4f}     Z ultimo: {z_last:.2f}"
    axs.text(0.015, 0.50, stats_txt, color=ACCENT_CYAN, fontsize=9, family="monospace", va="center")

    ax = fig.add_axes([0.07, 0.12, 0.89, 0.66])
    _style_quant_ax(ax)
    y = diff_df["Diferencia"]
    x = diff_df["Fecha"]
    positive = y >= 0
    negative = y < 0
    ax.fill_between(x[positive], y[positive], 0, color=ACCENT_GREEN, alpha=0.55, label=f"{s1}-{s2} positivo")
    ax.fill_between(x[negative], y[negative], 0, color=ERR_RED, alpha=0.45, label=f"{s1}-{s2} negativo")
    ax.plot(x, y, color=ACCENT_CYAN, linewidth=1.2)
    ax.axhline(mean_val, color=ACCENT_CYAN, linestyle="--", linewidth=1.2, label="Media")
    if sigma and np.isfinite(sigma):
        ax.axhspan(mean_val - sigma, mean_val + sigma, facecolor="#1d4ed8", alpha=0.12, label="±1σ")
    ax.scatter([x.iloc[-1]], [last_val], color="yellow", s=50, zorder=5, label="Ultimo valor")
    ax.axvline(x.iloc[-1], color="yellow", linestyle=":", alpha=0.7)
    ttl = f"Spread {s1} - {s2}"
    if np.isfinite(z_last):
        ttl += f"   (Z ultimo = {z_last:.2f})"
    ax.set_title(ttl, fontsize=12, pad=10, color=FG_MAIN)
    ax.set_xlabel("Fecha", fontsize=10, color=FG_MAIN)
    ax.set_ylabel("Diferencia", fontsize=10, color=FG_MAIN)
    leg = ax.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=8)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)
    ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    if max_val != min_val:
        margin = 0.08 * (max_val - min_val)
        ax.set_ylim(min_val - margin, max_val + margin)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_pair_histogram(diff_df: pd.DataFrame, s1: str, s2: str, path: Path) -> Optional[Path]:
    if diff_df.empty:
        return None
    vals = diff_df["Diferencia"].dropna()
    mu = vals.mean()
    sigma = vals.std()
    last_val = vals.iloc[-1]
    z_last = (last_val - mu) / sigma if sigma and np.isfinite(sigma) else np.nan
    try:
        sk = stats.skew(vals, nan_policy="omit")
        kt = stats.kurtosis(vals, fisher=True, nan_policy="omit")
    except Exception:
        sk, kt = np.nan, np.nan

    fig = plt.figure(figsize=(13.5, 7.2), dpi=160)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, f"SPREAD DISTRIBUTION: {s1} - {s2}", "> Histograma + Normal(μ, σ) · bandas ±1σ, ±2σ, ±3σ", "MODE: HISTOGRAM", ACCENT_GREEN)

    axs = fig.add_axes([0.035, 0.825, 0.93, 0.06])
    axs.set_axis_off()
    axs.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012", facecolor=BG_PANEL, edgecolor=GRID_LINE, transform=axs.transAxes))
    stats_txt = f"N: {len(vals)}     μ: {mu:.4f}     σ: {sigma:.4f}     Ultimo: {last_val:.4f}     Z ultimo: {z_last:.2f}     Skew: {sk:.2f}     Kurtosis: {kt:.2f}"
    axs.text(0.015, 0.50, stats_txt, color=ACCENT_CYAN, fontsize=9, family="monospace", va="center")

    ax = fig.add_axes([0.07, 0.12, 0.89, 0.66])
    _style_quant_ax(ax)
    ax.hist(vals, bins=30, density=True, alpha=0.45, color=ACCENT_CYAN, label="Datos")
    if sigma and np.isfinite(sigma):
        x = np.linspace(mu - 4*sigma, mu + 4*sigma, 300)
        ax.plot(x, stats.norm.pdf(x, mu, sigma), "r-", lw=2, alpha=0.8, label="N(μ, σ)")
        ax.axvspan(mu - sigma, mu + sigma, facecolor=ACCENT_GREEN, alpha=0.09, label="±1σ")
        ax.axvspan(mu - 2*sigma, mu - sigma, facecolor=ACCENT_AMBER, alpha=0.06)
        ax.axvspan(mu + sigma, mu + 2*sigma, facecolor=ACCENT_AMBER, alpha=0.06)
        ax.axvspan(mu - 3*sigma, mu - 2*sigma, facecolor=ERR_RED, alpha=0.04)
        ax.axvspan(mu + 2*sigma, mu + 3*sigma, facecolor=ERR_RED, alpha=0.04)
        for k, col in zip([1, 2, 3], [ACCENT_GREEN, "#f97316", ERR_RED]):
            ax.axvline(mu + k*sigma, color=col, linestyle="-", alpha=0.5)
            ax.axvline(mu - k*sigma, color=col, linestyle="-", alpha=0.5)
    ax.axvline(last_val, color="yellow", linestyle="--", linewidth=1.4, label=f"Ultimo: {last_val:.4f}")
    if np.isfinite(z_last):
        ymax = ax.get_ylim()[1]
        ax.annotate(f"Z = {z_last:.2f}", xy=(last_val, 0), xytext=(last_val, ymax*0.85), ha="center", color="yellow", fontsize=9,
                    arrowprops=dict(facecolor="yellow", shrink=0.05, alpha=0.7))
    ax.set_title(f"Distribucion del Spread: {s1} - {s2}", fontsize=12, pad=10, color=FG_MAIN)
    ax.set_xlabel("Diferencia", fontsize=10, color=FG_MAIN)
    ax.set_ylabel("Densidad", fontsize=10, color=FG_MAIN)
    leg = ax.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=8)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_curve_terminal(curve: pd.DataFrame, title: str, path: Path, curve_days: int) -> Optional[Path]:
    if curve.empty:
        return None
    fig = plt.figure(figsize=(13.5, 7.2), dpi=160)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, title, f"> Yield Curve Lab MX · actual vs hace {curve_days} dias", "MODE: CURVE", ACCENT_CYAN)
    ax = fig.add_axes([0.07, 0.14, 0.58, 0.68])
    _style_quant_ax(ax)
    ax.plot(curve["TENOR"], curve["ACTUAL"], marker="o", linewidth=2.2, color=ACCENT_CYAN, label="Actual")
    if curve["HACE_30D"].notna().any():
        ax.plot(curve["TENOR"], curve["HACE_30D"], marker="o", linestyle="--", linewidth=1.8, color=ACCENT_AMBER, label=f"Hace {curve_days} dias")
    ax.set_title("Curva de rendimiento", color=FG_MAIN, fontsize=12, fontweight="bold")
    ax.set_xlabel("Tenor (años)", color=FG_MAIN)
    ax.set_ylabel("Rendimiento (%)", color=FG_MAIN)
    leg = ax.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=8)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)

    # panel tabla al lado derecho
    axt = fig.add_axes([0.68, 0.14, 0.28, 0.68])
    axt.set_axis_off()
    axt.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012", facecolor=BG_PANEL, edgecolor=GRID_LINE, transform=axt.transAxes))
    axt.text(0.05, 0.96, "Diferencia por serie", color=ACCENT_CYAN, fontsize=10, fontweight="bold", va="top")
    d = curve.dropna(subset=["DIF"]).copy().head(18)
    y0 = 0.88
    axt.text(0.05, y0, "SERIE", color=FG_SOFT, fontsize=7.5, fontweight="bold")
    axt.text(0.48, y0, "ACT", color=FG_SOFT, fontsize=7.5, fontweight="bold", ha="right")
    axt.text(0.70, y0, "30D", color=FG_SOFT, fontsize=7.5, fontweight="bold", ha="right")
    axt.text(0.94, y0, "DIF", color=FG_SOFT, fontsize=7.5, fontweight="bold", ha="right")
    for k, (_, r) in enumerate(d.iterrows()):
        y = y0 - 0.043*(k+1)
        row_bg = BG_CARD if k % 2 == 0 else BG_HEADER
        axt.add_patch(Rectangle((0.03, y-0.017), 0.94, 0.035, facecolor=row_bg, edgecolor=GRID_LINE, linewidth=0.3, transform=axt.transAxes))
        col = ACCENT_GREEN if r["DIF"] >= 0 else ERR_RED
        axt.text(0.05, y, str(r["SERIE"]), color=FG_MAIN, fontsize=7.0, va="center", family="monospace")
        axt.text(0.48, y, f"{r['ACTUAL']:.4f}", color=FG_MAIN, fontsize=7.0, va="center", ha="right", family="monospace")
        axt.text(0.70, y, f"{r['HACE_30D']:.4f}", color=FG_MAIN, fontsize=7.0, va="center", ha="right", family="monospace")
        axt.text(0.94, y, f"{r['DIF']:+.4f}", color=col, fontsize=7.0, va="center", ha="right", family="monospace")

    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_curve_diff_bars(curve: pd.DataFrame, title: str, path: Path, curve_days: int) -> Optional[Path]:
    d = curve.dropna(subset=["DIF"]).copy()
    if d.empty:
        return None
    fig = plt.figure(figsize=(13.5, 6.5), dpi=160)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, title, f"> Actual menos hace {curve_days} dias · barras por vencimiento", "MODE: DIFF", ACCENT_VIOLET)
    ax = fig.add_axes([0.07, 0.15, 0.89, 0.68])
    _style_quant_ax(ax)
    x = np.arange(len(d))
    bar_colors = [ACCENT_GREEN if v >= 0 else ERR_RED for v in d["DIF"]]
    ax.bar(x, d["DIF"], color=bar_colors, alpha=0.85)
    ax.axhline(0, color=FG_MAIN, linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(d["SERIE"], rotation=60, ha="right", color=FG_MAIN, fontsize=8)
    ax.set_ylabel("Diferencia de rendimiento", color=FG_MAIN)
    ax.set_title("Cambio de curva punto a punto", color=FG_MAIN, fontsize=12, fontweight="bold")
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# -----------------------------------------------------------------------------
# PDF helpers
# -----------------------------------------------------------------------------
def fmt(x, nd=4):
    try:
        if x is None or pd.isna(x) or not np.isfinite(float(x)):
            return "n/a"
        return f"{float(x):.{nd}f}"
    except Exception:
        return str(x)





# -----------------------------------------------------------------------------
# Breakeven inflation helpers
# -----------------------------------------------------------------------------
def interpolate_nominal_yield(nominal: pd.Series, ref_date: pd.Timestamp, target_tenor: float) -> float:
    pts = []
    for serie, y in nominal.dropna().items():
        t = tenor_years(serie, ref_date)
        if np.isfinite(t) and t > 0:
            pts.append((t, float(y)))
    if not pts:
        return np.nan
    pts = sorted(pts)
    xs = np.array([x for x, _ in pts], dtype=float)
    ys = np.array([y for _, y in pts], dtype=float)
    if len(xs) == 1:
        return float(ys[0])
    return float(np.interp(target_tenor, xs, ys))


def compute_breakeven_snapshot(bonos: Dataset, udis: Dataset, report_date: pd.Timestamp) -> Tuple[pd.DataFrame, pd.Timestamp]:
    common = sorted(set(bonos.pivot.index) & set(udis.pivot.index))
    if not common:
        return pd.DataFrame(), report_date
    idx = pd.DatetimeIndex(common)
    pos = idx.searchsorted(pd.Timestamp(report_date), side="right") - 1
    if pos < 0:
        pos = 0
    d = pd.Timestamp(idx[pos])
    nominal = bonos.pivot.loc[d].dropna()
    real = udis.pivot.loc[d].dropna()
    rows = []
    for udi_s, real_y in real.items():
        t = tenor_years(udi_s, d)
        if not np.isfinite(t) or t <= 0:
            continue
        nom_y = interpolate_nominal_yield(nominal, d, t)
        if not np.isfinite(nom_y):
            continue
        # Las bases historicas suelen traer RENDIMIENTO en porcentaje.
        be = ((1 + nom_y / 100.0) / (1 + float(real_y) / 100.0) - 1) * 100.0
        rows.append({
            "UDI": str(udi_s),
            "TENOR": t,
            "NOMINAL_INTERP": nom_y,
            "REAL": float(real_y),
            "BREAKEVEN": be,
        })
    return pd.DataFrame(rows).sort_values("TENOR").reset_index(drop=True), d


def breakeven_history(bonos: Dataset, udis: Dataset, udi_serie: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    common = sorted(set(bonos.pivot.index) & set(udis.pivot.index))
    if not common:
        return pd.DataFrame(columns=["Fecha", "BREAKEVEN"])
    idx = pd.DatetimeIndex(common)
    d0 = idx[idx.searchsorted(pd.Timestamp(start), side="left"):] if len(idx) else idx
    rows = []
    for d in d0:
        d = pd.Timestamp(d)
        if d > pd.Timestamp(end):
            break
        if udi_serie not in udis.pivot.columns:
            continue
        real_y = udis.pivot.loc[d].get(udi_serie, np.nan)
        if pd.isna(real_y):
            continue
        t = tenor_years(udi_serie, d)
        if not np.isfinite(t) or t <= 0:
            continue
        nom_y = interpolate_nominal_yield(bonos.pivot.loc[d].dropna(), d, t)
        if not np.isfinite(nom_y):
            continue
        be = ((1 + nom_y / 100.0) / (1 + float(real_y) / 100.0) - 1) * 100.0
        rows.append({"Fecha": d, "BREAKEVEN": be})
    return pd.DataFrame(rows).dropna()


def compute_breakeven_extremes(bonos: Dataset, udis: Dataset, report_date: pd.Timestamp, window_days: int, top_n: int = 3) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], pd.Timestamp, pd.Timestamp]:
    be_now, d = compute_breakeven_snapshot(bonos, udis, report_date)
    if be_now.empty:
        return pd.DataFrame(), {}, d, d
    start = nearest_available_date(bonos.pivot, d - pd.Timedelta(days=window_days))
    histories: Dict[str, pd.DataFrame] = {}
    rows = []
    for _, r in be_now.iterrows():
        serie = str(r["UDI"])
        hist = breakeven_history(bonos, udis, serie, start, d)
        histories[serie] = hist
        if hist.empty or len(hist) < 5:
            z = np.nan
            mu = np.nan
            sigma = np.nan
        else:
            mu = hist["BREAKEVEN"].mean()
            sigma = hist["BREAKEVEN"].std()
            last = hist["BREAKEVEN"].iloc[-1]
            z = (last - mu) / sigma if sigma and np.isfinite(sigma) else np.nan
        rows.append({
            "UDI": serie,
            "TENOR": r["TENOR"],
            "BREAKEVEN": r["BREAKEVEN"],
            "MEAN": mu,
            "STD": sigma,
            "Z": z,
            "ABS_Z": abs(z) if pd.notna(z) else np.nan,
        })
    out = pd.DataFrame(rows)
    out = out.sort_values("ABS_Z", ascending=False).head(top_n).reset_index(drop=True)
    return out, histories, start, d


def save_breakeven_snapshot_image(be: pd.DataFrame, title: str, path: Path) -> Optional[Path]:
    if be.empty:
        return None
    fig = plt.figure(figsize=(13.5, 7.2), dpi=160)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, title, "> Breakeven Inflation Monitor · nominal interpolado vs real", "MODE: BE", ACCENT_VIOLET)

    ax = fig.add_axes([0.07, 0.18, 0.58, 0.64])
    _style_quant_ax(ax)
    ax.plot(be["TENOR"], be["BREAKEVEN"], marker="o", linewidth=2.2, color=ACCENT_CYAN)
    ax.fill_between(be["TENOR"], be["BREAKEVEN"], be["BREAKEVEN"].mean(), color=ACCENT_CYAN, alpha=0.10)
    ax.axhline(be["BREAKEVEN"].mean(), color=ACCENT_AMBER, linestyle="--", linewidth=1.2, label="Promedio")
    ax.set_title("Todos los breakevens", color=FG_MAIN, fontsize=12, fontweight="bold")
    ax.set_xlabel("Tenor (años)", color=FG_MAIN)
    ax.set_ylabel("Breakeven (%)", color=FG_MAIN)
    leg = ax.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=8)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)

    axt = fig.add_axes([0.68, 0.18, 0.28, 0.64])
    axt.set_axis_off()
    axt.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012", facecolor=BG_PANEL, edgecolor=GRID_LINE, transform=axt.transAxes))
    axt.text(0.05, 0.96, "Tabla BE", color=ACCENT_CYAN, fontsize=10, fontweight="bold", va="top")
    d = be.sort_values("TENOR").head(18)
    y0 = 0.88
    axt.text(0.05, y0, "UDI", color=FG_SOFT, fontsize=7.5, fontweight="bold")
    axt.text(0.45, y0, "TENOR", color=FG_SOFT, fontsize=7.5, fontweight="bold", ha="right")
    axt.text(0.68, y0, "REAL", color=FG_SOFT, fontsize=7.5, fontweight="bold", ha="right")
    axt.text(0.94, y0, "BE", color=FG_SOFT, fontsize=7.5, fontweight="bold", ha="right")
    for k, (_, r) in enumerate(d.iterrows()):
        y = y0 - 0.043*(k+1)
        row_bg = BG_CARD if k % 2 == 0 else BG_HEADER
        axt.add_patch(Rectangle((0.03, y-0.017), 0.94, 0.035, facecolor=row_bg, edgecolor=GRID_LINE, linewidth=0.3, transform=axt.transAxes))
        axt.text(0.05, y, str(r["UDI"]), color=FG_MAIN, fontsize=7.0, va="center", family="monospace")
        axt.text(0.45, y, f"{r['TENOR']:.2f}", color=FG_MAIN, fontsize=7.0, va="center", ha="right", family="monospace")
        axt.text(0.68, y, f"{r['REAL']:.4f}", color=FG_MAIN, fontsize=7.0, va="center", ha="right", family="monospace")
        axt.text(0.94, y, f"{r['BREAKEVEN']:.4f}", color=ACCENT_GREEN, fontsize=7.0, va="center", ha="right", family="monospace")
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_be_histogram(hist: pd.DataFrame, serie: str, zrow: pd.Series, path: Path) -> Optional[Path]:
    if hist.empty:
        return None
    vals = hist["BREAKEVEN"].dropna()
    if vals.empty:
        return None
    mu = vals.mean()
    sigma = vals.std()
    last_val = vals.iloc[-1]
    z_last = (last_val - mu) / sigma if sigma and np.isfinite(sigma) else np.nan

    fig = plt.figure(figsize=(13.5, 6.8), dpi=160)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, f"BREAKEVEN HISTOGRAM: {serie}", "> Distribucion historica del breakeven · top extremo por |Z|", "MODE: BE HIST", ACCENT_GREEN)

    axs = fig.add_axes([0.035, 0.805, 0.93, 0.065])
    axs.set_axis_off()
    axs.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012", facecolor=BG_PANEL, edgecolor=GRID_LINE, transform=axs.transAxes))
    stats_txt = f"UDI: {serie}     BE actual: {last_val:.4f}     Media: {mu:.4f}     Std: {sigma:.4f}     Z: {z_last:.2f}     Tenor: {zrow.get('TENOR', np.nan):.2f}a"
    axs.text(0.015, 0.50, stats_txt, color=ACCENT_CYAN, fontsize=9, family="monospace", va="center")

    ax1 = fig.add_axes([0.07, 0.13, 0.52, 0.62])
    _style_quant_ax(ax1)
    ax1.plot(hist["Fecha"], hist["BREAKEVEN"], color=ACCENT_CYAN, linewidth=1.4)
    ax1.axhline(mu, color=ACCENT_CYAN, linestyle="--", linewidth=1.1, label="Media")
    if sigma and np.isfinite(sigma):
        ax1.axhspan(mu - sigma, mu + sigma, facecolor="#1d4ed8", alpha=0.12, label="±1σ")
    ax1.scatter([hist["Fecha"].iloc[-1]], [last_val], color="yellow", s=45, zorder=5)
    ax1.set_title("Serie historica del breakeven", color=FG_MAIN, fontsize=11, fontweight="bold")
    ax1.set_xlabel("Fecha", color=FG_MAIN)
    ax1.set_ylabel("BE (%)", color=FG_MAIN)
    ax1.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
    leg = ax1.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=8)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)

    ax2 = fig.add_axes([0.66, 0.13, 0.30, 0.62])
    _style_quant_ax(ax2)
    ax2.hist(vals, bins=25, density=True, alpha=0.45, color=ACCENT_CYAN, label="Datos")
    if sigma and np.isfinite(sigma):
        xs = np.linspace(mu - 4*sigma, mu + 4*sigma, 250)
        ax2.plot(xs, stats.norm.pdf(xs, mu, sigma), "r-", lw=1.8, alpha=0.85, label="N(μ,σ)")
        ax2.axvspan(mu - sigma, mu + sigma, facecolor=ACCENT_GREEN, alpha=0.09)
        for k, col in zip([1, 2, 3], [ACCENT_GREEN, "#f97316", ERR_RED]):
            ax2.axvline(mu + k*sigma, color=col, linestyle="-", alpha=0.5)
            ax2.axvline(mu - k*sigma, color=col, linestyle="-", alpha=0.5)
    ax2.axvline(last_val, color="yellow", linestyle="--", linewidth=1.4, label=f"Ultimo {last_val:.2f}")
    ax2.set_title("Histograma", color=FG_MAIN, fontsize=11, fontweight="bold")
    ax2.set_xlabel("BE (%)", color=FG_MAIN)
    ax2.set_ylabel("Densidad", color=FG_MAIN)
    leg = ax2.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=8)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)

    fig.autofmt_xdate()
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_pair_combo(diff_df: pd.DataFrame, s1: str, s2: str, path: Path) -> Optional[Path]:
    """Una sola imagen con grafica historica e histograma en la misma hoja."""
    if diff_df.empty:
        return None
    vals = diff_df["Diferencia"].dropna()
    if vals.empty:
        return None
    min_val = vals.min()
    max_val = vals.max()
    mean_val = vals.mean()
    last_val = vals.iloc[-1]
    sigma = vals.std()
    z_last = (last_val - mean_val) / sigma if sigma and np.isfinite(sigma) else np.nan
    try:
        sk = stats.skew(vals, nan_policy="omit")
        kt = stats.kurtosis(vals, fisher=True, nan_policy="omit")
    except Exception:
        sk, kt = np.nan, np.nan

    fig = plt.figure(figsize=(13.5, 7.4), dpi=165)
    fig.patch.set_facecolor(BG_MAIN)
    add_terminal_header(fig, f"PAIR EXTREME: {s1} - {s2}", "> Spread historico + histograma en una sola hoja", "MODE: PAIR", ACCENT_CYAN)

    axs = fig.add_axes([0.035, 0.815, 0.93, 0.065])
    axs.set_axis_off()
    axs.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.01,rounding_size=0.012", facecolor=BG_PANEL, edgecolor=GRID_LINE, transform=axs.transAxes))
    stats_txt = f"N: {len(vals)}     Min: {min_val:.4f}     Max: {max_val:.4f}     Media: {mean_val:.4f}     Ultimo: {last_val:.4f}     Z: {z_last:.2f}     Skew: {sk:.2f}     Kurtosis: {kt:.2f}"
    axs.text(0.015, 0.50, stats_txt, color=ACCENT_CYAN, fontsize=8.8, family="monospace", va="center")

    ax1 = fig.add_axes([0.06, 0.13, 0.56, 0.63])
    _style_quant_ax(ax1)
    y = diff_df["Diferencia"]
    x = diff_df["Fecha"]
    positive = y >= 0
    negative = y < 0
    ax1.fill_between(x[positive], y[positive], 0, color=ACCENT_GREEN, alpha=0.55, label="Positivo")
    ax1.fill_between(x[negative], y[negative], 0, color=ERR_RED, alpha=0.45, label="Negativo")
    ax1.plot(x, y, color=ACCENT_CYAN, linewidth=1.2)
    ax1.axhline(mean_val, color=ACCENT_CYAN, linestyle="--", linewidth=1.1, label="Media")
    if sigma and np.isfinite(sigma):
        ax1.axhspan(mean_val - sigma, mean_val + sigma, facecolor="#1d4ed8", alpha=0.12, label="±1σ")
    ax1.scatter([x.iloc[-1]], [last_val], color="yellow", s=48, zorder=5, label="Ultimo")
    ax1.axvline(x.iloc[-1], color="yellow", linestyle=":", alpha=0.7)
    ax1.set_title(f"Historico del spread", fontsize=11.5, pad=10, color=FG_MAIN, fontweight="bold")
    ax1.set_xlabel("Fecha", fontsize=9.5, color=FG_MAIN)
    ax1.set_ylabel("Diferencia", fontsize=9.5, color=FG_MAIN)
    ax1.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
    leg = ax1.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=7.5)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)
    if max_val != min_val:
        margin = 0.08 * (max_val - min_val)
        ax1.set_ylim(min_val - margin, max_val + margin)

    ax2 = fig.add_axes([0.68, 0.13, 0.28, 0.63])
    _style_quant_ax(ax2)
    ax2.hist(vals, bins=30, density=True, alpha=0.45, color=ACCENT_CYAN, label="Datos")
    if sigma and np.isfinite(sigma):
        xs = np.linspace(mean_val - 4*sigma, mean_val + 4*sigma, 280)
        ax2.plot(xs, stats.norm.pdf(xs, mean_val, sigma), "r-", lw=1.9, alpha=0.85, label="N(μ,σ)")
        ax2.axvspan(mean_val - sigma, mean_val + sigma, facecolor=ACCENT_GREEN, alpha=0.09, label="±1σ")
        ax2.axvspan(mean_val - 2*sigma, mean_val - sigma, facecolor=ACCENT_AMBER, alpha=0.06)
        ax2.axvspan(mean_val + sigma, mean_val + 2*sigma, facecolor=ACCENT_AMBER, alpha=0.06)
        for k, col in zip([1, 2, 3], [ACCENT_GREEN, "#f97316", ERR_RED]):
            ax2.axvline(mean_val + k*sigma, color=col, linestyle="-", alpha=0.5)
            ax2.axvline(mean_val - k*sigma, color=col, linestyle="-", alpha=0.5)
    ax2.axvline(last_val, color="yellow", linestyle="--", linewidth=1.4, label="Ultimo")
    ax2.set_title("Histograma", fontsize=11.5, pad=10, color=FG_MAIN, fontweight="bold")
    ax2.set_xlabel("Diferencia", fontsize=9.5, color=FG_MAIN)
    ax2.set_ylabel("Densidad", fontsize=9.5, color=FG_MAIN)
    leg = ax2.legend(facecolor=BG_MAIN, edgecolor="#4b5563", fontsize=7.5)
    for t in leg.get_texts():
        t.set_color(FG_MAIN)

    fig.autofmt_xdate()
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path



# -----------------------------------------------------------------------------
# Tabla Bonos M - Carry / Fondeo tomada del algoritmo Futuristic Quant FI Engine
# -----------------------------------------------------------------------------
def serie_to_date_bono(serie):
    s = str(int(float(serie))).zfill(6)
    return date(2000 + int(s[:2]), int(s[2:4]), int(s[4:6]))


def P_bono2(sett, maturity, nv, coupon, yld, coup_freq, clean, coup_freq1, coup_freq2):
    coupon /= 100
    yld /= 100
    C = nv * coup_freq * coupon / 360
    c1 = nv * coup_freq1 * coupon / 360
    c2 = nv * coup_freq2 * coupon / 360
    r = yld * coup_freq / 360
    k = (maturity - sett).days
    m = k % coup_freq
    k = (k - m) / coup_freq - 1
    m = m + (coup_freq - coup_freq2)
    k2 = ((coup_freq2 - coup_freq) + coup_freq) / coup_freq + k
    if r == 0:
        return nv
    a = C * ((1 / r) - (1 / (r * (1 + r) ** k)))
    b = nv / (1 + r) ** k2
    d = (1 + r) ** (m / coup_freq)
    e = c2 / (1 + r) ** k2
    ia = c1 * (1 - m / coup_freq1)
    p = (a + b + e) / d + c1 / d - clean * ia
    return p - ia if m == 0 else p


def coupon_schedule(sett, maturity, freq=FREQ):
    d = maturity
    dates = []
    while d > sett:
        dates.append(d)
        d = d - timedelta(days=freq)
    dates.sort()
    return dates


def cashflows(sett, maturity, coupon_pct, nv=NV, freq=FREQ, dc=DC):
    C = nv * (coupon_pct / 100.0) * (freq / dc)
    pays = coupon_schedule(sett, maturity, freq)
    flows = []
    for i, dt in enumerate(pays):
        t = (dt - sett).days
        cf = C + (nv if i == len(pays) - 1 else 0.0)
        flows.append((t, cf))
    return flows


def loglin_df(curve, t):
    if t in curve:
        return curve[t]
    xs = sorted(curve.keys())
    if len(xs) < 2:
        return 1.0
    if t <= xs[0]:
        x0, x1 = xs[0], xs[1]
    elif t >= xs[-1]:
        x0, x1 = xs[-2], xs[-1]
    else:
        x0 = max(x for x in xs if x < t)
        x1 = min(x for x in xs if x > t)
    df0, df1 = curve[x0], curve[x1]
    w = (t - x0) / (x1 - x0)
    return float(math.exp((1 - w) * math.log(df0) + w * math.log(df1)))


def bootstrap_curve_and_zero_map(sett, instruments):
    inst = sorted(instruments, key=lambda x: x["maturity"])
    curve = {0: 1.0}
    out = {}
    for it in inst:
        maturity = it["maturity"]
        coup = float(it["coupon_pct"])
        P = float(it["priceP48"])
        fl = cashflows(sett, maturity, coup)
        if not fl:
            out[it["iid"]] = None
            continue
        pv_known = 0.0
        for t, cf in fl[:-1]:
            pv_known += cf * loglin_df(curve, t)
        T, CF_T = fl[-1]
        DF_T = (P - pv_known) / CF_T if CF_T != 0 else None
        if DF_T is None or DF_T <= 0:
            out[it["iid"]] = None
            continue
        curve[T] = float(DF_T)
        z = (1.0 / DF_T - 1.0) * (DC / T)
        out[it["iid"]] = 100.0 * z
    return out, curve


def compute_carry_row(maturity, y, c, monto, tasa_fondeo_decimal):
    fecha48 = date.today() + timedelta(days=2)
    fecha72 = date.today() + timedelta(days=3)
    p48 = P_bono2(fecha48, maturity, 100, c, y, 182, 0, 182, 182)
    p72 = P_bono2(fecha72, maturity, 100, c, y, 182, 0, 182, 182)
    p_dn = P_bono2(fecha48, maturity, 100, c, y - 0.01, 182, 0, 182, 182)
    dv01 = (p_dn - p48) * monto / 100
    theta = (p72 - p48) * monto / 100
    costo = (p48 * tasa_fondeo_decimal / 360) * monto / 100
    carry = theta - costo
    prest = (carry / dv01) * 1000 if dv01 != 0 else 0
    tasa1d = ((p72 / p48) - 1) * 360 * 100
    dias_recup_1pb = (dv01 / carry) if abs(carry) > 1e-12 else np.nan
    return p48, dv01, theta, costo, carry, dias_recup_1pb, prest, tasa1d


def load_carry_table(vector_path: Optional[str], funding_rate_pct: float = 6.50, monto: float = 10_000_000) -> pd.DataFrame:
    if not vector_path:
        return pd.DataFrame()
    p = Path(vector_path)
    if not p.exists():
        return pd.DataFrame()

    # vector.csv suele venir en latin1/cp1252; probamos varios encodings.
    last_err = None
    df = None
    for enc in ("latin1", "cp1252", "utf-8-sig", "utf-8"):
        try:
            df = pd.read_csv(p, encoding=enc)
            break
        except Exception as e:
            last_err = e
    if df is None:
        raise last_err

    need = ["TV", "Serie", "Rendimiento", "TasaCuponVigente"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        return pd.DataFrame()
    dfm = df[df["TV"].astype(str).str.strip().str.upper() == "M"].copy()
    if dfm.empty:
        return pd.DataFrame()
    dfm = dfm.dropna(subset=["Serie", "Rendimiento", "TasaCuponVigente"])

    rows = []
    instruments = []
    tasa_fondeo = funding_rate_pct / 100.0
    fecha48 = date.today() + timedelta(days=2)
    for _, r in dfm.iterrows():
        try:
            serie = str(int(float(r["Serie"]))).zfill(6)
            maturity = serie_to_date_bono(serie)
            y = float(r["Rendimiento"])
            c = float(r["TasaCuponVigente"]) * 100.0
            p48, dv01, theta, costo, carry, dias, prest, tasa1d = compute_carry_row(maturity, y, c, monto, tasa_fondeo)
            iid = serie
            rows.append({
                "Serie": serie,
                "Rend (%)": y,
                "Cupón (%)": c,
                "DV01": dv01,
                "Theta": theta,
                "Costo Fondeo": costo,
                "Carry": carry,
                "Dias recup 1pb": dias,
                "Préstamo Teórico": prest,
                "Tasa 1 Día (%)": tasa1d,
                "_iid": iid,
                "_maturity": maturity,
                "_coupon": c,
                "_p48": p48,
            })
            instruments.append({"iid": iid, "maturity": maturity, "coupon_pct": c, "priceP48": p48})
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("_maturity")
    zero_map, _ = bootstrap_curve_and_zero_map(fecha48, instruments)
    out["Cupo Zero (%)"] = out["_iid"].map(lambda x: zero_map.get(x, np.nan))
    cols = ["Serie", "Rend (%)", "Cupón (%)", "Cupo Zero (%)", "DV01", "Theta", "Costo Fondeo", "Carry", "Dias recup 1pb", "Préstamo Teórico", "Tasa 1 Día (%)"]
    return out[cols]


def _font_heat_color(value, vmin, vmax):
    # Paleta discreta del archivo de tabla: rojo -> amarillo -> verde, aplicada SOLO al texto.
    if pd.isna(value):
        return FG_SOFT
    if vmax == vmin:
        t = 0.5
    else:
        t = max(0.0, min(1.0, (float(value) - float(vmin)) / (float(vmax) - float(vmin))))
    if t <= 0.5:
        u = t / 0.5
        r0, g0, b0 = 239, 68, 68
        r1, g1, b1 = 250, 204, 21
    else:
        u = (t - 0.5) / 0.5
        r0, g0, b0 = 250, 204, 21
        r1, g1, b1 = 34, 197, 94
    r = int(r0 + (r1 - r0) * u)
    g = int(g0 + (g1 - g0) * u)
    b = int(b0 + (b1 - b0) * u)
    return f"#{r:02x}{g:02x}{b:02x}"


def save_carry_table_image(carry: pd.DataFrame, funding_rate_pct: float, path: Path) -> Optional[Path]:
    if carry is None or carry.empty:
        return None
    cols = list(carry.columns)
    n = len(carry)
    fig_w = 23.5
    fig_h = max(5.5, min(13.5, 2.1 + 0.44 * (n + 1)))
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=180)
    fig.patch.set_facecolor("#070A12")

    # Header tipo app nueva
    axh = fig.add_axes([0.02, 0.875, 0.96, 0.11])
    axh.set_axis_off()
    axh.add_patch(Rectangle((0, 0), 1, 1, transform=axh.transAxes, facecolor="#070A12", edgecolor="none"))
    axh.text(0.015, 0.62, "⚡ QUANT FIXED INCOME ENGINE — BONOS M", color="#38bdf8", fontsize=18, fontweight="bold", family="monospace", va="center")
    axh.text(0.015, 0.22, f"> Carry / Theta / DV01 / Costo fondeo · Monto: 10,000,000 · Tasa fondeo: {funding_rate_pct:.2f}%", color="#94a3b8", fontsize=9.2, family="monospace", va="center")
    axh.text(0.965, 0.58, "● OK", color="#22c55e", fontsize=10, family="monospace", ha="right", va="center")

    ax = fig.add_axes([0.02, 0.045, 0.96, 0.81])
    ax.set_axis_off()
    ax.set_facecolor("#070A12")

    # widths relativos estilo dos treeviews: última columna destacada
    widths = np.array([1.05, .95, .95, 1.12, 1.15, 1.15, 1.28, 1.15, 1.35, 1.45, 1.18], dtype=float)
    widths = widths / widths.sum()
    x_edges = np.concatenate([[0], np.cumsum(widths)])
    row_h = 1.0 / (n + 1)

    # header
    for j, col in enumerate(cols):
        x0 = x_edges[j]
        w = widths[j]
        ax.add_patch(Rectangle((x0, 1 - row_h), w, row_h, transform=ax.transAxes, facecolor="#0f1730", edgecolor="#1f2933", linewidth=0.7))
        ax.text(x0 + w/2, 1 - row_h/2, col, transform=ax.transAxes, ha="center", va="center", color="#38bdf8", fontsize=7.6, fontweight="bold", family="monospace")

    vmin = carry["Tasa 1 Día (%)"].min(skipna=True)
    vmax = carry["Tasa 1 Día (%)"].max(skipna=True)
    for i, (_, r) in enumerate(carry.iterrows()):
        y0 = 1 - (i + 2) * row_h
        bg = "#0b1020" if i % 2 == 0 else "#0f1730"
        for j, col in enumerate(cols):
            x0 = x_edges[j]
            w = widths[j]
            ax.add_patch(Rectangle((x0, y0), w, row_h, transform=ax.transAxes, facecolor=bg, edgecolor="#111827", linewidth=0.45))
            val = r[col]
            if col == "Serie":
                txt = str(val)
            elif col in ["Rend (%)", "Cupón (%)", "Cupo Zero (%)", "Tasa 1 Día (%)"]:
                txt = "—" if pd.isna(val) else f"{float(val):,.4f}" if col != "Tasa 1 Día (%)" else f"{float(val):,.3f}"
            elif col == "Dias recup 1pb":
                txt = "—" if pd.isna(val) else f"{float(val):,.2f}"
            else:
                txt = "—" if pd.isna(val) else f"{float(val):,.2f}"
            color = _font_heat_color(val, vmin, vmax) if col == "Tasa 1 Día (%)" else "#e5e7eb"
            ax.text(x0 + w/2, y0 + row_h/2, txt, transform=ax.transAxes, ha="center", va="center", color=color, fontsize=7.15, family="monospace")

    # marco exterior
    ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor="none", edgecolor="#38bdf8", linewidth=1.0))
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# -----------------------------------------------------------------------------
# Tabla Bonos M - Tasas equivalentes por horizonte 1D / 28D / 90D
# -----------------------------------------------------------------------------
def load_bonos_equivalent_rate_table(vector_path: Optional[str]) -> pd.DataFrame:
    """
    Convierte el rendimiento anual de Bonos M a tasas anualizadas equivalentes
    para horizontes de 1, 28 y 90 dias usando la base de cupon de 182 dias.

    Correccion importante:
    - NO usa retorno de precio P_h/P_0 anualizado. Eso mezcla devengamiento,
      rolldown/cupon y puede inflar artificialmente la tasa de horizontes cortos.
    - Usa equivalencia de tasa nominal con periodo de 182 dias:

        eq_h = ((1 + y * 182/360) ** (h/182) - 1) * (360/h)

      donde y es el rendimiento anual en decimal y h es 1, 28 o 90 dias.
    - Para h = 182, la tasa equivalente regresa exactamente al rendimiento original.
    - Para h < 182 y tasas positivas, normalmente queda ligeramente debajo del
      rendimiento anual original, que es lo esperado.
    """
    if not vector_path:
        return pd.DataFrame()
    p = Path(vector_path)
    if not p.exists():
        return pd.DataFrame()

    df = None
    last_err = None
    for enc in ("latin1", "cp1252", "utf-8-sig", "utf-8"):
        try:
            df = pd.read_csv(p, encoding=enc, low_memory=False)
            break
        except Exception as e:
            last_err = e
    if df is None:
        raise last_err

    df.columns = [str(c).strip() for c in df.columns]
    need = ["TV", "Serie", "Rendimiento", "TasaCuponVigente"]
    if any(c not in df.columns for c in need):
        return pd.DataFrame()

    dfm = df[df["TV"].astype(str).str.strip().str.upper() == "M"].copy()
    dfm = dfm.dropna(subset=["Serie", "Rendimiento", "TasaCuponVigente"])
    if dfm.empty:
        return pd.DataFrame()

    sett0 = date.today() + timedelta(days=2)
    horizons = [1, 28, 90]
    rows = []

    def bono_equiv_rate_182(y_pct: float, h: int) -> float:
        """Tasa anualizada equivalente del rendimiento nominal base cupón 182d."""
        if h <= 0 or not np.isfinite(y_pct):
            return np.nan
        y_dec = y_pct / 100.0
        periodic_182 = 1.0 + y_dec * (182.0 / 360.0)
        if periodic_182 <= 0:
            return np.nan
        eq_dec = (periodic_182 ** (h / 182.0) - 1.0) * (360.0 / h)
        return eq_dec * 100.0

    for _, r in dfm.iterrows():
        try:
            serie = str(int(float(r["Serie"]))).zfill(6)
            maturity = serie_to_date_bono(serie)
            y = float(r["Rendimiento"])
            c = float(r["TasaCuponVigente"]) * 100.0
            row = {
                "Serie": serie,
                "Plazo días": max((maturity - sett0).days, 0),
                "Rend (%)": y,
                "Cupón (%)": c,
            }
            for h in horizons:
                if (maturity - sett0).days <= 0:
                    row[f"Eq {h}D (%)"] = np.nan
                else:
                    row[f"Eq {h}D (%)"] = bono_equiv_rate_182(y, h)
            rows.append(row)
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("Plazo días")
    return out[["Serie", "Plazo días", "Rend (%)", "Cupón (%)", "Eq 1D (%)", "Eq 28D (%)", "Eq 90D (%)"]]


def save_bonos_equiv_rate_table_image(eq: pd.DataFrame, path: Path) -> Optional[Path]:
    if eq is None or eq.empty:
        return None

    # Tabla amable: columnas amplias, notas simples y colores por nivel de tasa.
    cols = list(eq.columns)
    n = len(eq)
    rows_per_page_est = min(n, 24)
    fig_w = 17.5
    fig_h = max(6.2, min(13.0, 2.65 + 0.43 * (rows_per_page_est + 1)))
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=180)
    fig.patch.set_facecolor("#f8fafc")

    # Header
    axh = fig.add_axes([0.03, 0.83, 0.94, 0.14])
    axh.set_axis_off()
    axh.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.018,rounding_size=0.025",
                                 transform=axh.transAxes, facecolor="#0f172a", edgecolor="#0ea5e9", linewidth=1.2))
    axh.text(0.025, 0.63, "Bonos M — Tasas equivalentes base 182d", color="#e5e7eb",
             fontsize=15.5, fontweight="bold", family="DejaVu Sans", va="center")
    axh.text(0.025, 0.26,
             "Lectura simple: tasa anualizada implícita de mantener el bono 1, 28 o 90 días, usando el precio teórico con el rendimiento actual.",
             color="#cbd5e1", fontsize=8.8, family="DejaVu Sans", va="center")
    axh.text(0.975, 0.63, "1D · 28D · 90D", color="#38bdf8", fontsize=11.5,
             family="DejaVu Sans", ha="right", va="center", fontweight="bold")

    ax = fig.add_axes([0.03, 0.08, 0.94, 0.72])
    ax.set_axis_off()

    # Solo una imagen por página; si hay demasiados, esta función muestra todos con letra menor.
    widths = np.array([1.05, 1.05, 1.0, 1.0, 1.05, 1.05, 1.05], dtype=float)
    widths = widths / widths.sum()
    x_edges = np.concatenate([[0], np.cumsum(widths)])
    row_h = 1.0 / (len(eq) + 1)
    # Limitar alto mínimo de row visual reduciendo fuente cuando haya muchas filas
    fs = 7.2 if len(eq) <= 22 else max(5.5, 7.2 - 0.06*(len(eq)-22))
    hfs = fs + 0.5

    # Header row
    for j, col in enumerate(cols):
        x0, w = x_edges[j], widths[j]
        ax.add_patch(Rectangle((x0, 1-row_h), w, row_h, transform=ax.transAxes,
                               facecolor="#e2e8f0", edgecolor="#cbd5e1", linewidth=0.7))
        ax.text(x0+w/2, 1-row_h/2, col, transform=ax.transAxes, ha="center", va="center",
                color="#0f172a", fontsize=hfs, fontweight="bold", family="DejaVu Sans")

    eq_cols = ["Eq 1D (%)", "Eq 28D (%)", "Eq 90D (%)"]
    vals = pd.concat([eq[c] for c in eq_cols], axis=0).dropna()
    vmin = vals.min() if not vals.empty else np.nan
    vmax = vals.max() if not vals.empty else np.nan

    def cell_bg_for_rate(x):
        if pd.isna(x) or pd.isna(vmin) or pd.isna(vmax):
            return "#ffffff", "#334155"
        t = 0.5 if vmax == vmin else max(0.0, min(1.0, (float(x)-float(vmin))/(float(vmax)-float(vmin))))
        # suave: rojo claro -> amarillo claro -> verde claro
        if t <= 0.5:
            u = t/0.5
            r = int(254 + (254-254)*u); g = int(226 + (249-226)*u); b = int(226 + (195-226)*u)
        else:
            u = (t-0.5)/0.5
            r = int(254 + (220-254)*u); g = int(249 + (252-249)*u); b = int(195 + (231-195)*u)
        return f"#{r:02x}{g:02x}{b:02x}", "#0f172a"

    for i, (_, r) in enumerate(eq.iterrows()):
        y0 = 1 - (i+2)*row_h
        base_bg = "#ffffff" if i % 2 == 0 else "#f1f5f9"
        for j, col in enumerate(cols):
            x0, w = x_edges[j], widths[j]
            val = r[col]
            bg = base_bg
            fg = "#0f172a"
            if col in eq_cols:
                bg, fg = cell_bg_for_rate(val)
            ax.add_patch(Rectangle((x0, y0), w, row_h, transform=ax.transAxes,
                                   facecolor=bg, edgecolor="#e2e8f0", linewidth=0.5))
            if col == "Serie":
                txt = str(val)
            elif col == "Plazo días":
                txt = "—" if pd.isna(val) else f"{int(val):,}"
            else:
                txt = "—" if pd.isna(val) else f"{float(val):,.3f}" if col.startswith("Eq") else f"{float(val):,.4f}"
            ax.text(x0+w/2, y0+row_h/2, txt, transform=ax.transAxes, ha="center", va="center",
                    color=fg, fontsize=fs, family="DejaVu Sans")

    # Footer note
    fig.text(0.035, 0.035,
             "Nota: equivalencia de tasa nominal base 182d. No usa retorno de precio; evita inflar horizontes cortos.",
             color="#64748b", fontsize=7.6, family="DejaVu Sans")

    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# -----------------------------------------------------------------------------
# Tabla Udibono TV=S desde vector.csv (script Dashboard Udibono)
# -----------------------------------------------------------------------------
def _sniff_sep_csv(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(8192)
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        return ";"


def _try_read_vector_csv(filepath: str) -> pd.DataFrame:
    if not filepath or not Path(filepath).exists():
        return pd.DataFrame()
    sep = _sniff_sep_csv(filepath)
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(filepath, sep=sep, encoding=enc, engine="python")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"No pude leer vector.csv. Ultimo error: {last_err}")


def _norm_col_name(name: str) -> str:
    text = str(name).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    norm_map = {_norm_col_name(c): c for c in df.columns}
    cand_norms = [_norm_col_name(x) for x in candidates]
    for cn in cand_norms:
        if cn in norm_map:
            return norm_map[cn]
    for real in df.columns:
        nr = _norm_col_name(real)
        for cn in cand_norms:
            if cn and (cn in nr or nr in cn):
                return real
    return None


def _to_float_series(sx: pd.Series) -> pd.Series:
    def parse(x):
        if pd.isna(x):
            return np.nan
        t = str(x).strip().replace("%", "").strip()
        if not t:
            return np.nan
        if "," in t and "." in t:
            t = t.replace(",", "")
        elif "," in t and "." not in t:
            t = t.replace(",", ".")
        t = re.sub(r"[^0-9\.\-eE]", "", t)
        try:
            return float(t)
        except Exception:
            return np.nan
    return sx.map(parse).astype("float64")


def load_udibono_carry_table(vector_path: Optional[str], funding_rate_pct: float = 6.50, monto: float = 10_000_000) -> pd.DataFrame:
    """Replica la tabla del Dashboard Udibono: TV=S, DV01, THETA, fondeo, carry, prestamo teorico y T.1Dia."""
    if not vector_path:
        return pd.DataFrame()
    df0 = _try_read_vector_csv(vector_path)
    if df0.empty:
        return pd.DataFrame()

    col_tv = _pick_col(df0, ["TV", "TipoValor", "tipo_valor", "tipo"])
    col_serie = _pick_col(df0, ["SERIE", "Serie", "serieid", "idserie"])
    col_rend = _pick_col(df0, ["RENDIMIENTO", "Rendimiento", "yield", "yld", "rend"])
    col_cupon = _pick_col(df0, ["TasaCuponVigente", "tasacuponvigente", "cuponvigente", "cupon", "tasa_cupon"])
    col_dur = _pick_col(df0, ["Duracion", "DURACION", "duración", "duration", "moddur", "dur"])
    col_ps = _pick_col(df0, ["PrecioSucio", "preciosucio", "precio_sucio", "ps", "dirtyprice"])
    col_ps24 = _pick_col(df0, ["PrecioSucio24Hrs", "preciosucio24hrs", "preciosucio24h", "ps24", "dirtyprice24"])
    col_dpv = _pick_col(df0, ["DiasPorVencer", "diasporvencer", "dias_vencer", "dpv", "daystomaturity"])
    col_dpv24 = _pick_col(df0, ["DiasPorVencer24Hrs", "diasporvencer24hrs", "diasporvencer24h", "dpv24"])

    required = [col_tv, col_serie, col_rend, col_cupon, col_dur, col_ps, col_ps24, col_dpv, col_dpv24]
    if any(c is None for c in required):
        return pd.DataFrame()

    tv = df0[col_tv].astype(str).str.strip().str.upper()
    df = df0[tv == "S"].copy()
    if df.empty:
        return pd.DataFrame()

    out = pd.DataFrame({
        "Serie": df[col_serie].astype(str),
        "Rendimiento": _to_float_series(df[col_rend]),
        "TasaCuponVigente x100": _to_float_series(df[col_cupon]) * 100.0,
        "Duracion": _to_float_series(df[col_dur]),
        "PrecioSucio": _to_float_series(df[col_ps]),
        "PrecioSucio24Hrs": _to_float_series(df[col_ps24]),
        "DiasPorVencer": _to_float_series(df[col_dpv]),
        "DiasPorVencer24Hrs": _to_float_series(df[col_dpv24]),
    })
    tasa_fondeo = funding_rate_pct / 100.0
    out["DV01"] = out["Duracion"] * (monto / 10000.0) * 1.0
    units = (monto / out["PrecioSucio"]).where(out["PrecioSucio"].notna() & (out["PrecioSucio"] != 0), other=np.nan)
    out["THETA"] = units * (out["PrecioSucio24Hrs"] - out["PrecioSucio"])
    out["Costo Fondeo"] = (monto * tasa_fondeo) / 360.0
    denom = out["DiasPorVencer"] - out["DiasPorVencer24Hrs"]
    ratio = (out["PrecioSucio24Hrs"] / out["PrecioSucio"]).where(out["PrecioSucio"].notna() & (out["PrecioSucio"] != 0), other=np.nan)
    t1_dec = ((ratio - 1.0) / denom) * 360.0
    t1_dec = t1_dec.where(denom.notna() & (denom != 0), other=np.nan)
    out["T.1Dia (%)"] = t1_dec * 100.0
    out["Carry Neto"] = (monto * t1_dec) / 360.0 - out["Costo Fondeo"]
    out["Prestamo Teorico"] = ((out["Carry Neto"] / out["DV01"]) / 100.0).where(out["DV01"].notna() & (out["DV01"] != 0), other=np.nan)
    cols = ["Serie", "Rendimiento", "TasaCuponVigente x100", "DV01", "THETA", "Costo Fondeo", "Carry Neto", "Prestamo Teorico", "T.1Dia (%)"]
    return out[cols].dropna(how="all")


def _tri_gradient_hex(t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    if t <= 0.5:
        u = t / 0.5
        r = int(round(210 + (230 - 210) * u)); g = int(round(60 + (200 - 60) * u)); b = 60
    else:
        u = (t - 0.5) / 0.5
        r = int(round(230 + (60 - 230) * u)); g = int(round(200 + (210 - 200) * u)); b = int(round(60 + (80 - 60) * u))
    return f"#{r:02x}{g:02x}{b:02x}"


def save_udibono_carry_table_image(df: pd.DataFrame, funding_rate_pct: float, path: Path) -> Optional[Path]:
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    n = len(df)
    fig_w = 23.5
    fig_h = max(5.4, min(13.3, 2.0 + 0.43 * (n + 1)))
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=180)
    fig.patch.set_facecolor("#0b0f14")
    axh = fig.add_axes([0.02, 0.875, 0.96, 0.11])
    axh.set_axis_off()
    axh.text(0.015, 0.62, "NEUTRINO QUANT — DASHBOARD UDIBONO (TV=S)", color="#00e5ff", fontsize=18, fontweight="bold", family="monospace", va="center")
    axh.text(0.015, 0.22, f"> DV01 / THETA / Carry Neto / Prestamo Teorico · Monto: 10,000,000 · Tasa fondeo: {funding_rate_pct:.2f}%", color="#8aa0b6", fontsize=9.2, family="monospace", va="center")
    axh.text(0.965, 0.58, "● TV=S", color="#22c55e", fontsize=10, family="monospace", ha="right", va="center")

    ax = fig.add_axes([0.02, 0.045, 0.96, 0.81])
    ax.set_axis_off()
    widths = np.array([1.45, 1.2, 1.65, 1.25, 1.35, 1.45, 1.45, 1.45, 1.15], dtype=float)
    widths = widths / widths.sum()
    x_edges = np.concatenate([[0], np.cumsum(widths)])
    row_h = 1.0 / (n + 1)
    for j, col in enumerate(cols):
        x0 = x_edges[j]; w = widths[j]
        ax.add_patch(Rectangle((x0, 1-row_h), w, row_h, transform=ax.transAxes, facecolor="#0f1620", edgecolor="#1b2a3a", linewidth=0.7))
        ax.text(x0+w/2, 1-row_h/2, col, transform=ax.transAxes, ha="center", va="center", color="#00e5ff", fontsize=7.4, fontweight="bold", family="monospace")
    vmin = df["T.1Dia (%)"].min(skipna=True)
    vmax = df["T.1Dia (%)"].max(skipna=True)
    for i, (_, r) in enumerate(df.iterrows()):
        y0 = 1 - (i+2)*row_h
        bg = "#0c141d" if i % 2 == 0 else "#0e1722"
        for j, col in enumerate(cols):
            x0 = x_edges[j]; w = widths[j]
            ax.add_patch(Rectangle((x0, y0), w, row_h, transform=ax.transAxes, facecolor=bg, edgecolor="#1b2a3a", linewidth=0.42))
            val = r[col]
            if col == "Serie":
                txt = str(val)
            elif pd.isna(val):
                txt = "—"
            elif col in ["Rendimiento", "TasaCuponVigente x100", "T.1Dia (%)"]:
                txt = f"{float(val):,.4f}"
            else:
                txt = f"{float(val):,.2f}"
            color = "#d7e1ee"
            if col == "T.1Dia (%)" and pd.notna(val):
                t = 0.5 if vmax == vmin else max(0.0, min(1.0, (float(val)-float(vmin))/(float(vmax)-float(vmin))))
                color = _tri_gradient_hex(t)
            ax.text(x0+w/2, y0+row_h/2, txt, transform=ax.transAxes, ha="center", va="center", color=color, fontsize=7.05, family="monospace")
    ax.add_patch(Rectangle((0,0),1,1,transform=ax.transAxes,facecolor="none",edgecolor="#00e5ff",linewidth=1.0))
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def add_udibono_carry_section(story: List, styles, vector_path: Optional[str], funding_rate_pct: float, tmp: Path):
    try:
        df = load_udibono_carry_table(vector_path, funding_rate_pct=funding_rate_pct)
        if df is None or df.empty:
            return
        img = save_udibono_carry_table_image(df, funding_rate_pct, tmp / "udibono_carry_fondeo.png")
        if img:
            add_section_label(story, styles, f"Udibonos - Carry / Fondeo {funding_rate_pct:.2f}%", "Tabla TV=S del Dashboard Udibono: DV01, THETA, Costo Fondeo, Carry Neto, Prestamo Teorico y T.1Dia.")
            story += img_flow(img, 26.8*cm, 15.6*cm)
            # Sin salto extra: evita páginas vacías al final de la sección.
    except Exception as e:
        print(f"Aviso: no se pudo generar tabla Udibono TV=S: {e}")


# -----------------------------------------------------------------------------
# LF / ST polynomial regression module (from LF – Curva ST Polinómica)
# -----------------------------------------------------------------------------
def _safe_color_from_z_lf(z, min_z, max_z):
    """Color dinamico basado en Z-score: gris cerca de 0, verde positivo, rojo negativo."""
    try:
        if pd.isna(z):
            return '#808080'
        if abs(float(z)) < 0.05:
            return '#808080'
        if z > 0:
            denom = max_z if (max_z is not None and max_z != 0) else 1.0
            ratio = min(float(z) / denom, 1.0)
            g = int(255 * ratio)
            return f'#00{g:02x}00'
        denom = abs(min_z) if (min_z is not None and min_z != 0) else 1.0
        ratio = min(abs(float(z)) / denom, 1.0)
        r = int(255 * ratio)
        return f'#{r:02x}0000'
    except Exception:
        return '#808080'


def load_lf_data(lf_path: Optional[str]) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Lee LF_PYTHON.csv siguiendo la estructura del script subido: columnas [1]=Dia, [2]=Serie, [3]=DPV, [4]=ST."""
    if not lf_path:
        lf_path = DEFAULT_LF
    p = Path(lf_path)
    if not p.exists():
        raise FileNotFoundError(f"No existe LF_PYTHON.csv: {p}")
    df = pd.read_csv(p)
    df.columns = [str(c).strip() for c in df.columns]
    if len(df.columns) < 5:
        raise ValueError("LF_PYTHON.csv debe tener al menos 5 columnas como el script original.")
    cols = {
        "dia": df.columns[1],
        "serie": df.columns[2],
        "dpv": df.columns[3],
        "st": df.columns[4],
    }
    df[cols["dia"]] = pd.to_datetime(df[cols["dia"]], errors="coerce", dayfirst=True)
    df[cols["dpv"]] = pd.to_numeric(df[cols["dpv"]], errors="coerce")
    df[cols["st"]] = pd.to_numeric(df[cols["st"]], errors="coerce")
    df = df.dropna(subset=[cols["dia"], cols["dpv"], cols["st"]]).copy()
    if df.empty:
        raise ValueError("LF_PYTHON.csv no tiene datos validos despues de limpiar fecha, DPV y ST.")
    return df, cols


def _polyfit_predict_lf(x, y, degree: int, x_grid=None):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    degree_eff = int(min(max(1, degree), max(1, len(np.unique(x)) - 1), max(1, len(x) - 1)))
    coeffs = np.polyfit(x, y, degree_eff)
    pred = np.polyval(coeffs, x)
    if x_grid is None:
        grid_pred = None
    else:
        grid_pred = np.polyval(coeffs, np.asarray(x_grid, dtype=float))
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot != 0 else np.nan
    return coeffs, pred, grid_pred, r2, degree_eff


def compute_lf_regression_and_zscore(lf_path: Optional[str], report_date: Optional[pd.Timestamp] = None,
                                     degree: int = 3, periods: int = 180) -> Dict[str, object]:
    df, cols = load_lf_data(lf_path)
    dates = sorted(df[cols["dia"]].dt.date.dropna().unique())
    if not dates:
        raise ValueError("LF_PYTHON.csv no tiene fechas validas.")
    if report_date is None:
        fecha_actual = dates[-1]
    else:
        target = pd.Timestamp(report_date).date()
        candidates = [d for d in dates if d <= target]
        fecha_actual = candidates[-1] if candidates else dates[-1]

    data_actual = df[df[cols["dia"]].dt.date == fecha_actual].dropna(subset=[cols["dpv"], cols["st"]]).copy()
    if len(data_actual) < 4:
        raise ValueError(f"No hay suficientes datos LF para {fecha_actual}.")
    data_actual = data_actual.sort_values(cols["dpv"]).reset_index(drop=True)
    x = data_actual[cols["dpv"]].astype(float).to_numpy()
    y = data_actual[cols["st"]].astype(float).to_numpy()
    coeffs, pred, _, r2, degree_eff = _polyfit_predict_lf(x, y, degree)
    data_actual["Regresion"] = np.round(pred, 4)
    data_actual["Diferencia"] = np.round(data_actual[cols["st"]] - data_actual["Regresion"], 4)

    historico = df[df[cols["dia"]].dt.date < fecha_actual].dropna(subset=[cols["dpv"], cols["st"]]).copy()
    registros = []
    if not historico.empty:
        for f in sorted(historico[cols["dia"]].dt.date.unique()):
            hist = historico[historico[cols["dia"]].dt.date == f].dropna(subset=[cols["dpv"], cols["st"]]).copy()
            if len(hist) < 4:
                continue
            xh = hist[cols["dpv"]].astype(float).to_numpy()
            yh = hist[cols["st"]].astype(float).to_numpy()
            _, pred_h, _, _, _ = _polyfit_predict_lf(xh, yh, degree)
            for s, r in zip(hist[cols["serie"]], yh - pred_h):
                registros.append({"Serie": s, "Fecha": f, "Residuo": float(r)})

    residuos_historico = pd.DataFrame(registros)
    if not residuos_historico.empty:
        residuos_lim = residuos_historico.sort_values(["Serie", "Fecha"]).groupby("Serie", group_keys=False).tail(periods)
        media_res = residuos_lim.groupby("Serie")["Residuo"].mean()
        std_res = residuos_lim.groupby("Serie")["Residuo"].std()
    else:
        media_res = pd.Series(dtype=float)
        std_res = pd.Series(dtype=float)

    df_modelo = data_actual.copy()
    df_modelo["Prediccion"] = pred
    df_modelo["Residuo"] = y - pred
    df_modelo["Media_Residuo"] = df_modelo[cols["serie"]].map(media_res)
    df_modelo["STD_Residuo"] = df_modelo[cols["serie"]].map(std_res).replace(0, np.nan)
    df_modelo["Z-score"] = (df_modelo["Residuo"] - df_modelo["Media_Residuo"]) / df_modelo["STD_Residuo"]
    df_modelo["Z-score"] = df_modelo["Z-score"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    df_modelo = df_modelo.sort_values(cols["dpv"]).reset_index(drop=True)

    reg_view = data_actual.rename(columns={cols["serie"]: "Serie", cols["dpv"]: "Días por vencer", cols["st"]: "ST"})[
        ["Serie", "Días por vencer", "ST", "Regresion", "Diferencia"]
    ].copy()
    z_view = df_modelo.rename(columns={cols["serie"]: "Serie", cols["dpv"]: "Días por vencer", cols["st"]: "ST"})[
        ["Serie", "Días por vencer", "ST", "Prediccion", "Residuo", "Media_Residuo", "STD_Residuo", "Z-score"]
    ].copy()
    return {
        "df": df,
        "cols": cols,
        "fecha": fecha_actual,
        "degree": degree_eff,
        "r2": r2,
        "reg": reg_view,
        "z": z_view,
        "coeffs": coeffs,
        "residuos_historico": residuos_historico,
        "periods": periods,
    }


def save_lf_regression_chart(result: Dict[str, object], path: Path) -> Optional[Path]:
    reg = result["reg"]
    if reg is None or reg.empty:
        return None
    fig, ax = plt.subplots(figsize=(12.0, 6.2), dpi=170)
    fig.patch.set_facecolor('#050608')
    ax.set_facecolor('#050608')
    x = reg["Días por vencer"].astype(float).to_numpy()
    y = reg["ST"].astype(float).to_numpy()
    coeffs = result["coeffs"]
    ax.scatter(x, y, color='#00e5ff', label='ST Real', s=52, edgecolor='#111111')
    if len(x) > 1:
        xg = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), 300)
        yg = np.polyval(coeffs, xg)
        ax.plot(xg, yg, color='#ffeb3b', linewidth=2.4, label=f'Regresión grado {result["degree"]}')
    ax.set_title(f"LF / ST vs Días por Vencer | {result['fecha']} | R²={result['r2']:.4f}", color='#e0e0e0', fontsize=14, pad=12)
    ax.set_xlabel('Días por vencer', color='#b0bec5', fontsize=11)
    ax.set_ylabel('ST', color='#b0bec5', fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.25, color='#263238')
    ax.tick_params(axis='both', colors='#b0bec5')
    leg = ax.legend(facecolor="#111827", edgecolor="#374151", fontsize=9)
    for t in leg.get_texts():
        t.set_color('#e5e7eb')
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_lf_zscore_chart(result: Dict[str, object], path: Path) -> Optional[Path]:
    zdf = result["z"]
    if zdf is None or zdf.empty:
        return None
    fig, ax = plt.subplots(figsize=(12.0, 6.2), dpi=170)
    fig.patch.set_facecolor('#050608')
    ax.set_facecolor('#050608')
    min_z = float(zdf['Z-score'].min()) if not zdf.empty else -1
    max_z = float(zdf['Z-score'].max()) if not zdf.empty else 1
    for _, row in zdf.iterrows():
        ax.scatter(row["Días por vencer"], row["ST"], color=_safe_color_from_z_lf(row['Z-score'], min_z, max_z), s=48, edgecolor='#000000')
    x = zdf["Días por vencer"].astype(float).to_numpy()
    if len(x) > 1:
        xg = np.linspace(float(np.nanmin(x)), float(np.nanmax(x)), 300)
        yg = np.polyval(result["coeffs"], xg)
        ax.plot(xg, yg, color='#ffeb3b', lw=2.2)
    ax.set_title(f"Modelo Z-score de residuos LF (N={result['periods']}) | grado {result['degree']} | {result['fecha']}", color='#e5e7eb', fontsize=13, pad=12)
    ax.set_xlabel('Días por vencer', color='#9ca3af')
    ax.set_ylabel('ST', color='#9ca3af')
    ax.grid(True, linestyle='--', alpha=0.25, color='#263238')
    ax.tick_params(axis='both', colors='#9ca3af')
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_lf_residual_history_combo(result: Dict[str, object], serie: str, path: Path) -> Optional[Path]:
    hist = result.get("residuos_historico")
    df = result.get("df")
    cols = result.get("cols")
    if hist is None or hist.empty or df is None or not cols:
        return None
    data_serie = hist[hist["Serie"].astype(str) == str(serie)].sort_values("Fecha").tail(int(result.get("periods", 180)))
    if data_serie.empty:
        return None
    mean_res = data_serie["Residuo"].mean()
    std_res = data_serie["Residuo"].std()
    if not std_res or not np.isfinite(std_res):
        std_res = 1.0
    current_row = result["z"][result["z"]["Serie"].astype(str) == str(serie)]
    last_res = float(current_row["Residuo"].iloc[0]) if not current_row.empty else float(data_serie["Residuo"].iloc[-1])
    serie_st = df[df[cols["serie"]].astype(str) == str(serie)].sort_values(cols["dia"]).tail(int(result.get("periods", 180)))
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 4.8), dpi=170)
    fig.patch.set_facecolor('#050608')
    for ax in (ax1, ax2, ax3):
        ax.set_facecolor('#050608')
        ax.tick_params(axis='both', colors='#9ca3af', labelsize=8)
        ax.grid(True, alpha=0.2, color='#4b5563')
    fechas = pd.to_datetime(data_serie['Fecha'])
    r = data_serie['Residuo'].astype(float).values
    for k, c in zip([1, 2, 3], ['#37415166', '#f59e0b66', '#ef444466']):
        ax1.fill_between(fechas, mean_res - k * std_res, mean_res + k * std_res, color=c)
    ax1.plot(fechas, r, color='#e5e7eb', lw=1)
    ax1.scatter(fechas, r, color='#22d3ee', s=22)
    ax1.axhline(mean_res, color='#facc15', linestyle='--', lw=1)
    ax1.set_title(f"Residuo histórico ±σ | {serie}", color='#e5e7eb')
    if not serie_st.empty:
        ax2.fill_between(serie_st[cols["dia"]], serie_st[cols["st"]], color='#16a34a66')
        ax2.plot(serie_st[cols["dia"]], serie_st[cols["st"]], color='#22c55e', lw=1)
    ax2.set_title("ST histórica", color='#e5e7eb')
    ax3.hist(r, bins=20, alpha=0.7, edgecolor='#000000', color='#22d3ee')
    if len(r) > 1 and np.nanmax(r) != np.nanmin(r):
        x = np.linspace(np.nanmin(r), np.nanmax(r), 200)
        ax3.plot(x, stats.norm.pdf(x, mean_res, std_res) * len(r) * (x[1] - x[0]), color='#e5e7eb')
    ax3.axvline(mean_res, color='#facc15', ls='--', lw=2)
    ax3.axvline(last_res, color='#ef4444', lw=2)
    ax3.set_title("Histograma residuos", color='#e5e7eb')
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def build_dataset_section(story: List, styles, ds: Dataset, report_date: pd.Timestamp,
                          matrix_days: int, curve_days: int, top_n: int, tmp: Path,
                          vector_path: Optional[str] = None, funding_rate_pct: float = 6.50, lf_path: Optional[str] = None, lf_periods: int = 180, general_amount: float = 100_000_000):
    matrix_start_raw = report_date - pd.Timedelta(days=matrix_days)
    curve_comp_raw = report_date - pd.Timedelta(days=curve_days)

    spread_mx, z_mx, df_filtrado, color_spread, color_z, matrix_start, matrix_end = compute_spread_matrices(ds, matrix_start_raw, report_date)
    pairs = best_pairs(z_mx, spread_mx, top_n=top_n)
    curve, curve_d1, curve_d2 = compute_curve_table(ds, report_date, curve_comp_raw)
    metrics = curve_metrics(ds, curve_d1, curve_d2)

    safe = re.sub(r"[^A-Za-z0-9]+", "_", ds.name)
    spread_img = save_tk_matrix_image(spread_mx, color_spread, f"SPREAD MATRIX - {ds.name}", "MODE: SPREAD", ACCENT_GREEN, ds.name, matrix_start, matrix_end, tmp / f"{safe}_spread_matrix.png", is_z=False)
    z_img = save_tk_matrix_image(z_mx, color_z, f"Z-MATRIX - {ds.name}", "MODE: Z-SCORE", ACCENT_VIOLET, ds.name, matrix_start, matrix_end, tmp / f"{safe}_z_matrix.png", is_z=True)
    curve_img = save_curve_terminal(curve, f"YIELD CURVE LAB - {ds.name}", tmp / f"{safe}_curve.png", curve_days)
    curve_diff_img = save_curve_diff_bars(curve, f"CURVE DIFFERENCE - {ds.name}", tmp / f"{safe}_curve_diff.png", curve_days)

    add_section_label(story, styles, f"{ds.name} - Dashboard Ejecutivo", "Resumen limpio del motor de spreads, sin rutas de archivos ni metadatos operativos.")
    kpis = [
        ("FECHA", str(curve_d1.date()), ACCENT_CYAN),
        ("SERIES", str(len(spread_mx.columns)), ACCENT_VIOLET),
        ("2s10s", fmt(metrics.get("2s10s"), 2), ACCENT_GREEN),
        ("5s10s", fmt(metrics.get("5s10s"), 2), ACCENT_AMBER),
        ("TOP |Z|", fmt(pairs.iloc[0]["ABS_Z"], 2) if not pairs.empty else "n/a", ERR_RED),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 0.35*cm))
    info = pd.DataFrame([
        {"Campo": "Ventana matriz", "Valor": f"{matrix_start.date()} a {matrix_end.date()} ({(matrix_end-matrix_start).days} dias)"},
        {"Campo": "Curva comparativa", "Valor": f"{curve_d1.date()} vs {curve_d2.date()}"},
        {"Campo": "Metodo matriz", "Valor": "Spread = SERIE_1 - SERIE_2; Z = (ultimo - media) / std; triangular inferior j < i."},
        {"Campo": "Lectura", "Valor": "Z positivo = spread arriba de media reciente; Z negativo = spread debajo de media reciente."},
    ])
    story.append(table_from_df(info, ["Campo", "Valor"], widths=[5.0*cm, 19.0*cm], max_rows=10))
    if not pairs.empty:
        story.append(Spacer(1, 0.25*cm))
        story.append(Paragraph(f"Par mas extremo: {pairs.iloc[0]['PAR']} con Z={pairs.iloc[0]['Z']:.2f}. Revisar la pagina del par antes de tomar cualquier lectura operativa.", styles["BodyN"]))
    add_page_break(story)

    add_section_label(story, styles, f"{ds.name} - Matriz SPREAD estilo Tkinter", "Replica visual del grid original: triangular inferior, headers cyan/violeta y gradiente rojo-azul por rango historico.")
    story += img_flow(spread_img, 26.5*cm, 17.0*cm)
    add_page_break(story)

    add_section_label(story, styles, f"{ds.name} - Matriz Z-SCORE estilo Tkinter", "Misma matriz triangular, pero mostrando el Z-score de cada spread contra la ventana historica.")
    story += img_flow(z_img, 26.5*cm, 17.0*cm)
    add_page_break(story)

    add_section_label(story, styles, f"{ds.name} - Top {top_n} Z-scores mas extremos", "Ranking de dislocaciones por valor absoluto de Z.")
    if pairs.empty:
        story.append(Paragraph("No hay pares extremos disponibles.", styles["BodyN"]))
        add_page_break(story)
    else:
        out = pairs.copy()
        out.insert(0, "RANK", np.arange(1, len(out)+1))
        story.append(table_from_df(out, ["RANK", "PAR", "SPREAD", "Z", "ABS_Z"], ["#", "PAR", "SPREAD", "Z", "|Z|"], max_rows=top_n, widths=[1.1*cm, 8.2*cm, 3.1*cm, 2.9*cm, 2.9*cm]))
        story.append(Spacer(1, 0.25*cm))
        story.append(Paragraph("Cada par se presenta en una sola hoja con grafica historica e histograma juntos.", styles["BodyN"]))
        add_page_break(story)

        for idx, row in pairs.iterrows():
            s1, s2 = row["S1"], row["S2"]
            hist = pair_history(df_filtrado, s1, s2)
            if hist.empty:
                continue
            combo_img = save_pair_combo(hist, s1, s2, tmp / f"{safe}_pair_{idx}_combo.png")
            add_section_label(story, styles, f"{ds.name} - Extremo #{idx+1}: {s1} - {s2}")
            story += img_flow(combo_img, 26.5*cm, 16.3*cm)
            add_page_break(story)

    add_section_label(story, styles, f"{ds.name} - Curva actual vs hace {curve_days} dias", "Curva comparativa y diferencia punto a punto por vencimiento.")
    story += img_flow(curve_img, 26.0*cm, 12.7*cm)
    story += img_flow(curve_diff_img, 26.0*cm, 10.7*cm)
    story.append(table_from_df(curve, ["SERIE", "TENOR", "ACTUAL", "HACE_30D", "DIF"], ["SERIE", "TENOR", "ACTUAL", f"HACE {curve_days}D", "DIF"], max_rows=28, widths=[3.0*cm, 3.0*cm, 3.1*cm, 3.1*cm, 3.1*cm]))
    add_page_break(story)

    # Tabla de carry / fondeo antes de cerrar seccion de Bonos.
    if "bonos" in ds.name.lower() or "bonos m" in ds.name.lower():
        try:
            carry = load_carry_table(vector_path, funding_rate_pct=funding_rate_pct)
            if carry is not None and not carry.empty:
                carry_img = save_carry_table_image(carry, funding_rate_pct, tmp / "bonos_carry_fondeo.png")
                add_section_label(story, styles, f"{ds.name} - Carry / Fondeo {funding_rate_pct:.2f}%", "Tabla tomada del motor Futuristic Quant Fixed Income Engine: DV01, Theta, Costo de Fondeo, Carry, Prestamo Teorico y Tasa 1 Dia.")
                story += img_flow(carry_img, 26.8*cm, 15.6*cm)

                # Tabla adicional: tasas equivalentes por horizonte para cada Bono M.
                try:
                    eq_rates = load_bonos_equivalent_rate_table(vector_path)
                    if eq_rates is not None and not eq_rates.empty:
                        eq_img = save_bonos_equiv_rate_table_image(eq_rates, tmp / "bonos_tasas_equivalentes_1_28_90.png")
                        story.append(Spacer(1, 0.25*cm))
                        story.append(Paragraph("Bonos M - tasas equivalentes base 182 dias", styles["H2N"]))
                        story.append(Paragraph("Esta tabla ayuda a comparar cada bono en horizontes cortos. La tasa se anualiza para hacer comparables 1, 28 y 90 dias. Debe leerse como una referencia de carry implícito, no como pronóstico garantizado.", styles["BodyN"]))
                        story += img_flow(eq_img, 26.8*cm, 14.2*cm)
                except Exception as e:
                    print(f"Aviso: no se pudo generar tabla de tasas equivalentes Bonos M: {e}")

                # Se inserta SOLO la imagen premium de la tabla para no duplicar la misma informacion.
                add_page_break(story)
        except Exception as e:
            # No romper el reporte si vector.csv no esta disponible.
            print(f"Aviso: no se pudo generar tabla carry/fondeo: {e}")


def build_breakeven_section(story: List, styles, bonos: Dataset, udis: Dataset, report_date: pd.Timestamp,
                            be_days: int, tmp: Path):
    be, be_date = compute_breakeven_snapshot(bonos, udis, report_date)
    extremes, histories, start, end = compute_breakeven_extremes(bonos, udis, report_date, be_days, top_n=3)
    be_img = save_breakeven_snapshot_image(be, "BREAKEVEN INFLATION - ALL", tmp / "breakeven_all.png")

    add_section_label(story, styles, "Breakeven Inflation - Todos los vencimientos", "Nominal interpolado vs tasa real Udibono. Primero se muestra todo el universo de breakevens.")
    if be.empty:
        story.append(Paragraph("No hay informacion comun suficiente entre Bonos M y Udibonos para calcular breakevens.", styles["BodyN"]))
        add_page_break(story)
        return
    story += img_flow(be_img, 26.0*cm, 12.5*cm)
    story.append(table_from_df(be, ["UDI", "TENOR", "NOMINAL_INTERP", "REAL", "BREAKEVEN"], ["UDI", "TENOR", "NOMINAL", "REAL", "BREAKEVEN"], max_rows=35, widths=[3.0*cm, 3.0*cm, 3.5*cm, 3.5*cm, 3.5*cm]))
    add_page_break(story)

    add_section_label(story, styles, "Breakeven Inflation - 3 histogramas mas extremos", f"Extremos por |Z| usando ventana historica de {be_days} dias ({start.date()} a {end.date()}).")
    if extremes.empty:
        story.append(Paragraph("No se encontraron breakevens con historial suficiente para calcular Z-score.", styles["BodyN"]))
        add_page_break(story)
        return
    ext_show = extremes.copy()
    ext_show.insert(0, "RANK", np.arange(1, len(ext_show)+1))
    story.append(table_from_df(ext_show, ["RANK", "UDI", "TENOR", "BREAKEVEN", "MEAN", "STD", "Z", "ABS_Z"], ["#", "UDI", "TENOR", "BE", "MEDIA", "STD", "Z", "|Z|"], max_rows=3, widths=[1.0*cm, 2.5*cm, 2.4*cm, 2.7*cm, 2.7*cm, 2.5*cm, 2.4*cm, 2.4*cm]))
    add_page_break(story)

    for i, r in extremes.iterrows():
        serie = str(r["UDI"])
        hist = histories.get(serie, pd.DataFrame())
        img = save_be_histogram(hist, serie, r, tmp / f"be_hist_{i}.png")
        add_section_label(story, styles, f"Breakeven extremo #{i+1}: {serie}")
        story += img_flow(img, 26.5*cm, 15.5*cm)
        add_page_break(story)



# -----------------------------------------------------------------------------
# Executive Summary - una sola pagina
# -----------------------------------------------------------------------------
def _safe_top(df: pd.DataFrame, col: str, n: int = 5, ascending: bool = False) -> pd.DataFrame:
    if df is None or df.empty or col not in df:
        return pd.DataFrame()
    d = df.copy()
    d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=[col])
    if d.empty:
        return d
    return d.sort_values(col, ascending=ascending).head(n).reset_index(drop=True)


def _arrow_fmt(x, nd=2):
    if x is None or pd.isna(x) or not np.isfinite(float(x)):
        return "n/a"
    x = float(x)
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.{nd}f}"


def _reading_from_z(z):
    if z is None or pd.isna(z) or not np.isfinite(float(z)):
        return "Sin señal"
    z = float(z)
    if z >= 2.0:
        return "Spread muy abierto"
    if z <= -2.0:
        return "Spread muy cerrado"
    if z >= 1.0:
        return "Arriba de media"
    if z <= -1.0:
        return "Debajo de media"
    return "Cerca de media"


def _be_reading(z):
    if z is None or pd.isna(z) or not np.isfinite(float(z)):
        return "Sin señal"
    z = float(z)
    if z >= 2.0:
        return "BE caro"
    if z <= -2.0:
        return "BE barato"
    if z >= 1.0:
        return "BE alto"
    if z <= -1.0:
        return "BE bajo"
    return "Neutral"




def _standardize_udi_carry_for_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas del dashboard Udibono para el resumen ejecutivo.
    Evita KeyError si el vector no trae TV=S, viene vacio o los nombres cambian.
    """
    target = ["Serie", "Carry", "DV01", "THETA", "T1Dia"]
    if df is None or df.empty:
        return pd.DataFrame(columns=target)
    d = df.copy()
    rename = {
        "Carry Neto": "Carry",
        "CarryNeto": "Carry",
        "T.1Dia (%)": "T1Dia",
        "T1Dia (%)": "T1Dia",
        "T.1Dia": "T1Dia",
        "Tasa 1 Dia": "T1Dia",
        "Tasa 1 Día (%)": "T1Dia",
    }
    d = d.rename(columns={k: v for k, v in rename.items() if k in d.columns})
    for c in target:
        if c not in d.columns:
            d[c] = np.nan if c != "Serie" else ""
    return d[target].copy()

def build_executive_summary_page(story: List, styles, bonos: Dataset, udis: Optional[Dataset],
                                 report_date: pd.Timestamp, matrix_days: int, curve_days: int,
                                 top_n: int, be_days: int, vector_path: Optional[str],
                                 funding_rate_pct: float, tmp: Path):
    """Primera pagina: mejores datos accionables del reporte, sin rutas ni portada."""
    matrix_start = report_date - pd.Timedelta(days=matrix_days)
    curve_comp = report_date - pd.Timedelta(days=curve_days)

    spread_b, z_b, df_b, _, _, m_start, m_end = compute_spread_matrices(bonos, matrix_start, report_date)
    pairs_b = best_pairs(z_b, spread_b, top_n=max(3, top_n))
    curve_b, curve_d1, curve_d2 = compute_curve_table(bonos, report_date, curve_comp)
    metrics_b = curve_metrics(bonos, report_date, curve_comp)

    carry_b = load_carry_table(vector_path, funding_rate_pct=funding_rate_pct) if vector_path else pd.DataFrame()
    udi_carry = load_udibono_carry_table(vector_path, funding_rate_pct=funding_rate_pct) if vector_path and udis is not None else pd.DataFrame()

    be_now = pd.DataFrame()
    be_ext = pd.DataFrame()
    if udis is not None:
        be_now, _ = compute_breakeven_snapshot(bonos, udis, report_date)
        be_ext, _, _, _ = compute_breakeven_extremes(bonos, udis, report_date, be_days, top_n=3)

    # Mini chart de diferencia de curva para la pagina 1.
    curve_diff_img = save_curve_diff_bars(curve_b, "BONOS M - CAMBIO DE CURVA VS 30D", tmp / "exec_curve_diff.png", curve_days)

    story.append(Paragraph("RESUMEN EJECUTIVO — BONOS M / UDIBONOS", styles["H1N"]))
    story.append(Paragraph("Snapshot cuantitativo de una pagina: dislocaciones, movimiento de curva, carry contra fondeo y breakevens.", styles["BodyN"]))

    n_udis = len(udis.pivot.columns) if udis is not None else 0
    kpis = [
        ("FECHA", str(pd.Timestamp(curve_d1).date()), ACCENT_CYAN),
        ("BONOS", str(len(bonos.pivot.columns)), ACCENT_VIOLET),
        ("UDIBONOS", str(n_udis), ACCENT_GREEN),
        ("VENTANA", f"{matrix_days}D", ACCENT_AMBER),
        ("FONDEO", f"{funding_rate_pct:.2f}%", ACCENT_CYAN),
        ("TOP |Z|", fmt(pairs_b.iloc[0]["ABS_Z"], 2) if not pairs_b.empty else "n/a", ERR_RED),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 0.22*cm))

    # Top 3 spreads extremos
    if not pairs_b.empty:
        top_spreads = pairs_b.head(3).copy()
        top_spreads.insert(0, "#", range(1, len(top_spreads)+1))
        top_spreads["Lectura"] = top_spreads["Z"].map(_reading_from_z)
        top_spreads = top_spreads[["#", "PAR", "SPREAD", "Z", "Lectura"]]
    else:
        top_spreads = pd.DataFrame(columns=["#", "PAR", "SPREAD", "Z", "Lectura"])

    # Movimiento clave de curva
    curve_points = []
    for tenor, label in [(2.0, "2Y"), (5.0, "5Y"), (10.0, "10Y"), (30.0, "30Y")]:
        if not curve_b.empty:
            d = curve_b.dropna(subset=["TENOR", "DIF"]).copy()
            if not d.empty:
                d["dist"] = (d["TENOR"] - tenor).abs()
                r = d.sort_values("dist").iloc[0]
                curve_points.append({"Punto": label, "Serie": r["SERIE"], "Cambio": _arrow_fmt(r["DIF"], 4)})
    curve_points.extend([
        {"Punto": "2s10s", "Serie": "spread", "Cambio": _arrow_fmt(metrics_b.get("delta_2s10s"), 4)},
        {"Punto": "5s10s", "Serie": "spread", "Cambio": _arrow_fmt(metrics_b.get("delta_5s10s"), 4)},
        {"Punto": "Fly 2-5-10", "Serie": "fly", "Cambio": _arrow_fmt(metrics_b.get("fly_2_5_10"), 4)},
    ])
    curve_tbl_df = pd.DataFrame(curve_points)

    # Carry Bonos M: mejores y peores
    if not carry_b.empty:
        carry_top = _safe_top(carry_b, "Carry", 5, ascending=False)
        carry_top = carry_top[["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"]]
        carry_worst = _safe_top(carry_b, "Carry", 3, ascending=True)
        carry_worst = carry_worst[["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"]]
    else:
        carry_top = pd.DataFrame(columns=["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"])
        carry_worst = pd.DataFrame(columns=["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"])

    # Breakevens: promedio y top 3 extremos
    be_kpis = []
    if not be_now.empty:
        be_kpis.append({"Métrica": "BE promedio", "Valor": fmt(be_now["BREAKEVEN"].mean(), 4)})
        be_kpis.append({"Métrica": "BE mínimo", "Valor": fmt(be_now["BREAKEVEN"].min(), 4)})
        be_kpis.append({"Métrica": "BE máximo", "Valor": fmt(be_now["BREAKEVEN"].max(), 4)})
    be_kpis_df = pd.DataFrame(be_kpis) if be_kpis else pd.DataFrame(columns=["Métrica", "Valor"])

    if not be_ext.empty:
        be_show = be_ext.head(3).copy()
        be_show.insert(0, "#", range(1, len(be_show)+1))
        be_show["Lectura"] = be_show["Z"].map(_be_reading)
        be_show = be_show[["#", "UDI", "BREAKEVEN", "Z", "Lectura"]]
    else:
        be_show = pd.DataFrame(columns=["#", "UDI", "BREAKEVEN", "Z", "Lectura"])

    # Carry Udibonos top 5 (robusto: el dashboard TV=S usa Carry Neto y T.1Dia (%))
    udi_carry_std = _standardize_udi_carry_for_summary(udi_carry)
    udi_top = _safe_top(udi_carry_std, "Carry", 5, ascending=False)
    if udi_top.empty:
        udi_top = pd.DataFrame(columns=["Serie", "Carry", "DV01", "THETA", "T1Dia"])
    else:
        udi_top = _standardize_udi_carry_for_summary(udi_top)

    # Comentario automático de 3 líneas
    comment_rows = []
    if not pairs_b.empty:
        p0 = pairs_b.iloc[0]
        comment_rows.append({"Lectura automática": f"Mayor dislocación Bonos M: {p0['PAR']} con Z={p0['Z']:.2f} ({_reading_from_z(p0['Z'])})."})
    if not curve_tbl_df.empty:
        d2s10s = metrics_b.get("delta_2s10s")
        if pd.notna(d2s10s) and np.isfinite(float(d2s10s)):
            action = "se empinó" if float(d2s10s) > 0 else "se aplanó"
            comment_rows.append({"Lectura automática": f"La curva 2s10s {action} vs hace {curve_days} días: Δ={_arrow_fmt(d2s10s, 4)}."})
    if not carry_top.empty:
        c0 = carry_top.iloc[0]
        comment_rows.append({"Lectura automática": f"Mejor carry Bonos M: {c0['Serie']} con Carry={fmt(c0['Carry'], 2)} usando fondeo {funding_rate_pct:.2f}%."})
    if not be_show.empty:
        b0 = be_show.iloc[0]
        comment_rows.append({"Lectura automática": f"Breakeven más extremo: {b0['UDI']} con Z={fmt(b0['Z'], 2)} ({b0['Lectura']})."})
    comments_df = pd.DataFrame(comment_rows[:4])

    # Layout compacto en 2 columnas para intentar mantenerlo en una pagina.
    left_blocks = [
        Paragraph("Top 3 Z-score Bonos M", styles["H2N"]),
        table_from_df(top_spreads, ["#", "PAR", "SPREAD", "Z", "Lectura"], max_rows=3,
                      widths=[0.65*cm, 5.0*cm, 2.0*cm, 1.5*cm, 3.0*cm]),
        Spacer(1, 0.12*cm),
        Paragraph("Top 5 Carry Bonos M", styles["H2N"]),
        table_from_df(carry_top, ["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"], max_rows=5,
                      widths=[2.0*cm, 2.2*cm, 2.0*cm, 2.0*cm, 2.2*cm]),
        Spacer(1, 0.12*cm),
        Paragraph("Peores 3 Carry Bonos M", styles["H2N"]),
        table_from_df(carry_worst, ["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"], max_rows=3,
                      widths=[2.0*cm, 2.2*cm, 2.0*cm, 2.0*cm, 2.2*cm]),
    ]

    right_blocks = [
        Paragraph(f"Cambio curva vs {curve_days} días", styles["H2N"]),
    ]
    right_blocks += img_flow(curve_diff_img, 11.6*cm, 4.6*cm)
    right_blocks += [
        table_from_df(curve_tbl_df, ["Punto", "Serie", "Cambio"], max_rows=7,
                      widths=[2.5*cm, 2.6*cm, 2.0*cm]),
        Spacer(1, 0.12*cm),
        Paragraph("Breakevens", styles["H2N"]),
        table_from_df(be_kpis_df, ["Métrica", "Valor"], max_rows=3, widths=[3.0*cm, 2.2*cm]),
        table_from_df(be_show, ["#", "UDI", "BREAKEVEN", "Z", "Lectura"], max_rows=3,
                      widths=[0.65*cm, 1.8*cm, 2.0*cm, 1.4*cm, 2.5*cm]),
        Spacer(1, 0.12*cm),
        Paragraph("Top 5 Carry Udibonos", styles["H2N"]),
        table_from_df(udi_top, ["Serie", "Carry", "DV01", "THETA", "T1Dia"], max_rows=5,
                      widths=[1.9*cm, 2.0*cm, 1.9*cm, 1.9*cm, 1.7*cm]),
    ]

    # Layout robusto: NO se mete una lista grande de flowables dentro de una celda.
    # ReportLab puede romper tablas pequeñas, pero no puede partir una celda gigante;
    # por eso el resumen se arma como bloques secuenciales compactos.
    story.append(Paragraph("Top 3 Z-score Bonos M", styles["H2N"]))
    story.append(table_from_df(top_spreads, ["#", "PAR", "SPREAD", "Z", "Lectura"], max_rows=3,
                              widths=[0.65*cm, 5.8*cm, 2.1*cm, 1.6*cm, 3.2*cm]))
    story.append(Spacer(1, 0.10*cm))

    # Dos tablas pequeñas lado a lado: movimiento de curva y breakevens.
    curve_block = [
        Paragraph(f"Cambio curva vs {curve_days} dias", styles["H2N"]),
        table_from_df(curve_tbl_df, ["Punto", "Serie", "Cambio"], max_rows=7,
                      widths=[2.5*cm, 2.8*cm, 2.0*cm]),
    ]
    be_block = [
        Paragraph("Breakevens", styles["H2N"]),
        table_from_df(be_kpis_df, ["Métrica", "Valor"], max_rows=3, widths=[3.2*cm, 2.2*cm]),
        Spacer(1, 0.06*cm),
        table_from_df(be_show, ["#", "UDI", "BREAKEVEN", "Z", "Lectura"], max_rows=3,
                      widths=[0.65*cm, 1.8*cm, 2.0*cm, 1.4*cm, 2.7*cm]),
    ]
    small_two_col = Table([[curve_block, be_block]], colWidths=[12.0*cm, 12.6*cm], hAlign="CENTER")
    small_two_col.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), R_BG_PANEL),
        ("BOX", (0,0), (-1,-1), 0.25, R_ACCENT_CYAN),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(small_two_col)
    story.append(Spacer(1, 0.10*cm))

    # Carry: mostrar lo más importante para que quepa en la primera hoja.
    carry_pair = Table([[
        [Paragraph("Top 3 Carry Bonos M", styles["H2N"]),
         table_from_df(carry_top.head(3), ["Serie", "Carry", "DV01", "Theta", "Tasa 1 Día (%)"], max_rows=3,
                       widths=[1.8*cm, 2.0*cm, 1.8*cm, 1.8*cm, 2.0*cm])],
        [Paragraph("Top 3 Carry Udibonos", styles["H2N"]),
         table_from_df(udi_top.head(3), ["Serie", "Carry", "DV01", "THETA", "T1Dia"], max_rows=3,
                       widths=[1.8*cm, 2.0*cm, 1.8*cm, 1.8*cm, 1.7*cm])]
    ]], colWidths=[12.1*cm, 12.1*cm], hAlign="CENTER")
    carry_pair.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), R_BG_PANEL),
        ("BOX", (0,0), (-1,-1), 0.25, R_ACCENT_CYAN),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(carry_pair)
    story.append(Spacer(1, 0.10*cm))

    if not comments_df.empty:
        story.append(table_from_df(comments_df, ["Lectura automática"], max_rows=4, widths=[25.0*cm]))

    story.append(PageBreak())



# -----------------------------------------------------------------------------
# EXTENSION: LF full colored Z-score table + General CETES BI module
# -----------------------------------------------------------------------------
def _z_color_lf_bg(z: float, min_z: float, max_z: float) -> str:
    """Background color for LF z-score rows: red negative, green positive, gray near zero."""
    try:
        if pd.isna(z) or abs(float(z)) < 0.05:
            return "#111827"
        z = float(z)
        if z > 0:
            denom = max_z if max_z not in (None, 0) and np.isfinite(max_z) else 1.0
            ratio = max(0.0, min(1.0, z / denom))
            return f"#00{int(70 + 150*ratio):02x}{int(40 + 40*ratio):02x}"
        denom = abs(min_z) if min_z not in (None, 0) and np.isfinite(min_z) else 1.0
        ratio = max(0.0, min(1.0, abs(z) / denom))
        return f"#{int(75 + 155*ratio):02x}{int(35 + 20*(1-ratio)):02x}{int(35 + 20*(1-ratio)):02x}"
    except Exception:
        return "#111827"


def _best_text_color_for_bg(bg_hex: str) -> str:
    try:
        h = bg_hex.lstrip('#')
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        lum = 0.2126*r + 0.7152*g + 0.0722*b
        return "#020617" if lum > 155 else "#e5e7eb"
    except Exception:
        return "#e5e7eb"


def save_lf_zscore_full_table_images(zdf: pd.DataFrame, tmp: Path, prefix: str = "lf_z_full", chunk_size: int = 34) -> List[Path]:
    """Render ALL LF rows as colored table images sorted by Z-score."""
    if zdf is None or zdf.empty:
        return []
    d = zdf.copy()
    if "Z-score" not in d.columns:
        return []
    d = d.sort_values("Z-score", ascending=False).reset_index(drop=True)
    cols = [c for c in ["Serie", "Días por vencer", "ST", "Prediccion", "Residuo", "Media_Residuo", "STD_Residuo", "Z-score"] if c in d.columns]
    min_z = float(d["Z-score"].min(skipna=True))
    max_z = float(d["Z-score"].max(skipna=True))
    images: List[Path] = []
    chunks = [d.iloc[i:i+chunk_size].copy() for i in range(0, len(d), chunk_size)]
    for k, ch in enumerate(chunks, start=1):
        n = len(ch)
        fig_w = 23.5
        fig_h = max(5.2, min(15.0, 2.25 + 0.34*(n+1)))
        fig = plt.figure(figsize=(fig_w, fig_h), dpi=180)
        fig.patch.set_facecolor("#050608")

        axh = fig.add_axes([0.025, 0.875, 0.95, 0.105])
        axh.set_axis_off()
        axh.add_patch(Rectangle((0, 0), 1, 1, transform=axh.transAxes, facecolor="#050608", edgecolor="none"))
        axh.text(0.015, 0.62, "LF / ST — TABLA GENERAL POR Z-SCORE", color="#22d3ee", fontsize=17, fontweight="bold", family="monospace", va="center")
        axh.text(0.015, 0.22, f"> Todas las series LF coloreadas por Z-score de residuos · página {k}/{len(chunks)} · verde positivo / rojo negativo", color="#9ca3af", fontsize=9.2, family="monospace", va="center")
        axh.text(0.965, 0.58, f"N={len(d)}", color="#a855f7", fontsize=10, family="monospace", ha="right", va="center")

        ax = fig.add_axes([0.025, 0.045, 0.95, 0.81])
        ax.set_axis_off()
        widths = np.array([1.35, 1.15, .85, 1.0, 1.0, 1.15, 1.05, .85], dtype=float)[:len(cols)]
        widths = widths / widths.sum()
        x_edges = np.concatenate([[0], np.cumsum(widths)])
        row_h = 1.0 / (n + 1)
        for j, col in enumerate(cols):
            x0, w = x_edges[j], widths[j]
            ax.add_patch(Rectangle((x0, 1-row_h), w, row_h, transform=ax.transAxes, facecolor="#020617", edgecolor="#1f2937", linewidth=0.7))
            ax.text(x0+w/2, 1-row_h/2, col, transform=ax.transAxes, ha="center", va="center", color="#9ca3af", fontsize=7.6, fontweight="bold", family="monospace")
        for i, (_, r) in enumerate(ch.iterrows()):
            y0 = 1 - (i+2)*row_h
            bg = _z_color_lf_bg(r.get("Z-score", np.nan), min_z, max_z)
            fg = _best_text_color_for_bg(bg)
            for j, col in enumerate(cols):
                x0, w = x_edges[j], widths[j]
                ax.add_patch(Rectangle((x0, y0), w, row_h, transform=ax.transAxes, facecolor=bg, edgecolor="#111827", linewidth=0.42))
                val = r.get(col, "")
                if isinstance(val, (float, np.floating)):
                    txt = "—" if pd.isna(val) else (f"{float(val):,.3f}" if col == "Z-score" else f"{float(val):,.4f}")
                else:
                    txt = str(val)
                ax.text(x0+w/2, y0+row_h/2, txt, transform=ax.transAxes, ha="center", va="center", color=fg, fontsize=7.0, family="monospace")
        ax.add_patch(Rectangle((0,0),1,1,transform=ax.transAxes, facecolor="none", edgecolor="#22d3ee", linewidth=1.0))
        path = tmp / f"{prefix}_{k}.png"
        fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        images.append(path)
    return images


def load_general_cetes_bi_table(vector_path: Optional[str], funding_rate_pct: float = 6.50, monto: float = 100_000_000) -> pd.DataFrame:
    """Replica el apartado General: TV=BI, 1 DIA, DV0 y CARRY con fondeo/monto dados."""
    if not vector_path:
        return pd.DataFrame()
    df = _try_read_vector_csv(vector_path)
    if df is None or df.empty:
        return pd.DataFrame()
    df.columns = df.columns.astype(str).str.strip()
    required = {"TV", "Serie", "DiasPorVencer", "Rendimiento"}
    if not required.issubset(set(df.columns)):
        # try flexible pick
        col_tv = _pick_col(df, ["TV", "TipoValor", "tipo valor"])
        col_serie = _pick_col(df, ["Serie", "SERIE"])
        col_dpv = _pick_col(df, ["DiasPorVencer", "Dias por vencer", "DXV"])
        col_rend = _pick_col(df, ["Rendimiento", "RENDIMIENTO", "yield"])
        if not all([col_tv, col_serie, col_dpv, col_rend]):
            return pd.DataFrame()
        df = df.rename(columns={col_tv:"TV", col_serie:"Serie", col_dpv:"DiasPorVencer", col_rend:"Rendimiento"})
    d = df[df["TV"].astype(str).str.strip().str.upper() == "BI"].copy()
    if d.empty:
        return pd.DataFrame()
    d = d[["Serie", "DiasPorVencer", "Rendimiento"]].copy()
    d["Serie"] = pd.to_numeric(d["Serie"], errors="coerce")
    d["DiasPorVencer"] = pd.to_numeric(d["DiasPorVencer"], errors="coerce")
    d["Rendimiento"] = pd.to_numeric(d["Rendimiento"], errors="coerce")
    d = d.dropna(subset=["Serie", "DiasPorVencer", "Rendimiento"])
    d["Serie"] = d["Serie"].round().astype(int)
    d["DiasPorVencer"] = d["DiasPorVencer"].round().astype(int)
    d = d[d["DiasPorVencer"] > 0].copy()
    if d.empty:
        return pd.DataFrame()
    dias = d["DiasPorVencer"].astype(float)
    rend = d["Rendimiento"].astype(float)
    d["1 DIA"] = (((1 + (rend/36000.0 * dias)) ** (1.0/dias)) - 1.0) * 360.0 * 100.0
    d["DV0"] = ((-(10.0 / (1.0 + dias * (rend/36000.0))) + (10.0 / (1.0 + dias * ((rend-0.01)/36000.0)))) * (float(monto)/10.0))
    d["CARRY"] = ((d["1 DIA"] - float(funding_rate_pct)) * float(monto)) / 36000.0
    d = d.sort_values("DiasPorVencer").reset_index(drop=True)
    return d[["Serie", "DiasPorVencer", "Rendimiento", "1 DIA", "DV0", "CARRY"]]


def save_general_cetes_bi_table_images(df: pd.DataFrame, tmp: Path, funding_rate_pct: float, monto: float, chunk_size: int = 34) -> List[Path]:
    if df is None or df.empty:
        return []
    d = df.copy().sort_values("DiasPorVencer").reset_index(drop=True)
    vmin = d["CARRY"].min(skipna=True)
    vmax = d["CARRY"].max(skipna=True)
    imgs: List[Path] = []
    cols = ["Serie", "DiasPorVencer", "Rendimiento", "1 DIA", "DV0", "CARRY"]
    chunks = [d.iloc[i:i+chunk_size].copy() for i in range(0, len(d), chunk_size)]
    for k, ch in enumerate(chunks, start=1):
        n = len(ch)
        fig_w = 22.8
        fig_h = max(5.2, min(14.8, 2.25 + 0.36*(n+1)))
        fig = plt.figure(figsize=(fig_w, fig_h), dpi=180)
        fig.patch.set_facecolor("#050816")
        axh = fig.add_axes([0.025, 0.875, 0.95, 0.105])
        axh.set_axis_off()
        axh.text(0.015, 0.62, "CETES — MÓDULO GENERAL BI", color="#22d3ee", fontsize=17, fontweight="bold", family="monospace", va="center")
        axh.text(0.015, 0.22, f"> Monto: {monto:,.0f} · T. Fondeo: {funding_rate_pct:.2f}% · DV0 & CARRY · página {k}/{len(chunks)}", color="#9ca3af", fontsize=9.2, family="monospace", va="center")
        axh.text(0.965, 0.58, f"N={len(d)}", color="#4ade80", fontsize=10, family="monospace", ha="right", va="center")
        ax = fig.add_axes([0.025, 0.045, 0.95, 0.81])
        ax.set_axis_off()
        widths = np.array([1.0, 1.2, 1.15, 1.05, 1.35, 1.35], dtype=float)
        widths = widths / widths.sum()
        x_edges = np.concatenate([[0], np.cumsum(widths)])
        row_h = 1.0/(n+1)
        for j, col in enumerate(cols):
            x0, w = x_edges[j], widths[j]
            ax.add_patch(Rectangle((x0, 1-row_h), w, row_h, transform=ax.transAxes, facecolor="#0f172a", edgecolor="#1e293b", linewidth=0.7))
            ax.text(x0+w/2, 1-row_h/2, col, transform=ax.transAxes, ha="center", va="center", color="#e5e7eb", fontsize=7.8, fontweight="bold", family="monospace")
        for i, (_, r) in enumerate(ch.iterrows()):
            y0 = 1 - (i+2)*row_h
            # Color by CARRY: green positive, red negative, darker around zero
            carry = r.get("CARRY", np.nan)
            if pd.isna(carry) or vmax == vmin:
                bg = "#0b1020"
            elif carry >= 0:
                t = max(0.0, min(1.0, float(carry) / max(abs(vmax), 1e-9)))
                bg = f"#0b{int(80+120*t):02x}{int(40+55*t):02x}"
            else:
                t = max(0.0, min(1.0, abs(float(carry)) / max(abs(vmin), 1e-9)))
                bg = f"#{int(90+140*t):02x}2d2d"
            fg = _best_text_color_for_bg(bg)
            for j, col in enumerate(cols):
                x0, w = x_edges[j], widths[j]
                ax.add_patch(Rectangle((x0, y0), w, row_h, transform=ax.transAxes, facecolor=bg, edgecolor="#111827", linewidth=0.42))
                val = r.get(col, "")
                if col in ["Serie", "DiasPorVencer"]:
                    txt = "" if pd.isna(val) else f"{int(val)}"
                elif col in ["DV0", "CARRY"]:
                    txt = "—" if pd.isna(val) else f"${float(val):,.2f}"
                elif col == "1 DIA":
                    txt = "—" if pd.isna(val) else f"{float(val):,.2f}"
                else:
                    txt = "—" if pd.isna(val) else f"{float(val):,.4f}"
                ax.text(x0+w/2, y0+row_h/2, txt, transform=ax.transAxes, ha="center", va="center", color=fg, fontsize=7.1, family="monospace")
        ax.add_patch(Rectangle((0,0),1,1,transform=ax.transAxes, facecolor="none", edgecolor="#22d3ee", linewidth=1.0))
        path = tmp / f"general_cetes_bi_{k}.png"
        fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        imgs.append(path)
    return imgs


def build_general_cetes_bi_section(story: List, styles, vector_path: Optional[str], funding_rate_pct: float, monto: float, tmp: Path):
    try:
        df = load_general_cetes_bi_table(vector_path, funding_rate_pct=funding_rate_pct, monto=monto)
    except Exception as e:
        print(f"Aviso: no se pudo generar General CETES BI: {e}")
        return
    if df.empty:
        return
    add_section_label(story, styles, "CETES / General BI — DV0 & CARRY", f"Apartado General del script CETES: TV=BI, fondeo {funding_rate_pct:.2f}% y monto {monto:,.0f}.")
    kpis = [
        ("Monto", f"{monto:,.0f}", ACCENT_CYAN),
        ("Fondeo", f"{funding_rate_pct:.2f}%", ACCENT_AMBER),
        ("BI activos", str(len(df)), ACCENT_GREEN),
        ("Carry total", f"${df['CARRY'].sum(skipna=True):,.2f}", ACCENT_VIOLET),
        ("Mejor carry", f"${df['CARRY'].max(skipna=True):,.2f}", ACCENT_GREEN),
        ("Peor carry", f"${df['CARRY'].min(skipna=True):,.2f}", ERR_RED),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 0.18*cm))
    best = df.sort_values("CARRY", ascending=False).head(5)
    worst = df.sort_values("CARRY", ascending=True).head(5)
    pair_tbl = Table([[
        [Paragraph("Top mejor CARRY", styles["H2N"]), table_from_df(best, ["Serie", "DiasPorVencer", "Rendimiento", "1 DIA", "DV0", "CARRY"], max_rows=5, widths=[1.7*cm, 2.1*cm, 2.0*cm, 1.7*cm, 2.1*cm, 2.3*cm])],
        [Paragraph("Top peor CARRY", styles["H2N"]), table_from_df(worst, ["Serie", "DiasPorVencer", "Rendimiento", "1 DIA", "DV0", "CARRY"], max_rows=5, widths=[1.7*cm, 2.1*cm, 2.0*cm, 1.7*cm, 2.1*cm, 2.3*cm])],
    ]], colWidths=[12.3*cm, 12.3*cm], hAlign="CENTER")
    pair_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), R_BG_PANEL),
        ("BOX", (0,0), (-1,-1), 0.25, R_ACCENT_CYAN),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(pair_tbl)
    story.append(Spacer(1, 0.18*cm))
    for img in save_general_cetes_bi_table_images(df, tmp, funding_rate_pct=funding_rate_pct, monto=monto):
        story += img_flow(img, 26.4*cm, 14.6*cm)
    add_page_break(story)


# OVERRIDE: same LF section plus final ALL-LF colored Z-score table.
def build_lf_regression_section(story: List, styles, lf_path: Optional[str], report_date: pd.Timestamp,
                                tmp: Path, degree: int = 3, periods: int = 180):
    try:
        res = compute_lf_regression_and_zscore(lf_path, report_date, degree=degree, periods=periods)
    except Exception as e:
        print(f"Aviso: no se pudo generar sección LF/ST: {e}")
        return
    reg = res["reg"].copy()
    zdf = res["z"].copy()
    reg_img = save_lf_regression_chart(res, tmp / "lf_regression_g3.png")
    z_img = save_lf_zscore_chart(res, tmp / "lf_zscore_model.png")
    best = reg.sort_values("Diferencia", ascending=False).head(5).copy()
    worst = reg.sort_values("Diferencia", ascending=True).head(5).copy()
    z_best = zdf.sort_values("Z-score", ascending=False).head(5).copy()
    z_worst = zdf.sort_values("Z-score", ascending=True).head(5).copy()
    z_ext = zdf.assign(ABS_Z=zdf["Z-score"].abs()).sort_values("ABS_Z", ascending=False).head(10).copy()
    add_section_label(story, styles, "LF / ST Polynomial Regression — grado 3", f"Modelo del script LF_PYTHON.csv: ST vs Días por Vencer, regresión polinómica grado {res['degree']} y residuales.")
    kpis = [
        ("Fecha LF", str(res["fecha"]), ACCENT_CYAN),
        ("Grado", str(res["degree"]), ACCENT_VIOLET),
        ("R²", fmt(res["r2"], 4), ACCENT_GREEN),
        ("N obs", str(len(reg)), ACCENT_AMBER),
        ("N histórico Z", str(periods), ACCENT_CYAN),
        ("Máx |Z|", fmt(zdf["Z-score"].abs().max() if not zdf.empty else np.nan, 3), ERR_RED),
    ]
    story.append(kpi_table(kpis))
    story.append(Spacer(1, 0.18*cm))
    story += img_flow(reg_img, 26.0*cm, 11.5*cm)
    pair_tbl = Table([[
        [Paragraph("Top mejor: ST sobre regresión", styles["H2N"]), table_from_df(best, ["Serie", "Días por vencer", "ST", "Regresion", "Diferencia"], max_rows=5, widths=[3.0*cm, 2.3*cm, 1.8*cm, 2.0*cm, 2.0*cm])],
        [Paragraph("Top peor: ST bajo regresión", styles["H2N"]), table_from_df(worst, ["Serie", "Días por vencer", "ST", "Regresion", "Diferencia"], max_rows=5, widths=[3.0*cm, 2.3*cm, 1.8*cm, 2.0*cm, 2.0*cm])],
    ]], colWidths=[12.3*cm, 12.3*cm], hAlign="CENTER")
    pair_tbl.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), R_BG_PANEL), ("BOX", (0,0), (-1,-1), 0.25, R_ACCENT_CYAN), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    story.append(pair_tbl)
    add_page_break(story)
    add_section_label(story, styles, "LF / ST — Modelo Z-score de residuos", f"Misma lógica de la función modelo_residuos_zscore: residuo actual vs media/std de los últimos {periods} periodos por serie.")
    story += img_flow(z_img, 26.0*cm, 11.5*cm)
    z_pair = Table([[
        [Paragraph("Top Z positivo", styles["H2N"]), table_from_df(z_best, ["Serie", "Días por vencer", "ST", "Residuo", "Z-score"], max_rows=5, widths=[3.0*cm, 2.3*cm, 1.8*cm, 2.0*cm, 1.8*cm])],
        [Paragraph("Top Z negativo", styles["H2N"]), table_from_df(z_worst, ["Serie", "Días por vencer", "ST", "Residuo", "Z-score"], max_rows=5, widths=[3.0*cm, 2.3*cm, 1.8*cm, 2.0*cm, 1.8*cm])],
    ]], colWidths=[12.3*cm, 12.3*cm], hAlign="CENTER")
    z_pair.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), R_BG_PANEL), ("BOX", (0,0), (-1,-1), 0.25, R_ACCENT_CYAN), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    story.append(z_pair)
    story.append(Spacer(1, 0.16*cm))
    story.append(Paragraph("Datos del modelo Z-score — series más extremas por |Z|", styles["H2N"]))
    story.append(table_from_df(z_ext, ["Serie", "Días por vencer", "ST", "Prediccion", "Residuo", "Media_Residuo", "STD_Residuo", "Z-score", "ABS_Z"], max_rows=10, widths=[2.4*cm, 2.1*cm, 1.7*cm, 1.9*cm, 1.9*cm, 2.1*cm, 2.0*cm, 1.7*cm, 1.7*cm]))
    add_page_break(story)
    if not z_ext.empty:
        add_section_label(story, styles, "LF / ST — Historial de residuos de los 3 Z-score más extremos")
        for i, row in z_ext.head(3).iterrows():
            serie = str(row["Serie"])
            img = save_lf_residual_history_combo(res, serie, tmp / f"lf_residual_combo_{i}.png")
            if img:
                story.append(Paragraph(f"Serie {serie} | Z={fmt(row['Z-score'], 3)}", styles["H2N"]))
                story += img_flow(img, 26.2*cm, 9.2*cm)
        add_page_break(story)
    # Final requested table: ALL LF rows colored by Z-score.
    add_section_label(story, styles, "LF / ST — Tabla general por color de todos los LF", "Todas las series LF ordenadas por Z-score y coloreadas según el modelo de residuos.")
    for img in save_lf_zscore_full_table_images(zdf, tmp):
        story += img_flow(img, 26.4*cm, 14.6*cm)
    add_page_break(story)
def add_page_break(story: List):
    """Separador suave: evita PageBreak forzados que generaban paginas vacias o paginas con solo titulo."""
    if not story:
        return
    # Ya no forzamos salto de pagina; dejamos que ReportLab acomode el contenido.
    # Esto elimina hojas blancas y cortes de pagina consecutivos.
    if not isinstance(story[-1], Spacer):
        story.append(Spacer(1, 0.35*cm))


def cleanup_story_pagebreaks(story: List):
    """Quita PageBreaks consecutivos y el PageBreak final para evitar páginas vacías."""
    cleaned = []
    prev_break = False
    for item in story:
        is_break = isinstance(item, PageBreak)
        if is_break and prev_break:
            continue
        cleaned.append(item)
        prev_break = is_break
    while cleaned and isinstance(cleaned[-1], PageBreak):
        cleaned.pop()
    story[:] = cleaned

# =============================================================================
# V8 DESIGN SYSTEM — Profesional · Legible · Informativo
# Fondo blanco · tipografía generosa · semáforos · Z-score en número grande
# portada con datos reales del día · tablas con color por señal
# =============================================================================

# ── Paleta ─────────────────────────────────────────────────────────────────────
C_INK   = colors.HexColor("#0f172a")
C_BODY  = colors.HexColor("#334155")
C_SOFT  = colors.HexColor("#64748b")
C_LINE  = colors.HexColor("#e2e8f0")
C_WHITE = colors.white
C_PAGE  = colors.HexColor("#f8fafc")

C_BLUE  = colors.HexColor("#1d4ed8"); C_BLUE_S  = colors.HexColor("#eff6ff")
C_NAVY  = colors.HexColor("#0f2044")
C_GOLD  = colors.HexColor("#b45309"); C_GOLD_S  = colors.HexColor("#fffbeb")
C_GRN   = colors.HexColor("#047857"); C_GRN_S   = colors.HexColor("#f0fdf4")
C_RED   = colors.HexColor("#b91c1c"); C_RED_S   = colors.HexColor("#fff5f5")
C_VIO   = colors.HexColor("#6d28d9"); C_VIO_S   = colors.HexColor("#f5f3ff")
C_SKY   = colors.HexColor("#0369a1"); C_SKY_S   = colors.HexColor("#f0f9ff")
C_AMB   = colors.HexColor("#92400e"); C_AMB_S   = colors.HexColor("#fef3c7")

_AC_MAP = {"blue":C_BLUE,"sky":C_SKY,"gold":C_GOLD,"amber":C_AMB,
           "green":C_GRN,"emerald":C_GRN,"red":C_RED,"rose":C_RED,
           "purple":C_VIO,"violet":C_VIO,"navy":C_NAVY}
_SF_MAP = {C_BLUE:C_BLUE_S,C_SKY:C_SKY_S,C_GOLD:C_GOLD_S,C_AMB:C_AMB_S,
           C_GRN:C_GRN_S,C_RED:C_RED_S,C_VIO:C_VIO_S}

def _ac(x):
    if isinstance(x,str) and x in _AC_MAP: return _AC_MAP[x]
    try: return colors.HexColor(x) if isinstance(x,str) else x
    except: return C_BLUE
def _sf(ac): return _SF_MAP.get(ac, C_BLUE_S)
def _z_ac(z):
    try:
        z=float(z)
        if z<=-2: return C_RED
        if z>= 2: return C_GRN
        if z<=-1: return C_AMB
        if z>= 1: return C_GOLD
        return C_SOFT
    except: return C_SOFT
def _z_sf(z):
    try:
        z=float(z)
        if abs(z)>=2: return C_RED_S if z<0 else C_GRN_S
        if abs(z)>=1: return C_AMB_S
        return C_WHITE
    except: return C_WHITE


# ── Estilos ────────────────────────────────────────────────────────────────────
def make_styles():
    ss = getSampleStyleSheet()
    DEFS=[
        ("CoverTitle",dict(fontName="Helvetica-Bold",fontSize=40,leading=46,textColor=C_WHITE,alignment=TA_LEFT)),
        ("CoverSub",  dict(fontName="Helvetica",fontSize=14,leading=18,textColor=colors.HexColor("#bfdbfe"),alignment=TA_LEFT)),
        ("H1N",       dict(fontName="Helvetica-Bold",fontSize=20,leading=24,textColor=C_INK,spaceBefore=4,spaceAfter=5)),
        ("H2N",       dict(fontName="Helvetica-Bold",fontSize=13,leading=16,textColor=C_INK,spaceBefore=3,spaceAfter=4)),
        ("BodyN",     dict(fontName="Helvetica",fontSize=10.5,leading=14,textColor=C_BODY,spaceAfter=4)),
        ("SmallN",    dict(fontName="Helvetica",fontSize=9,leading=11.5,textColor=C_SOFT)),
        ("Kpi",       dict(fontName="Helvetica-Bold",fontSize=11,leading=13,textColor=C_INK,alignment=TA_CENTER)),
    ]
    for name,kw in DEFS:
        try: ss.add(ParagraphStyle(name,**kw))
        except: pass
    return ss


# ── Header / Footer ────────────────────────────────────────────────────────────
def on_page(canvas,doc):
    canvas.saveState()
    w,h=doc.pagesize
    canvas.setFillColor(C_PAGE); canvas.rect(0,0,w,h,fill=1,stroke=0)
    canvas.setFillColor(C_NAVY); canvas.rect(0,h-1.18*cm,w,1.18*cm,fill=1,stroke=0)
    canvas.setFillColor(C_GOLD); canvas.rect(0,h-1.18*cm,0.42*cm,1.18*cm,fill=1,stroke=0)
    canvas.setFillColor(C_WHITE); canvas.setFont("Helvetica-Bold",9.5)
    canvas.drawString(0.82*cm,h-0.76*cm,"RENTA FIJA MX  ·  ANÁLISIS EJECUTIVO")
    canvas.setFont("Helvetica",8.5)
    canvas.drawRightString(w-0.82*cm,h-0.76*cm,"Bonos M  ·  Udibonos  ·  CETES")
    canvas.setStrokeColor(C_LINE); canvas.setLineWidth(0.5)
    canvas.line(0.8*cm,1.08*cm,w-0.8*cm,1.08*cm)
    canvas.setFillColor(C_SOFT); canvas.setFont("Helvetica",7.8)
    canvas.drawString(0.8*cm,0.5*cm,
        "Material informativo. Las señales cuantitativas son apoyo de análisis — no constituyen recomendación de inversión.")
    canvas.setFillColor(C_BLUE); canvas.setFont("Helvetica-Bold",9)
    canvas.drawRightString(w-0.8*cm,0.5*cm,f"Pág. {doc.page}")
    canvas.restoreState()


# ── Portada con datos reales ───────────────────────────────────────────────────
class _CoverFlowable(Flowable):
    def __init__(self,report_date,bonos_name="Bonos M",
                 top_pair="—",top_z=float("nan"),
                 curve_msg="—",carry_msg="—",be_msg="—",lf_msg="—",
                 n_bonos=0,n_udis=0,funding=6.50):
        super().__init__()
        self.rd=report_date; self.bn=bonos_name
        self.top_pair=top_pair; self.top_z=top_z
        self.curve_msg=curve_msg; self.carry_msg=carry_msg
        self.be_msg=be_msg; self.lf_msg=lf_msg
        self.n_bonos=n_bonos; self.n_udis=n_udis; self.funding=funding

    def wrap(self,aw,ah): return aw,ah

    def draw(self):
        cv=self.canv; w,h=cv._doctemplate.pagesize
        # fondo
        cv.setFillColor(colors.HexColor("#0a1628")); cv.rect(0,0,w,h,fill=1,stroke=0)
        # banda dorada lateral
        cv.setFillColor(C_GOLD); cv.rect(0,0,0.5*cm,h,fill=1,stroke=0)
        # zona superior
        cv.setFillColor(colors.HexColor("#0d1f40")); cv.rect(0.5*cm,h*0.60,w,h*0.40,fill=1,stroke=0)
        cv.setStrokeColor(C_GOLD); cv.setLineWidth(1.5)
        cv.line(1.1*cm,h*0.60,w-0.8*cm,h*0.60)

        # eyebrow
        cv.setFillColor(C_GOLD); cv.setFont("Helvetica-Bold",10)
        cv.drawString(1.5*cm,h*0.918,"REPORTE CUANTITATIVO  ·  RENTA FIJA MX")
        cv.setStrokeColor(colors.HexColor("#1d3a6b")); cv.setLineWidth(0.4)
        cv.line(1.5*cm,h*0.905,w-1.2*cm,h*0.905)

        # título
        cv.setFillColor(C_WHITE); cv.setFont("Helvetica-Bold",40)
        cv.drawString(1.5*cm,h*0.845,"Análisis Ejecutivo")
        cv.setFont("Helvetica-Bold",26); cv.setFillColor(colors.HexColor("#93c5fd"))
        cv.drawString(1.5*cm,h*0.793,"de Renta Fija")
        cv.setFillColor(colors.HexColor("#94a3b8")); cv.setFont("Helvetica",11.5)
        cv.drawString(1.5*cm,h*0.760,"Señales Z-score · Carry · Curvas · Breakeven")

        # fecha + stats badges
        cv.setFillColor(C_BLUE); cv.roundRect(1.5*cm,h*0.698,8.0*cm,0.8*cm,0.18*cm,fill=1,stroke=0)
        cv.setFillColor(C_WHITE); cv.setFont("Helvetica-Bold",11.5)
        fecha_str=pd.Timestamp(self.rd).strftime("%d %b %Y").upper()
        cv.drawString(2.0*cm,h*0.724,f"Fecha:  {fecha_str}")

        for i,(label,val) in enumerate([("Bonos M",str(self.n_bonos)),
                                         ("Udibonos",str(self.n_udis)),
                                         ("Fondeo",f"{self.funding:.2f}%")]):
            bx=10.2*cm+i*3.0*cm
            cv.setFillColor(colors.HexColor("#0d1f3c"))
            cv.roundRect(bx,h*0.698,2.7*cm,0.8*cm,0.15*cm,fill=1,stroke=0)
            cv.setFillColor(colors.HexColor("#64748b")); cv.setFont("Helvetica",7.5)
            cv.drawString(bx+0.18*cm,h*0.745,label)
            cv.setFillColor(C_WHITE); cv.setFont("Helvetica-Bold",11)
            cv.drawString(bx+0.18*cm,h*0.710,val)

        # ── 4 tarjetas de señal del día con número grande ──────────────────
        SIGNALS=[
            ("PAR MÁS DISLOCADO",self.top_pair,
             f"Z = {float(self.top_z):+.2f}" if _is_finite(self.top_z) else "",
             "#b91c1c" if _is_finite(self.top_z) and float(self.top_z)<-1
             else ("#047857" if _is_finite(self.top_z) and float(self.top_z)>1 else "#b45309")),
            ("MEJOR CARRY",self.carry_msg,"Carry neto positivo máximo","#047857"),
            ("CURVA 2s10s",self.curve_msg,"Pendiente vs hace 30 días","#1d4ed8"),
            ("BREAKEVEN EXTREMO",self.be_msg,"Inflación implícita","#6d28d9"),
        ]
        nc=len(SIGNALS); cw=(w-1.8*cm)/nc-0.2*cm; ch=h*0.145
        y0=h*0.605-ch-0.12*cm
        for idx,(title,line1,line2,hx) in enumerate(SIGNALS):
            cx=0.9*cm+idx*(cw+0.22*cm)
            cv.setFillColor(colors.HexColor("#0d1f3c"))
            cv.roundRect(cx,y0,cw,ch,0.2*cm,fill=1,stroke=0)
            cv.setFillColor(colors.HexColor(hx))
            cv.rect(cx,y0+ch-0.16*cm,cw,0.16*cm,fill=1,stroke=0)
            cv.setFillColor(colors.HexColor("#94a3b8")); cv.setFont("Helvetica-Bold",7.5)
            cv.drawString(cx+0.28*cm,y0+ch*0.80,title)
            cv.setFillColor(C_WHITE); cv.setFont("Helvetica-Bold",9.5)
            l1=line1[:46] if len(line1)>46 else line1
            cv.drawString(cx+0.28*cm,y0+ch*0.52,l1)
            if line2:
                cv.setFillColor(colors.HexColor(hx)); cv.setFont("Helvetica",8.5)
                cv.drawString(cx+0.28*cm,y0+ch*0.20,line2)

        # ── 6 tarjetas de secciones del reporte ───────────────────────────
        SECS=[("01","Señales Z-score","Spreads más alejados de su historial","#1d4ed8"),
              ("02","Carry & Fondeo","Ganancia neta vs tasa de referencia","#b45309"),
              ("03","Curva de Tasas","Pendiente y cambio por plazo","#0369a1"),
              ("04","Inflación Implícita","Breakevens Bonos M vs Udibonos","#047857"),
              ("05","CETES","Curvas y carry indicativo","#6d28d9"),
              ("06","Guía de Lectura","Cada métrica explicada en una línea","#b91c1c")]
        sw=(w-2.0*cm)/3-0.18*cm; sh=h*0.10; ys=y0-sh-0.50*cm
        for idx,(num,sec,desc,hx) in enumerate(SECS):
            ci=idx%3; ri=idx//3
            cx=0.9*cm+ci*(sw+0.22*cm); cy=ys-ri*(sh+0.16*cm)
            cv.setFillColor(colors.HexColor("#0d1f3c"))
            cv.roundRect(cx,cy,sw,sh,0.16*cm,fill=1,stroke=0)
            cv.setFillColor(colors.HexColor(hx))
            cv.rect(cx,cy+sh-0.13*cm,sw,0.13*cm,fill=1,stroke=0)
            cv.setFillColor(colors.HexColor(hx)); cv.setFont("Helvetica-Bold",17)
            cv.drawString(cx+0.28*cm,cy+sh*0.50,num)
            cv.setFillColor(C_WHITE); cv.setFont("Helvetica-Bold",9)
            cv.drawString(cx+0.28*cm,cy+sh*0.24,sec)
            cv.setFillColor(colors.HexColor("#94a3b8")); cv.setFont("Helvetica",7.2)
            cv.drawString(cx+0.28*cm,cy+0.07*cm,desc[:55])

        # footer
        cv.setFillColor(colors.HexColor("#475569")); cv.setFont("Helvetica",7.5)
        cv.drawString(1.5*cm,0.45*cm,"Material informativo · No constituye recomendación de inversión · Uso interno")
        cv.setFillColor(C_GOLD); cv.setFont("Helvetica-Bold",7.5)
        cv.drawRightString(w-1.1*cm,0.45*cm,"BONOS M 3.0  ·  V8 PREMIUM")


def _is_finite(x):
    try: return np.isfinite(float(x))
    except: return False


# ── KPI cards ──────────────────────────────────────────────────────────────────
def kpi_table(rows):
    norm=[]
    for r in rows:
        if isinstance(r,dict): norm.append((str(r.get("label","")),str(r.get("value","")),"blue"))
        elif isinstance(r,(list,tuple)) and len(r)==2: norm.append((str(r[0]),str(r[1]),"blue"))
        elif isinstance(r,(list,tuple)) and len(r)>=3: norm.append((str(r[0]),str(r[1]),r[2]))
    if not norm: return Spacer(1,0.1*cm)
    cw=25.4*cm/len(norm); cells=[]
    for label,value,accent in norm:
        ac=_ac(accent); sf=_sf(ac)
        nest=Table([
            [Paragraph(label.upper(),ParagraphStyle(f"kL{id(label)%9999}",fontName="Helvetica-Bold",
                fontSize=7,textColor=C_SOFT,alignment=TA_CENTER))],
            [Paragraph(value,ParagraphStyle(f"kV{id(label)%9999}",fontName="Helvetica-Bold",
                fontSize=15,textColor=C_INK,alignment=TA_CENTER,leading=17))],
        ],colWidths=[cw-0.26*cm])
        nest.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),sf),
            ("BOX",(0,0),(-1,-1),0.5,C_LINE),
            ("LINEABOVE",(0,0),(-1,0),4,ac),
            ("TOPPADDING",(0,0),(-1,-1),9),
            ("BOTTOMPADDING",(0,0),(-1,-1),9),
            ("LEFTPADDING",(0,0),(-1,-1),4),
            ("RIGHTPADDING",(0,0),(-1,-1),4),
        ]))
        cells.append(nest)
    t=Table([cells],colWidths=[cw]*len(cells),hAlign="CENTER")
    t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                           ("LEFTPADDING",(0,0),(-1,-1),2),
                           ("RIGHTPADDING",(0,0),(-1,-1),2)]))
    return t


# ── Tabla de datos con color de celda por Z ────────────────────────────────────
def table_from_df(df,columns,headers=None,max_rows=20,widths=None,z_col=None):
    """Renderiza DataFrame. Si z_col está presente, colorea fondo de esa columna según Z."""
    headers=headers or columns
    th=ParagraphStyle("v8TH",fontName="Helvetica-Bold",fontSize=9,
                      textColor=C_WHITE,alignment=TA_CENTER,leading=11)
    td=ParagraphStyle("v8TD",fontName="Helvetica",fontSize=9,
                      textColor=C_INK,alignment=TA_CENTER,leading=11)
    tdz_pos=ParagraphStyle("v8TZ+",fontName="Helvetica-Bold",fontSize=9,
                            textColor=C_GRN,alignment=TA_CENTER,leading=11)
    tdz_neg=ParagraphStyle("v8TZ-",fontName="Helvetica-Bold",fontSize=9,
                            textColor=C_RED,alignment=TA_CENTER,leading=11)

    data=[[Paragraph(str(h),th) for h in headers]]
    style_cmds=[
        ("BACKGROUND",(0,0),(-1,0),C_NAVY),
        ("TEXTCOLOR",(0,0),(-1,0),C_WHITE),
        ("GRID",(0,0),(-1,-1),0.35,C_LINE),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LINEBELOW",(0,0),(-1,0),2.5,C_BLUE),
    ]

    if df is None or (hasattr(df,"empty") and df.empty):
        data.append([Paragraph("Sin datos",td)]+[Paragraph("",td) for _ in headers[1:]])
    else:
        for row_i,(_,row) in enumerate(df.head(max_rows).iterrows()):
            bg=C_WHITE if row_i%2==0 else C_BLUE_S
            style_cmds.append(("BACKGROUND",(0,row_i+1),(-1,row_i+1),bg))
            line=[]
            for col in columns:
                val=row.get(col,"")
                try:
                    fv=float(val) if isinstance(val,(float,np.floating,int)) else float(str(val))
                    txt=fmt(fv,4)
                    if col==z_col or (z_col is None and "Z" in str(col) and "score" not in str(col).lower()):
                        sty=tdz_pos if fv>=0 else tdz_neg
                        # color background of this cell
                        ci=columns.index(col)
                        cell_bg=_z_sf(fv)
                        style_cmds.append(("BACKGROUND",(ci,row_i+1),(ci,row_i+1),cell_bg))
                        line.append(Paragraph(f"{fv:+.2f}",sty))
                        continue
                except: txt=str(val)
                line.append(Paragraph(txt,td))
            data.append(line)

    tbl=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT",splitByRow=1)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


# ── Image wrapper ──────────────────────────────────────────────────────────────
def img_flow(path,max_w=25.8*cm,max_h=15.3*cm):
    if not path or not Path(path).exists(): return []
    im=Image(str(path))
    w,h=im.imageWidth,im.imageHeight
    scale=min(max_w/w,max_h/h,1.0)
    im.drawWidth=w*scale; im.drawHeight=h*scale
    return [im,Spacer(1,0.2*cm)]


# ── Semáforo de secciones ──────────────────────────────────────────────────────
def _semaforo_row(label, value_txt, status, note):
    """status: 'red'|'amber'|'green'|'blue'"""
    COLOR={"red":C_RED,"amber":C_GOLD,"green":C_GRN,"blue":C_BLUE}
    BG={"red":C_RED_S,"amber":C_AMB_S,"green":C_GRN_S,"blue":C_BLUE_S}
    EMOJI={"red":"🔴","amber":"🟡","green":"🟢","blue":"🔵"}
    ac=COLOR.get(status,C_BLUE); bg=BG.get(status,C_BLUE_S)
    dot=Paragraph(EMOJI.get(status,"⚪"),ParagraphStyle("smDot",fontSize=14,leading=16,alignment=TA_CENTER))
    lbl=Paragraph(f"<b>{label}</b>",ParagraphStyle("smLbl",fontName="Helvetica-Bold",fontSize=10,leading=12,textColor=C_INK))
    val=Paragraph(value_txt,ParagraphStyle("smVal",fontName="Helvetica-Bold",fontSize=12,leading=14,textColor=ac))
    nt=Paragraph(note,ParagraphStyle("smNt",fontName="Helvetica",fontSize=8.5,leading=11,textColor=C_SOFT))
    return [dot,lbl,val,nt]


def build_semaforo_table(rows_data):
    """rows_data: list of (label, value_txt, status, note)"""
    rows=[[Paragraph("",ParagraphStyle("sh")),
           Paragraph("SECCIÓN",ParagraphStyle("sh",fontName="Helvetica-Bold",fontSize=8,textColor=C_WHITE)),
           Paragraph("SEÑAL CLAVE",ParagraphStyle("sh",fontName="Helvetica-Bold",fontSize=8,textColor=C_WHITE)),
           Paragraph("CONTEXTO",ParagraphStyle("sh",fontName="Helvetica-Bold",fontSize=8,textColor=C_WHITE))]]
    for r in rows_data:
        rows.append(_semaforo_row(*r))
    t=Table(rows,colWidths=[1.0*cm,4.8*cm,9.0*cm,10.6*cm],hAlign="LEFT")
    style=[
        ("BACKGROUND",(0,0),(-1,0),C_NAVY),
        ("TEXTCOLOR",(0,0),(-1,0),C_WHITE),
        ("LINEBELOW",(0,0),(-1,0),2,C_BLUE),
        ("GRID",(0,0),(-1,-1),0.35,C_LINE),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),7),
        ("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),7),
        ("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("ALIGN",(0,0),(0,-1),"CENTER"),
    ]
    for i in range(1,len(rows)):
        bg=C_WHITE if i%2==0 else C_BLUE_S
        style.append(("BACKGROUND",(0,i),(-1,i),bg))
    t.setStyle(TableStyle(style))
    return t


# ── Tarjeta de señal con Z grande ─────────────────────────────────────────────
def _signal_card(title,z_value,body,accent="blue",width=8.0*cm):
    ac=_ac(accent); sf=_sf(ac)
    try: zf=float(z_value); z_txt=f"{zf:+.2f}"; z_col=_z_ac(zf)
    except: z_txt=str(z_value); z_col=ac
    pt=Paragraph(title,ParagraphStyle("sc8T",fontName="Helvetica-Bold",fontSize=8.5,leading=10.5,textColor=ac))
    pz=Paragraph(z_txt,ParagraphStyle("sc8Z",fontName="Helvetica-Bold",fontSize=28,leading=32,textColor=z_col,alignment=TA_CENTER))
    pb=Paragraph(body,ParagraphStyle("sc8B",fontName="Helvetica",fontSize=8.5,leading=11.5,textColor=C_BODY))
    t=Table([[pt],[pz],[pb]],colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),sf),
        ("BOX",(0,0),(-1,-1),0.5,C_LINE),
        ("LINELEFT",(0,0),(0,-1),4,ac),
        ("LINEABOVE",(0,0),(-1,0),2.5,ac),
        ("LEFTPADDING",(0,0),(-1,-1),10),
        ("RIGHTPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),7),
        ("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("ALIGN",(0,1),(0,1),"CENTER"),
    ]))
    return t


# ── Etiqueta de sección ────────────────────────────────────────────────────────
def add_section_label(story,styles,title,subtitle=""):
    tp=Paragraph(title,ParagraphStyle("v8SecT",fontName="Helvetica-Bold",fontSize=17,leading=21,textColor=C_INK))
    bp=Paragraph("ANÁLISIS",ParagraphStyle("v8SecB",fontName="Helvetica-Bold",fontSize=8,leading=10,textColor=C_WHITE,alignment=TA_CENTER))
    t=Table([[tp,bp]],colWidths=[22.2*cm,3.2*cm],hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),C_WHITE),
        ("BACKGROUND",(1,0),(1,0),C_BLUE),
        ("BOX",(0,0),(-1,-1),0.5,C_LINE),
        ("LINEBELOW",(0,0),(-1,0),2.5,C_BLUE),
        ("LINELEFT",(0,0),(0,-1),5,C_GOLD),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),12),
        ("RIGHTPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),10),
        ("BOTTOMPADDING",(0,0),(-1,-1),10),
    ]))
    story.append(t)
    if subtitle:
        story.append(Paragraph(subtitle,ParagraphStyle("v8SecSub",fontName="Helvetica",
            fontSize=9.5,leading=12,textColor=C_SOFT,spaceAfter=2,leftIndent=5)))
    story.append(Spacer(1,0.18*cm))


# ── Tarjeta explicativa ────────────────────────────────────────────────────────
def explain_card(title,body,accent="blue",width=24.9*cm):
    ac=_ac(accent); sf=_sf(ac)
    pt=Paragraph(title,ParagraphStyle("v8ecT",fontName="Helvetica-Bold",fontSize=10.5,leading=13,textColor=C_INK))
    pb=Paragraph(body,ParagraphStyle("v8ecB",fontName="Helvetica",fontSize=9.5,leading=13,textColor=C_BODY))
    t=Table([[pt],[pb]],colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),sf),
        ("BOX",(0,0),(-1,-1),0.5,C_LINE),
        ("LINELEFT",(0,0),(0,-1),4.5,ac),
        ("LEFTPADDING",(0,0),(-1,-1),13),
        ("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),8),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),
    ]))
    return t


# ── Resumen ejecutivo ──────────────────────────────────────────────────────────
def build_reader_friendly_opening(story,styles,bonos,udis,report_date,
                                   matrix_days,curve_days,be_days,
                                   vector_path,funding_rate_pct,
                                   lf_path,lf_periods,general_amount):

    # ── computar todas las métricas ───────────────────────────────────────
    top_pair_txt="Sin datos"; top_z=float("nan")
    curve_msg="Sin datos"; carry_msg="Sin datos"
    be_msg="Sin datos"; lf_msg="Sin datos"
    pairs=pd.DataFrame(); metrics={}
    curve_status="blue"; carry_status="blue"
    be_status="blue"; lf_status="blue"; z_status="blue"

    try:
        sp_mx,z_mx,_,_,_,_,_=compute_spread_matrices(
            bonos,report_date-pd.Timedelta(days=matrix_days),report_date)
        pairs=best_pairs(z_mx,sp_mx,top_n=5)
        if not pairs.empty:
            top_pair_txt=pairs.iloc[0]["PAR"]
            top_z=float(pairs.iloc[0]["Z"])
            z_status="red" if abs(top_z)>=2 else ("amber" if abs(top_z)>=1 else "green")
    except Exception: pass

    try:
        _,d1,d2=compute_curve_table(bonos,report_date,
                                    report_date-pd.Timedelta(days=curve_days))
        metrics=curve_metrics(bonos,d1,d2)
        delta=metrics.get("delta_2s10s")
        if pd.notna(delta):
            dir_txt="empinó ↑" if delta>0 else "aplanó ↓"
            curve_msg=f"2s10s se {dir_txt} {abs(delta):+.2f} pb"
            curve_status="amber" if abs(float(delta))>5 else "green"
    except Exception: pass

    try:
        carry_tbl=load_carry_table(vector_path,funding_rate_pct=funding_rate_pct,monto=100_000_000)
        if carry_tbl is not None and not carry_tbl.empty:
            best_c=carry_tbl.sort_values("Carry",ascending=False).iloc[0]
            cv_=float(best_c["Carry"])
            carry_msg=f"{best_c['Serie']}  —  ${cv_:,.0f}"
            carry_status="green" if cv_>0 else "red"
    except Exception: pass

    try:
        if udis is not None:
            be_tbl,_=compute_breakeven_snapshot(bonos,udis,report_date)
            if be_tbl is not None and not be_tbl.empty and "Z_BE" in be_tbl.columns:
                ext=(be_tbl.assign(AZ=be_tbl["Z_BE"].abs())
                           .sort_values("AZ",ascending=False).iloc[0])
                bz=float(ext["Z_BE"])
                be_msg=f"{ext['SERIE_UDI']}  Z={bz:+.2f}"
                be_status="red" if abs(bz)>=2 else ("amber" if abs(bz)>=1 else "green")
    except Exception: pass

    try:
        if lf_path and Path(lf_path).exists():
            lfr=compute_lf_regression_and_zscore(lf_path,report_date,degree=3,periods=lf_periods)
            zdf=(lfr["z"].copy().assign(AZ=lambda x:x["Z-score"].abs())
                         .sort_values("AZ",ascending=False))
            if not zdf.empty:
                lz=float(zdf.iloc[0]["Z-score"])
                lf_msg=f"{zdf.iloc[0]['Serie']}  Z={lz:+.2f}"
                lf_status="red" if abs(lz)>=2 else ("amber" if abs(lz)>=1 else "green")
    except Exception: pass

    # ── Hero ──────────────────────────────────────────────────────────────
    hero=Table([
        [Paragraph("Resumen Ejecutivo del Día",
            ParagraphStyle("v8HT",fontName="Helvetica-Bold",fontSize=26,leading=31,textColor=C_INK))],
        [Paragraph(
            "Señales ordenadas por urgencia. Los pares con <b>Z fuera de ±2</b> requieren atención inmediata. "
            "El semáforo de abajo te dice en 5 segundos qué secciones tienen algo hoy.",
            ParagraphStyle("v8HB",fontName="Helvetica",fontSize=11,leading=14.5,textColor=C_BODY))],
    ],colWidths=[24.6*cm],hAlign="LEFT")
    hero.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),C_WHITE),
        ("BOX",(0,0),(-1,-1),0.5,C_LINE),
        ("LINELEFT",(0,0),(0,-1),7,C_BLUE),
        ("LINEABOVE",(0,0),(-1,0),2.5,C_BLUE),
        ("LEFTPADDING",(0,0),(-1,-1),16),
        ("RIGHTPADDING",(0,0),(-1,-1),16),
        ("TOPPADDING",(0,0),(-1,-1),13),
        ("BOTTOMPADDING",(0,0),(-1,-1),13),
    ]))
    story.append(hero)
    story.append(Spacer(1,0.22*cm))

    # ── KPIs ──────────────────────────────────────────────────────────────
    story.append(kpi_table([
        ("Fecha",str(pd.Timestamp(report_date).date()),"blue"),
        ("Ventana",f"{matrix_days} días","purple"),
        ("Fondeo",f"{funding_rate_pct:.2f} %","amber"),
        ("Bonos M",str(len(bonos.pivot.columns)),"green"),
        ("Udibonos",str(len(udis.pivot.columns)) if udis else "0","emerald"),
        ("Monto",f"${general_amount:,.0f}","sky"),
    ]))
    story.append(Spacer(1,0.22*cm))

    # ── Semáforo de secciones ─────────────────────────────────────────────
    story.append(Paragraph("Estado del mercado hoy",
        ParagraphStyle("v8Sub",fontName="Helvetica-Bold",fontSize=12,leading=15,
                       textColor=C_NAVY,spaceAfter=5)))
    sem_rows=[
        ("Z-score Bonos M",
         f"Par más extremo: {top_pair_txt}  |  Z = {top_z:+.2f}" if _is_finite(top_z) else top_pair_txt,
         z_status,
         "Z fuera de ±2 = señal de dislocación. Revisar gráfica histórica y spread vs media."),
        ("Curva de tasas",curve_msg,curve_status,
         "Cambio en pendiente 2s10s. Curva empinándose = favorece posiciones en corto plazo."),
        ("Carry neto",carry_msg,carry_status,
         "Carry positivo = instrumento paga más que el costo de fondeo. Punto de partida del análisis."),
        ("Breakeven / Inflación",be_msg,be_status,
         "Z_BE fuera de ±2 = inflación implícita alejada de su rango habitual."),
        ("CETES / Renta fija",carry_msg,carry_status,
         "Residuo vs curva teórica grado 3. Series alejadas del modelo = candidatos a revisión."),
    ]
    story.append(build_semaforo_table(sem_rows))
    story.append(Spacer(1,0.22*cm))

    # ── Top 5 pares con Z grande ──────────────────────────────────────────
    if not pairs.empty:
        story.append(Paragraph("Top 5 pares por |Z-score| — Bonos M",
            ParagraphStyle("v8Sub2",fontName="Helvetica-Bold",fontSize=12,leading=15,
                           textColor=C_NAVY,spaceAfter=5)))
        pcards=[]
        for _,row in pairs.head(5).iterrows():
            zv=float(row["Z"])
            ac="red" if zv<=-2 else ("green" if zv>=2 else "amber")
            pcards.append(_signal_card(
                row["PAR"],zv,
                f"Spread {fmt(row['SPREAD'],4)}  |  |Z| {abs(zv):.2f}",
                accent=ac,width=4.9*cm))
        while len(pcards)<5: pcards.append(Spacer(1,0.1*cm))
        pt=Table([pcards],colWidths=[5.0*cm]*5,hAlign="CENTER")
        pt.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                ("LEFTPADDING",(0,0),(-1,-1),2),
                                ("RIGHTPADDING",(0,0),(-1,-1),2)]))
        story.append(pt)
    story.append(PageBreak())


# ── Glosario ───────────────────────────────────────────────────────────────────
def build_plain_language_glossary(story,styles):
    add_section_label(story,styles,"Guía de conceptos",
        "Cada métrica explicada en lenguaje directo antes del análisis técnico.")
    BLOCKS=[
        ("Z-score","Qué tan raro es el valor de hoy vs su historial. "
         "<b>>+2 o <−2</b> = señal que merece revisión. Cerca de 0 = comportamiento normal.","blue"),
        ("Spread","Diferencia de tasas entre dos instrumentos. Si se amplió demasiado puede indicar "
         "oportunidad de <b>compresión</b>. Si se cerró, posible riesgo de <b>apertura</b>.","sky"),
        ("Carry","Ganancia estimada de mantener una posición menos el costo de fondeo. "
         "<b>Positivo</b> = el instrumento paga más que el fondeo.","green"),
        ("Breakeven","Inflación que el mercado 'descuenta' entre bonos nominales y Udibonos. "
         "Si sube = el mercado espera <b>más inflación futura</b>.","amber"),
        ("DV01","Sensibilidad monetaria ante 1 punto base de movimiento. "
         "Útil para <b>dimensionar el riesgo</b> de una posición.","purple"),
        ("Curvas y carry","Indicadores orientativos de tasas y carry. "
         "Los más alejados son <b>candidatos prioritarios</b> de análisis.","red"),
    ]
    rows2=[]
    for i in range(0,len(BLOCKS),2):
        ca=explain_card(BLOCKS[i][0],BLOCKS[i][1],BLOCKS[i][2],width=12.1*cm)
        cb=(explain_card(BLOCKS[i+1][0],BLOCKS[i+1][1],BLOCKS[i+1][2],width=12.1*cm)
            if i+1<len(BLOCKS) else Spacer(1,0.1*cm))
        rows2.append([ca,cb])
    gl=Table(rows2,colWidths=[12.45*cm,12.45*cm],hAlign="CENTER")
    gl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                            ("LEFTPADDING",(0,0),(-1,-1),3),
                            ("RIGHTPADDING",(0,0),(-1,-1),3),
                            ("TOPPADDING",(0,0),(-1,-1),4),
                            ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(gl)
    story.append(Spacer(1,0.2*cm))
    story.append(explain_card(
        "🚦  Cómo leer los colores en tablas y tarjetas",
        "<font color='#047857'><b>Verde</b></font> = favorable / por arriba del modelo / Z positivo.   "
        "<font color='#b91c1c'><b>Rojo</b></font> = adverso / por debajo / Z negativo extremo.   "
        "<font color='#b45309'><b>Dorado/Ámbar</b></font> = requiere revisión / Z en zona media.   "
        "<font color='#1d4ed8'><b>Azul</b></font> = métrica informativa neutral.   "
        "Los colores <b>priorizan la lectura</b> — no son señales automáticas de compra o venta.",
        "amber",width=25.0*cm))
    story.append(PageBreak())


# ── generate_pdf ──────────────────────────────────────────────────────────────
def generate_pdf(bonos,udis,out_path,report_date,
                 matrix_days=60,curve_days=30,top_n=5,be_days=60,
                 vector_path=None,funding_rate_pct=6.50,
                 lf_path=None,lf_periods=180,general_amount=100_000_000):

    out_path=Path(out_path)
    out_path.parent.mkdir(parents=True,exist_ok=True)
    styles=make_styles()

    doc=BaseDocTemplate(str(out_path),pagesize=landscape(A4),
                        leftMargin=1.0*cm,rightMargin=1.0*cm,
                        topMargin=1.55*cm,bottomMargin=1.4*cm)
    frame=Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id="main")
    doc.addPageTemplates([PageTemplate(id="main",frames=[frame],onPage=on_page)])

    # Pre-compute para portada
    top_pair_txt="—"; top_z=float("nan")
    curve_msg="—"; carry_msg="—"; be_msg="—"; lf_msg="—"
    try:
        sp_mx,z_mx,_,_,_,_,_=compute_spread_matrices(
            bonos,report_date-pd.Timedelta(days=matrix_days),report_date)
        p=best_pairs(z_mx,sp_mx,top_n=1)
        if not p.empty: top_pair_txt=p.iloc[0]["PAR"]; top_z=float(p.iloc[0]["Z"])
    except Exception: pass
    try:
        _,d1,d2=compute_curve_table(bonos,report_date,
                                    report_date-pd.Timedelta(days=curve_days))
        m=curve_metrics(bonos,d1,d2); delta=m.get("delta_2s10s")
        if pd.notna(delta): curve_msg=f"2s10s {'empinó' if delta>0 else 'aplanó'} {abs(delta):+.2f} pb"
    except Exception: pass
    try:
        ct=load_carry_table(vector_path,funding_rate_pct=funding_rate_pct,monto=100_000_000)
        if ct is not None and not ct.empty:
            bc=ct.sort_values("Carry",ascending=False).iloc[0]
            carry_msg=f"{bc['Serie']}  ${float(bc['Carry']):,.0f}"
    except Exception: pass
    try:
        if udis is not None:
            bt,_=compute_breakeven_snapshot(bonos,udis,report_date)
            if bt is not None and not bt.empty and "Z_BE" in bt.columns:
                ex=(bt.assign(AZ=bt["Z_BE"].abs()).sort_values("AZ",ascending=False).iloc[0])
                be_msg=f"{ex['SERIE_UDI']}  Z={float(ex['Z_BE']):+.2f}"
    except Exception: pass
    try:
        if lf_path and Path(lf_path).exists():
            lr=compute_lf_regression_and_zscore(lf_path,report_date,degree=3,periods=lf_periods)
            zd=(lr["z"].copy().assign(AZ=lambda x:x["Z-score"].abs())
                       .sort_values("AZ",ascending=False))
            if not zd.empty: lf_msg=f"{zd.iloc[0]['Serie']}  Z={float(zd.iloc[0]['Z-score']):+.2f}"
    except Exception: pass

    story=[]
    story.append(_CoverFlowable(report_date,bonos.name,
                                top_pair_txt,top_z,curve_msg,carry_msg,
                                be_msg,lf_msg,
                                len(bonos.pivot.columns),
                                len(udis.pivot.columns) if udis else 0,
                                funding_rate_pct))
    story.append(PageBreak())

    with tempfile.TemporaryDirectory() as _td:
        tmp=Path(_td)

        build_reader_friendly_opening(story,styles,bonos,udis,report_date,
            matrix_days,curve_days,be_days,vector_path,funding_rate_pct,
            lf_path,lf_periods,general_amount)

        build_plain_language_glossary(story,styles)

        build_executive_summary_page(story,styles,bonos,udis,report_date,
            matrix_days,curve_days,top_n,be_days,vector_path,funding_rate_pct,tmp)

        build_dataset_section(story,styles,bonos,report_date,
            matrix_days,curve_days,top_n,tmp,
            vector_path=vector_path,funding_rate_pct=funding_rate_pct)

        if udis is not None:
            build_dataset_section(story,styles,udis,report_date,
                matrix_days,curve_days,top_n,tmp,
                vector_path=None,funding_rate_pct=funding_rate_pct)
            add_udibono_carry_section(story,styles,vector_path,funding_rate_pct,tmp)
            build_breakeven_section(story,styles,bonos,udis,report_date,be_days,tmp)

        build_lf_regression_section(story,styles,lf_path,report_date,tmp,
            degree=3,periods=lf_periods)

        build_general_cetes_bi_section(story,styles,vector_path,
            funding_rate_pct,general_amount,tmp)

        add_section_label(story,styles,"Notas metodológicas",
            "Referencia técnica sobre cálculos y origen de los datos.")
        NOTAS=[
            ("Matrices","Parte triangular inferior — igual que el grid Tkinter original."),
            ("Gradiente","get_gradient_color(ratio): ratio bajo → rojo, ratio alto → azul."),
            ("Z-score","Z = (último spread − media del período) / desviación estándar del período."),
            ("Pares extremos","Los pares de mayor |Z| se muestran con gráfica histórica + histograma."),
            ("Breakeven","Tasa nominal aproximada por interpolación al tenor de cada Udibono."),
            
        ]
        for cat,nota in NOTAS:
            story.append(Paragraph(
                f"<font color='#1d4ed8'><b>{cat}:</b></font>  {nota}",
                ParagraphStyle("v8Nota",fontName="Helvetica",fontSize=10,
                               leading=13.5,textColor=C_BODY,leftIndent=8,spaceAfter=5)))

        cleanup_story_pagebreaks(story)
        while story and isinstance(story[-1],PageBreak): story.pop()
        doc.build(story)
    return out_path


# ── main ──────────────────────────────────────────────────────────────────────
def main(argv=None):
    ap=argparse.ArgumentParser(description="Reporte PDF V8 Premium — Renta Fija MX")
    ap.add_argument("--source-script",default=None)
    ap.add_argument("--bonos",default=None)
    ap.add_argument("--udis",default=None)
    ap.add_argument("--out",default=None)
    ap.add_argument("--date",default=None)
    ap.add_argument("--matrix-days",type=int,default=60)
    ap.add_argument("--curve-days",type=int,default=30)
    ap.add_argument("--be-days",type=int,default=60)
    ap.add_argument("--vector",default=None)
    ap.add_argument("--lf",default=None)
    ap.add_argument("--lf-periods",type=int,default=180)
    ap.add_argument("--funding-rate",type=float,default=6.50)
    ap.add_argument("--general-amount",type=float,default=100_000_000)
    ap.add_argument("--top",type=int,default=5)
    ap.add_argument("--no-udis",action="store_true")
    args=ap.parse_args(argv)

    paths=parse_literal_paths_from_script(args.source_script)
    bonos_path=args.bonos or paths.get("FILE_PATH") or DEFAULT_BONOS
    udis_path=args.udis or paths.get("FILE_PATH_UDI") or DEFAULT_UDIS
    vector_path=args.vector or str(Path(bonos_path).parent/"vector.csv")
    lf_path=args.lf or str(Path(bonos_path).parent/"LF_PYTHON.csv")

    print("Cargando Bonos M …")
    bonos=load_dataset(bonos_path,"Bonos M")
    udis=None
    if not args.no_udis:
        try:
            print("Cargando Udibonos …")
            udis=load_dataset(udis_path,"Udibonos")
        except Exception as e:
            print(f"Aviso: no se pudo cargar Udibonos ({e}). Solo Bonos M.")

    if args.date:
        report_date=pd.Timestamp(args.date)
    else:
        if udis is not None:
            common=sorted(set(bonos.pivot.index)&set(udis.pivot.index))
            report_date=pd.Timestamp(common[-1]) if common else bonos.last_date
        else:
            report_date=bonos.last_date
    report_date=nearest_available_date(bonos.pivot,report_date)

    out=(Path(args.out) if args.out
         else Path.cwd()/"reportes_pdf"/f"BONOS_M_V8_{report_date:%Y%m%d}.pdf")

    print(f"Generando PDF V8 Premium → {out}")
    generate_pdf(bonos,udis,out,report_date,
                 args.matrix_days,args.curve_days,args.top,args.be_days,
                 vector_path=vector_path,funding_rate_pct=args.funding_rate,
                 lf_path=lf_path,lf_periods=args.lf_periods,
                 general_amount=args.general_amount)
    print(f"✓ Listo: {out}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())