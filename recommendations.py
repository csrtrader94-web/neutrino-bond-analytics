"""Screening direccional de RV y BE para la pestaña de actualización."""
import numpy as np
import pandas as pd
import streamlit as st
import report_engine as eng
from live_market import overlay, _analyze, _severity, _color_alarm
from summary_dashboard import _be_rank


def _ranking(rv, window):
    """Cada par largo-corto suma +Z al largo y -Z al corto (tasas, no precios).
    Z positivo => rendimiento largo relativamente alto => barato relativo, bajo condiciones comparables.
    """
    zcol=f'Z{window}'
    if rv.empty or zcol not in rv:return pd.DataFrame()
    contrib=[]
    for _,r in rv.dropna(subset=[zcol]).iterrows():
        z=float(r[zcol])
        if not np.isfinite(z):continue
        contrib.extend([{'Emisión':str(r['Largo']),'RV Z':z}, {'Emisión':str(r['Corto']),'RV Z':-z}])
    if not contrib:return pd.DataFrame()
    d=pd.DataFrame(contrib).groupby('Emisión')['RV Z'].agg(['mean','count']).reset_index()
    d.columns=['Emisión','Score RV','Pares evaluados']
    d=d.loc[d['Pares evaluados']>=3].sort_values('Score RV',ascending=False)
    return d


def _choice(df, side, threshold):
    if df.empty:return None
    subset=df.loc[df['Score RV']>0] if side=='Compra' else df.loc[df['Score RV']<0]
    if subset.empty:return None
    row=subset.iloc[0] if side=='Compra' else subset.iloc[-1]
    return row


def _display_choice(r, family, side, threshold):
    if r is None:
        st.info(f'{side} {family}: no se identificó un candidato con suficiente evidencia RV.')
        return
    score=float(r['Score RV']); tag=_severity(score,threshold)
    st.markdown(f'**{side} relativa · {family}: {r["Emisión"]}**')
    st.caption(f'Score RV promedio {score:+.2f}σ · {int(r["Pares evaluados"])} spreads · {tag}')


def render_recommendations(bonos_hist,udis_hist,snap,win,threshold):
    st.divider()
    st.header('Radar de oportunidades · Tasas actuales')
    st.caption('Candidatos estadísticos basados únicamente en RV entre emisiones. Compra = mayor rendimiento relativo (más barato en precio); venta = menor rendimiento relativo (más caro). Ranking por promedio de Z de los spreads incidentes; requiere al menos 3 pares. No incorpora bid/ask, DV01 ni costo de fondeo.')
    day=pd.Timestamp(snap['date'])
    a,b=st.columns(2)
    for column,family,ds,key in [(a,'Bonos M',bonos_hist,'m'),(b,'Udibonos',udis_hist,'u')]:
        with column:
            st.subheader(family)
            if not snap.get(key):
                st.warning('Sin tasas capturadas');continue
            _,rv,_,_=_analyze(ds,day,snap[key],win)
            ranked=_ranking(rv,win)
            _display_choice(_choice(ranked,'Compra',threshold),family,'Compra',threshold)
            _display_choice(_choice(ranked,'Venta',threshold),family,'Venta',threshold)
            if not ranked.empty:
                ranked=ranked.assign(Semáforo=lambda d:d['Score RV'].apply(lambda z:_severity(z,threshold)))
                st.dataframe(ranked[['Semáforo','Emisión','Score RV','Pares evaluados']].style.map(_color_alarm,subset=['Semáforo']).format({'Score RV':'{:+.2f}'}),use_container_width=True,hide_index=True,height=270)
    st.subheader('Breakeven · Mejor extremo positivo y negativo')
    if not snap.get('m') or not snap.get('u'):
        st.info('Para calcular el BE actual se requieren tasas de ambos mercados en la misma fecha.')
        return
    m=overlay(bonos_hist,day,snap['m']);u=overlay(udis_hist,day,snap['u'])
    be=_be_rank(m,u,day,999,win)
    if be.empty:
        st.info('No hay BE con al menos 20 observaciones históricas comparables.')
        return
    positive=be[be['Z']>0].sort_values('Z',ascending=False)
    negative=be[be['Z']<0].sort_values('Z',ascending=True)
    p,n=st.columns(2)
    with p:
        if not positive.empty:
            row=positive.iloc[0]
            st.markdown(f'**BE positivo · {row["Udibono"]}**')
            st.metric('Breakeven actual',f'{row["BE actual (%)"]:.2f}%',f'Z {row["Z"]:+.2f}σ')
        else:st.info('No se identificó BE con Z positivo.')
    with n:
        if not negative.empty:
            row=negative.iloc[0]
            st.markdown(f'**BE negativo · {row["Udibono"]}**')
            st.metric('Breakeven actual',f'{row["BE actual (%)"]:.2f}%',f'Z {row["Z"]:+.2f}σ')
        else:st.info('No se identificó BE con Z negativo.')
    be=be.assign(Semáforo=lambda d:d['Z'].apply(lambda z:_severity(z,threshold)))
    st.dataframe(be[['Semáforo','Udibono','BE actual (%)','Media BE (%)','Z']].style.map(_color_alarm,subset=['Semáforo']).format({'BE actual (%)':'{:.3f}','Media BE (%)':'{:.3f}','Z':'{:+.2f}'}),use_container_width=True,hide_index=True)
    st.caption('BE positivo/negativo se refiere a la desviación del breakeven frente a su propia historia, no a inflación negativa. Un BE alto/bajo no implica por sí solo una operación ejecutable; considerar diferencias de duración, inflación implícita, liquidez y costos.')
