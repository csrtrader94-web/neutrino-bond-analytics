"""NEUTRINO: fotografía intradía manual, sin modificar los Excel históricos."""
from __future__ import annotations
from datetime import date
import re
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from quant_modules import _scout

WINDOWS=(30,60,120,250)

def _maturity(sym):
    m=re.search(r'(\d{6})',str(sym))
    if not m:return pd.NaT
    try:return pd.to_datetime(m.group(1),format='%y%m%d')
    except ValueError:return pd.NaT

def seed(ds, day):
    history=ds.pivot.sort_index()
    last=history.iloc[-1].dropna()
    data=[]
    for sym,val in last.items():
        mat=_maturity(sym)
        if pd.notna(mat) and mat>pd.Timestamp(day):
            data.append({'Emisión':str(sym),'Tasa actual (%)':round(float(val),4)})
    return pd.DataFrame(data).sort_values('Emisión',key=lambda s:s.map(_maturity)).reset_index(drop=True)

def check_inputs(df, day, ds):
    if df.empty:return {}
    if not {'Emisión','Tasa actual (%)'}.issubset(df):raise ValueError('Faltan columnas')
    if df['Emisión'].duplicated().any():raise ValueError('Hay emisiones duplicadas')
    allowed=set(map(str,ds.pivot.columns))
    out={}
    for _,r in df.iterrows():
        s=str(r['Emisión']); v=pd.to_numeric(r['Tasa actual (%)'],errors='coerce')
        if s not in allowed:raise ValueError(f'Emisión no reconocida: {s}')
        if pd.isna(v):continue # permitir exclusión dejando en blanco
        if not np.isfinite(v) or not -5 <= float(v) <= 40:raise ValueError(f'Tasa fuera de rango en {s}')
        if _maturity(s)<=pd.Timestamp(day):raise ValueError(f'Emisión vencida: {s}')
        out[s]=float(v)
    return out

def overlay(ds, day, quotes):
    """Solo altera una copia de la sesión. Nunca guarda sobre el Excel."""
    import copy
    new=copy.copy(ds)
    piv=ds.pivot.copy()
    when=pd.Timestamp(day)
    if when<=piv.index.max():
        raise ValueError('La fecha de captura debe ser posterior al último histórico; no se permite sustituir datos anteriores.')
    # No arrastrar automáticamente valores antiguos: solo emisiones capturadas.
    snapshot=pd.DataFrame([quotes],index=pd.DatetimeIndex([when]))
    new.pivot=pd.concat([piv,snapshot]).sort_index()
    new.last_date=when
    # La serie raw se amplía solo para herramientas que la necesitan.
    if hasattr(ds,'raw'):
        rows=[{'fecha':when,'SERIE':s,'RENDIMIENTO':v,'INSTRUMENTO':('M_BONOS_'+s if ds.name=='Bonos M' else 'S_UDIBONO_'+s)} for s,v in quotes.items()]
        new.raw=pd.concat([ds.raw,pd.DataFrame(rows)],ignore_index=True)
    return new

def _pca_live(ds, day, quotes, win):
    """Ajuste histórico previo a la fotografía, proyección fuera de muestra."""
    prior=ds.pivot.loc[ds.pivot.index<pd.Timestamp(day)].sort_index()
    if prior.empty:return pd.DataFrame(), 'Sin historia anterior'
    yesterday=prior.iloc[-1].dropna()
    syms=[s for s in quotes if s in yesterday.index]
    if len(syms)<4:return pd.DataFrame(), 'Se requieren al menos 4 emisiones con tasas actuales e historia previa'
    p=prior[syms].tail(win+15)
    count=p.notna().sum()
    syms=count[count>=max(25,int(len(p)*.85))].index.tolist()
    if len(syms)<4:return pd.DataFrame(), 'Cobertura histórica insuficiente para PCA'
    aligned=p[syms].ffill(limit=1).dropna()
    changes=(aligned.diff().dropna()*100).tail(win)
    if len(changes)<30:return pd.DataFrame(), 'Menos de 30 cambios diarios coincidentes'
    # Desechar columnas sin varianza; ajustar siempre con historia anterior.
    good=changes.std(ddof=1)>1e-10
    changes=changes.loc[:,good]
    if changes.shape[1]<4:return pd.DataFrame(), 'Menos de 4 emisiones con varianza válida'
    X=changes.to_numpy(float)
    mu=X.mean(axis=0)
    A=X-mu
    _,_,vh=np.linalg.svd(A,full_matrices=False)
    k=min(3,len(vh))
    components=vh[:k]
    historical_residual=A-(A@components.T)@components
    observed=np.array([(quotes[s]-yesterday[s])*100 for s in changes.columns],dtype=float)
    explained=((observed-mu)@components.T)@components+mu
    residual=observed-explained
    rows=[]
    for i,sym in enumerate(changes.columns):
        dist=historical_residual[:,i]
        sigma=dist.std(ddof=1)
        z=(residual[i]-dist.mean())/sigma if sigma>1e-10 else np.nan
        rows.append({'Emisión':sym,'Tasa actual (%)':quotes[sym], 'Cambio actual (pb)':observed[i],
                     'Cambio explicado PCA (pb)':explained[i],'Residual PCA (pb)':residual[i],
                     'Z PCA':z,'|Z PCA|':abs(z)})
    return pd.DataFrame(rows).sort_values('|Z PCA|',ascending=False), f'{len(changes)} cambios históricos; {len(changes.columns)} emisiones; {k} componentes; PCA entrenado sin la fecha nueva'

def _analyze(ds, day, quotes, win):
    if not quotes:return pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),'Sin tasas capturadas'
    updated=overlay(ds,day,quotes)
    pre=ds.pivot.sort_index()
    active=[s for s in quotes if s in pre.columns]
    z_rows=[]
    for s in active:
        hist=pre[s].dropna().tail(win)
        if len(hist)<20:continue
        sd=hist.std(ddof=1)
        z=(quotes[s]-hist.mean())/sd if sd>1e-12 else np.nan
        z_rows.append({'Emisión':s,'Tasa actual (%)':quotes[s],'Z nivel':z,'|Z nivel|':abs(z),
                       'Percentil histórico (%)':100*(hist<=quotes[s]).mean(),'Obs.':len(hist)})
    levels=pd.DataFrame(z_rows)
    if not levels.empty:levels=levels.sort_values('|Z nivel|',ascending=False)
    # Filtrar para tener spreads contemporáneos con ambas patas capturadas.
    pair_pivot=updated.pivot.reindex(columns=list(quotes))
    rv=_scout(pair_pivot)
    if not rv.empty:
        rv=rv.dropna(subset=[f'Z{win}']).copy()
        rv['|Z|']=rv[f'Z{win}'].abs()
        rv=rv.sort_values('|Z|',ascending=False)
    pca,note=_pca_live(ds,day,quotes,win)
    return levels,rv,pca,note

def panel(bonos_hist,udis_hist):
    st.header('Actualizar tasas | Market Snapshot')
    st.caption('Captura rendimientos de mercado en porcentaje: 8.7500 significa 8.75%. Los históricos originales permanecen intactos. Los cálculos se recalculan con las cotizaciones capturadas.')
    last=max(pd.Timestamp(bonos_hist.last_date),pd.Timestamp(udis_hist.last_date))
    minimum=(last+pd.Timedelta(days=1)).date()
    a,b,c=st.columns(3)
    day=a.date_input('Fecha de la fotografía',value=max(date.today(),minimum),min_value=minimum,key='live_date')
    win=b.selectbox('Ventana estadística (observaciones)',list(WINDOWS),index=2,key='live_window')
    threshold=c.selectbox('Alarma extrema |Z|', [1.5,2.0,2.5,3.0],index=1,key='live_threshold')
    if st.session_state.get('live_edit_day')!=str(day):
        st.session_state['live_edit_day']=str(day)
        st.session_state['live_editor_version']=st.session_state.get('live_editor_version',0)+1
    v=st.session_state['live_editor_version']
    with st.form('live_capture_form'):
        left,right=st.columns(2)
        with left:
            st.subheader('Bonos M')
            initial=seed(bonos_hist,day)
            m=st.data_editor(initial,use_container_width=True,hide_index=True,num_rows='fixed',
                disabled=['Emisión'],column_config={'Tasa actual (%)':st.column_config.NumberColumn(format='%.4f',step=.0001)},key=f'live_m_{v}')
        with right:
            st.subheader('Udibonos')
            initial=seed(udis_hist,day)
            u=st.data_editor(initial,use_container_width=True,hide_index=True,num_rows='fixed',
                disabled=['Emisión'],column_config={'Tasa actual (%)':st.column_config.NumberColumn(format='%.4f',step=.0001)},key=f'live_u_{v}')
        go=st.form_submit_button('Actualizar tasas y analizar',type='primary',use_container_width=True)
    if go:
        try:
            mq=check_inputs(m,day,bonos_hist); uq=check_inputs(u,day,udis_hist)
            if not mq and not uq:raise ValueError('Debes ingresar al menos una cotización')
            st.session_state['live_snapshot']={'date':str(day),'m':mq,'u':uq}
            st.success('Fotografía cargada. Se recalcularon las señales y las demás pestañas utilizarán esta fotografía cuando esté activa.')
            st.rerun()
        except Exception as e:st.error(str(e))
    snap=st.session_state.get('live_snapshot')
    if not snap:return
    if pd.Timestamp(snap['date'])<=last:
        st.error('La fecha guardada ya existe en la base histórica; descarta la fotografía.');return
    st.info(f"Fotografía activa: {snap['date']} · {len(snap['m'])} M · {len(snap['u'])} UDI · No se sobrescribieron los Excel históricos")
    if st.button('Descartar fotografía y regresar al histórico',key='live_clear'):
        st.session_state.pop('live_snapshot',None);st.rerun()
    results=[]
    for family,ds,quotes in [('Bonos M',bonos_hist,snap['m']),('Udibonos',udis_hist,snap['u'])]:
        st.subheader(f'Alertas · {family}')
        if not quotes:
            st.warning('Sin cotizaciones capturadas');continue
        lev,rv,pca,note=_analyze(ds,pd.Timestamp(snap['date']),quotes,win)
        extreme_levels=int((lev['|Z nivel|']>=threshold).sum()) if not lev.empty else 0
        extreme_rv=int((rv['|Z|']>=threshold).sum()) if not rv.empty else 0
        extreme_pca=int((pca['|Z PCA|']>=threshold).sum()) if not pca.empty else 0
        a,b,c=st.columns(3)
        a.metric('Extremos en nivel',extreme_levels)
        b.metric('Spreads extremos',extreme_rv)
        c.metric('Residuales PCA extremos',extreme_pca)
        if any((extreme_levels,extreme_rv,extreme_pca)):
            st.warning('Se detectaron extremos estadísticos; revisar liquidez, bid/ask, emisiones y contexto antes de operar.')
        else:st.success('No hay alertas que superen el umbral seleccionado.')
        t1,t2,t3=st.tabs(['Spreads / RV','PCA fuera de muestra','Niveles históricos'])
        with t1:
            if rv.empty:st.info('Faltan cotizaciones o historia coincidente para evaluar pares.')
            else:
                st.dataframe(rv[['Par','Spread actual (pb)',f'Z{win}','Hist. conjunto','Percentil (%)']].head(40),hide_index=True,use_container_width=True)
                st.caption('Spread = rendimiento de plazo largo menos plazo corto. Z positivo: spread más amplio; no implica por sí solo una compra.')
        with t2:
            st.caption(note)
            if pca.empty:st.info('No se dispone de una muestra suficiente para PCA.')
            else:
                st.dataframe(pca.drop(columns='|Z PCA|'),hide_index=True,use_container_width=True)
                st.caption('PCA estimado con cambios históricos anteriores y proyectado al movimiento actual. Residual positivo: la tasa subió más de lo explicado por los factores; no equivale directamente a precio barato.')
        with t3:
            if lev.empty:st.info('Histórico insuficiente')
            else:
                st.dataframe(lev.drop(columns='|Z nivel|'),hide_index=True,use_container_width=True)
                st.caption('El Z de nivel es descriptivo: puede reflejar ciclos de política monetaria, no desalineaciones de valor relativo.')
        results.append((family,lev,rv,pca))
    lines=[]
    for family,lev,rv,pca in results:
        for label,df,col in [('Niveles',lev,'Z nivel'),('RV',rv,f'Z{win}'),('PCA',pca,'Z PCA')]:
            if not df.empty:
                for _,r in df.iterrows():
                    if pd.notna(r[col]) and abs(r[col])>=threshold:
                        lines.append({'Mercado':family,'Modelo':label,'Instrumento/par':r.get('Par',r.get('Emisión','')),'Z':r[col],'Fecha':snap['date']})
    out=pd.DataFrame(lines,columns=['Mercado','Modelo','Instrumento/par','Z','Fecha'])
    st.subheader('Concentrado de alarmas')
    if out.empty:st.info('Sin alarmas extremas para este umbral.')
    else:
        out=out.assign(ABS_Z=out['Z'].abs()).sort_values('ABS_Z',ascending=False).drop(columns='ABS_Z')
        st.dataframe(out,hide_index=True,use_container_width=True)
        st.download_button('Descargar alarmas CSV',out.to_csv(index=False).encode('utf-8-sig'),file_name=f"NEUTRINO_ALERTAS_{snap['date']}.csv",mime='text/csv')
    rows=[{'Mercado':family,'Emisión':s,'Tasa actual (%)':v,'Fecha':snap['date']} for family,key in [('Bonos M','m'),('Udibonos','u')] for s,v in snap[key].items()]
    st.download_button('Exportar fotografía de tasas CSV',pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),file_name=f"NEUTRINO_TASAS_{snap['date']}.csv",mime='text/csv')
