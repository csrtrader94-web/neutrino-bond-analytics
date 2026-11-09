"""Panel de apertura NEUTRINO: señales históricas o snapshot manual."""
from __future__ import annotations
import numpy as np
import pandas as pd
import streamlit as st
import report_engine as eng
from quant_modules import _scout, _active_data
from live_market import _analyze, _pca_live, _severity, _color_alarm


def _sem_table(df, zcol='Z', threshold=2.0):
    if df.empty:
        st.info('Sin observaciones suficientes para esta sección.')
        return
    d=df.copy()
    d.insert(0, 'Semáforo', d[zcol].apply(lambda x: _severity(x, threshold)))
    numeric=[c for c in d.select_dtypes(include='number').columns if c != 'Obs.']
    st.dataframe(d.style.map(_color_alarm,subset=['Semáforo']).format({c:'{:+.2f}' for c in numeric},na_rep='n/d'),use_container_width=True,hide_index=True)


def _be_rank(bonos, udis, asof, count=3, window=120):
    """BE con historia de referencia anterior al snapshot; interpolación nominal de report_engine."""
    snapshot, d=eng.compute_breakeven_snapshot(bonos,udis,asof)
    if snapshot.empty:return pd.DataFrame()
    # Historial calendario holgado para reunir N observaciones de los dos mercados.
    start=d-pd.Timedelta(days=max(90,round(window*1.8)))
    rows=[]
    for _,r in snapshot.iterrows():
        series=str(r['UDI'])
        h=eng.breakeven_history(bonos,udis,series,start,d)
        prior=h.loc[pd.to_datetime(h['Fecha'])<d,'BREAKEVEN'].dropna().tail(window) if not h.empty else pd.Series(dtype=float)
        if len(prior)<20:continue
        sig=float(prior.std(ddof=1))
        if not np.isfinite(sig) or sig<1e-10:continue
        current=float(r['BREAKEVEN'])
        z=(current-float(prior.mean()))/sig
        rows.append({'Udibono':series,'BE actual (%)':current,'Media BE (%)':float(prior.mean()),'Z':z,'|Z|':abs(z)})
    if not rows:return pd.DataFrame()
    return pd.DataFrame(rows).sort_values('|Z|',ascending=False).head(count).drop(columns='|Z|')


def _stability_top(bonos, asof):
    pv=_active_data(bonos,asof)
    df=_scout(pv)
    if df.empty:return pd.DataFrame()
    cols=['Z30','Z60','Z120','Z250']
    df['Ventanas']=df[cols].notna().sum(axis=1)
    df['Consistente']=df[cols].apply(lambda x: bool((x.dropna()>0).all() or (x.dropna()<0).all()) if x.notna().sum()>=2 else False,axis=1)
    df['Dispersión']=df[cols].std(axis=1)
    df['Score']=df[cols].abs().mean(axis=1)/(1+df['Dispersión'].fillna(0))
    df.loc[~df['Consistente'],'Score']*=0.5
    return df.sort_values(['Consistente','Score'],ascending=[False,False]).head(5)[['Par','Z30','Z60','Z120','Z250','Score','Consistente']]


def _historical_pca(hist, asof, window=120):
    """Evalúa el último movimiento como si fuera una fotografía fuera de muestra."""
    before=hist.pivot.loc[hist.pivot.index<=pd.Timestamp(asof)].sort_index()
    if len(before)<45:return pd.DataFrame()
    latest=before.index[-1]
    if len(before)<2:return pd.DataFrame()
    quote=before.iloc[-1].dropna().to_dict()
    pca,note=_pca_live(hist,latest,quote,window)
    return pca


def render_summary(bonos_hist,udis_hist,bonos,udis,asof):
    st.header('NEUTRINO | Radar de mercado')
    snap=st.session_state.get('live_snapshot')
    if snap:
        day=pd.Timestamp(snap['date'])
        st.caption(f'Fotografía de tasas capturadas: {day:%d/%m/%Y}. El radar utiliza tasas actuales cuando hay cotizaciones completas; la muestra histórica no se modifica.')
    else:
        day=pd.Timestamp(asof)
        st.caption(f'Último histórico disponible: {day:%d/%m/%Y}. Para utilizar tasas de mercado actuales, ve a la última pestaña «ACTUALIZAR TASAS».')
    threshold=st.selectbox('Umbral del semáforo del radar (σ)',[1.5,2.0,2.5,3.0],index=1,key='summary_threshold')
    window=st.selectbox('Ventana RV y PCA del radar (observaciones)',[60,120,250],index=1,key='summary_window')
    if snap:
        _,rv_m,pca_m,_=_analyze(bonos_hist,day,snap['m'],window) if snap.get('m') else (None,pd.DataFrame(),pd.DataFrame(),'')
        _,rv_u,pca_u,_=_analyze(udis_hist,day,snap['u'],window) if snap.get('u') else (None,pd.DataFrame(),pd.DataFrame(),'')
    else:
        rv_m=_scout(_active_data(bonos,day))
        rv_u=_scout(_active_data(udis,day))
        pca_m=_historical_pca(bonos_hist,day,window)
        pca_u=_historical_pca(udis_hist,day,window)
    zcol=f'Z{window}'
    st.subheader('Top 5 · Extremos RV Bonos M')
    if not rv_m.empty:
        r=rv_m.dropna(subset=[zcol]).copy().assign(_abs=lambda d:d[zcol].abs()).sort_values('_abs',ascending=False).head(5)
        _sem_table(r[['Par','Spread actual (pb)',zcol]].rename(columns={zcol:'Z'}),threshold=threshold)
    else:st.info('Sin spreads RV con historia coincidente.')
    st.subheader('Top 3 · Extremos Breakeven')
    be=_be_rank(bonos,udis,day,3,window)
    _sem_table(be,threshold=threshold)
    a,b=st.columns(2)
    with a:
        st.subheader('Top 5 · PCA Bonos M')
        if not pca_m.empty:
            d=pca_m.sort_values('|Z PCA|',ascending=False).head(5)
            _sem_table(d[['Emisión','Residual PCA (pb)','Z PCA']].rename(columns={'Z PCA':'Z'}),threshold=threshold)
        else:st.info('No hay PCA con suficientes emisiones.')
    with b:
        st.subheader('Top 5 · PCA Udibonos')
        if not pca_u.empty:
            d=pca_u.sort_values('|Z PCA|',ascending=False).head(5)
            _sem_table(d[['Emisión','Residual PCA (pb)','Z PCA']].rename(columns={'Z PCA':'Z'}),threshold=threshold)
        else:st.info('No hay PCA con suficientes emisiones.')
    st.subheader('Top 5 · Estabilidad estadística Bonos M')
    stab=_stability_top(bonos,day)
    if not stab.empty:
        # Semáforo definido por Z120, no por score no-direccional.
        _sem_table(stab.rename(columns={'Z120':'Z'}),threshold=threshold)
    else:st.info('Sin estabilidad evaluable.')
    st.caption('🟢 extremo positivo · 🔴 extremo negativo · 🟡 dentro del rango. Son clasificaciones estadísticas, no recomendaciones ejecutables. En estabilidad el color usa Z120; el Score mide consistencia entre ventanas.')
