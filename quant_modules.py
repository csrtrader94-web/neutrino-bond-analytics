"""Extensiones independientes: PCA, RV Scanner y estabilidad. No modifica report_engine.py."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

COLORS = ['#007f83','#e6a545','#355e96','#9c6db8','#d77a62']

def _standard_plot(fig, h=440):
    fig.update_layout(template='plotly_white', paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
        font=dict(color='#243a51', size=12), height=h, margin=dict(t=48,b=50,l=48,r=26),
        hovermode='x unified', legend=dict(orientation='h',y=1.12),
        xaxis=dict(showgrid=True, gridcolor='#edf2f7'),yaxis=dict(showgrid=True,gridcolor='#edf2f7'))
    return fig

def _series_order(pivot:pd.DataFrame, asof:pd.Timestamp):
    def maturity(s):
        import re
        match=re.search(r'(\d{6})',str(s))
        if not match:return pd.Timestamp.max
        try:return pd.to_datetime(match.group(1),format='%y%m%d')
        except:return pd.Timestamp.max
    return sorted(pivot.columns.astype(str),key=lambda s:(maturity(s),s))

def _active_data(ds, asof):
    piv=ds.pivot.copy()
    piv.columns=piv.columns.astype(str)
    piv=piv.loc[piv.index<=pd.Timestamp(asof)].sort_index()
    if piv.empty:return piv
    # Solo emisiones que efectivamente cotizan en la última fecha del histórico elegido
    active=piv.iloc[-1].dropna().index.tolist()
    return piv.reindex(columns=[s for s in _series_order(piv,asof) if s in active])

def _scout(pivot, windows=(30,60,120,250), min_history=18):
    """Historia simultánea por par; largo - corto; media previa excluye el último dato."""
    if pivot.empty:return pd.DataFrame()
    symbols=list(pivot.columns)
    results=[]
    for i in range(1,len(symbols)):
        long=symbols[i]
        for j in range(i):
            short=symbols[j]
            hist=(pivot[long]-pivot[short]).dropna()
            if len(hist)<min_history+1:continue
            current=float(hist.iloc[-1]); prev=hist.iloc[:-1]
            row={'Par':f'{long} − {short}','Largo':long,'Corto':short,'Spread actual (pb)':current*100,
                 'Fecha':hist.index[-1], 'Hist. conjunto':len(hist)}
            for win in windows:
                reference=prev.tail(win)
                if len(reference)<min(min_history,win):
                    row[f'Z{win}']=np.nan;continue
                sd=float(reference.std(ddof=1))
                row[f'Z{win}']=(current-float(reference.mean()))/sd if sd>1e-12 else np.nan
                if win==120:
                    row['Media (pb)']=float(reference.mean())*100
                    row['Sigma (pb)']=sd*100
                    row['Percentil (%)']=100*float((reference<=current).mean())
            results.append(row)
    return pd.DataFrame(results)

def _pair_traces(pivot,long,short,window):
    df=pivot[[long,short]].dropna().tail(window+1).copy()
    if df.empty:return None,None
    diff=df[long]-df[short]
    prior=diff.iloc[:-1]
    mean=float(prior.mean()) if len(prior) else np.nan
    std=float(prior.std(ddof=1)) if len(prior)>1 else np.nan
    f1=go.Figure()
    f1.add_trace(go.Scatter(x=df.index,y=df[long],name=f'Largo {long}',line=dict(color=COLORS[0],width=2)))
    f1.add_trace(go.Scatter(x=df.index,y=df[short],name=f'Corto {short}',line=dict(color=COLORS[2],width=2)))
    f1.update_yaxes(title='Rendimiento (%)')
    f2=go.Figure()
    if np.isfinite(std) and std>0:
        for k in [2,1]:
            f2.add_hrect(y0=(mean-k*std)*100,y1=(mean+k*std)*100,
                line_width=0,fillcolor=COLORS[0] if k==1 else COLORS[1],opacity=.085,
                annotation_text=f'±{k}σ',annotation_position='top left')
    f2.add_trace(go.Scatter(x=diff.index,y=diff*100,name='Spread largo − corto',line=dict(color=COLORS[0],width=2)))
    if np.isfinite(mean):f2.add_hline(y=mean*100,line_dash='dash',line_color=COLORS[1],annotation_text='Media previa')
    f2.update_yaxes(title='Diferencia (pb)')
    return _standard_plot(f1),_standard_plot(f2)

def render_scanner(bonos,udis,asof):
    st.header('Relative Value Scanner')
    st.caption('Cada par se evalúa con su propio histórico coincidente: rendimiento del vencimiento largo MENOS el corto. La observación actual no participa en la media ni sigma del Z-score. Un Z positivo indica ampliación respecto de su historia, no necesariamente una operación rentable.')
    c1,c2,c3=st.columns([1,1,1]); family=c1.selectbox('Mercado',['Bonos M','Udibonos'],key='rv_fam');window=c2.selectbox('Ventana histórica (observaciones)',[30,60,120,250],index=2,key='rv_win');sortby=c3.selectbox('Ordenar por',['Mayor |Z|','Z más positivo','Z más negativo'],key='rv_sort')
    ds=bonos if family=='Bonos M' else udis
    piv=_active_data(ds,asof)
    if piv.empty:st.warning('Sin datos para la fecha seleccionada');return
    ranked=_scout(piv)
    if ranked.empty:st.warning('No hay pares con suficiente histórico simultáneo.');return
    key=f'Z{window}'
    ranked=ranked.dropna(subset=[key]).copy()
    if ranked.empty:st.warning(f'No hay suficientes observaciones para ventana {window}');return
    ranked['|Z|']=ranked[key].abs()
    if sortby=='Mayor |Z|':ranked=ranked.sort_values('|Z|',ascending=False)
    elif sortby=='Z más positivo':ranked=ranked.sort_values(key,ascending=False)
    else:ranked=ranked.sort_values(key)
    a,b,c=st.columns(3)
    a.metric('Emisiones activas',len(piv.columns));b.metric('Pares evaluables',len(ranked));c.metric('Máximo |Z|',f"{ranked['|Z|'].max():.2f}")
    view=ranked[['Par','Spread actual (pb)',key,'|Z|','Media (pb)','Sigma (pb)','Percentil (%)','Hist. conjunto']].rename(columns={key:'Z-score'})
    st.dataframe(view.style.format({'Spread actual (pb)':'{:+.2f}','Z-score':'{:+.2f}','|Z|':'{:.2f}','Media (pb)':'{:+.2f}','Sigma (pb)':'{:.2f}','Percentil (%)':'{:.1f}'}).background_gradient(subset=['Z-score'],cmap='RdYlGn',vmin=-3,vmax=3),hide_index=True,use_container_width=True,height=420)
    st.download_button('Exportar ranking RV',ranked.to_csv(index=False).encode('utf-8-sig'),file_name='neutrino_scanner_rv.csv',mime='text/csv',key='rv_export')
    picked=st.selectbox('Ver detalle histórico del par',ranked['Par'].tolist(),key='rv_pair')
    pair=ranked.loc[ranked['Par']==picked].iloc[0]
    f1,f2=_pair_traces(piv,pair['Largo'],pair['Corto'],window)
    if f1 is not None:
        st.plotly_chart(f1,use_container_width=True,key='rv_two_rates')
        st.plotly_chart(f2,use_container_width=True,key='rv_spread_bands')

def render_stability(bonos,udis,asof):
    st.header('Monitor de estabilidad estadística')
    st.caption('Z-scores calculados para cada combinación con 30, 60, 120 y 250 observaciones anteriores simultáneas. La observación actual queda fuera de las estadísticas de referencia.')
    fam=st.selectbox('Mercado',['Bonos M','Udibonos'],key='stab_fam')
    ds=bonos if fam=='Bonos M' else udis
    piv=_active_data(ds,asof)
    ranking=_scout(piv)
    if ranking.empty:st.warning('Sin pares con historia suficiente');return
    zcols=['Z30','Z60','Z120','Z250']
    ranking['Ventanas válidas']=ranking[zcols].notna().sum(axis=1)
    ranking['Signo consistente']=ranking[zcols].apply(lambda row: bool((row.dropna()>0).all() or (row.dropna()<0).all()) if len(row.dropna())>=2 else False,axis=1)
    ranking['Dispersión Z']=ranking[zcols].std(axis=1)
    ranking['Promedio |Z|']=ranking[zcols].abs().mean(axis=1)
    ranking['Score consistencia']=ranking['Promedio |Z|']/(1+ranking['Dispersión Z'].fillna(0))
    ranking.loc[~ranking['Signo consistente'],'Score consistencia']*=0.5
    ranking=ranking.sort_values(['Signo consistente','Score consistencia'],ascending=[False,False])
    show=ranking[['Par','Z30','Z60','Z120','Z250','Ventanas válidas','Signo consistente','Dispersión Z','Score consistencia']]
    st.dataframe(show.style.format({k:'{:+.2f}' for k in zcols}|{'Dispersión Z':'{:.2f}','Score consistencia':'{:.2f}'}).background_gradient(subset=zcols,cmap='RdYlGn',vmin=-3,vmax=3),use_container_width=True,hide_index=True,height=480)
    st.caption('Score de consistencia = promedio de |Z| / (1 + dispersión de Z), penalizado si cambia de signo; es un indicador exploratorio, no una probabilidad de reversión.')
    st.download_button('Exportar estabilidad',ranking.to_csv(index=False).encode('utf-8-sig'),file_name='neutrino_estabilidad.csv',mime='text/csv',key='stab_export')
    selected=st.selectbox('Par para comparación por ventana',ranking['Par'].tolist(),key='stab_pair')
    item=ranking.loc[ranking['Par']==selected].iloc[0]
    fig=go.Figure(go.Bar(x=zcols,y=[item[k] for k in zcols],marker_color=[COLORS[0] if item[k]>=0 else '#c75c53' for k in zcols],text=[f'{item[k]:+.2f}' if pd.notna(item[k]) else '' for k in zcols],textposition='outside'))
    fig.add_hline(y=0,line_color='#aab7c6')
    fig.update_yaxes(title='Desviaciones estándar')
    st.plotly_chart(_standard_plot(fig,360),use_container_width=True,key='stab_comparison_chart')

def _pca(piv,asof,obs,coverage,min_tenor):
    import re
    piv=piv.tail(obs+12)
    # Seleccionar emisones con historia suficiente; forward fill limitado 1 día.
    counts=piv.notna().sum()
    cols=counts[counts>=max(25,int(len(piv)*coverage))].index
    if len(cols)<4:return None
    data=piv[list(cols)].ffill(limit=1).dropna()
    if len(data)<max(30,obs//2):return None
    changes=data.diff().dropna()*100  # rendimiento % -> pb
    if len(changes)<25:return None
    return data,changes

def render_pca(bonos,udis,asof):
    st.header('PCA · Factores de curvas')
    st.caption('Análisis de componentes principales de movimientos diarios de rendimiento (pb). Se calcula por mercado, usando emisiones que cotizan en la fecha seleccionada. Factor 1/2/3 son estadísticos, y su signo puede invertirse sin cambiar la interpretación.')
    a,b,c=st.columns(3)
    family=a.selectbox('Mercado',['Bonos M','Udibonos'],key='pca_family')
    window=b.selectbox('Ventana de cambios diarios',[60,120,250,500],index=2,key='pca_window')
    mode=c.selectbox('Escalamiento',['Covarianza (pb)','Correlación (estandarizado)'],key='pca_method')
    ds=bonos if family=='Bonos M' else udis
    pivot=_active_data(ds,asof)
    result=_pca(pivot,asof,window,.85,0)
    if result is None:
        st.warning('No hay suficientes series con cotizaciones comunes para estimar una PCA fiable. Prueba una ventana más corta.');return
    data,returns=result
    # Conservar ventana exacta de cambios después de alinear
    returns=returns.tail(window)
    X=returns.to_numpy(dtype=float)
    center=X.mean(axis=0);sd=X.std(axis=0,ddof=1)
    if mode.startswith('Correlación'):
        good=sd>1e-10
        X=X[:,good];sd=sd[good];center=center[good];labels=list(returns.columns[good]);scale=sd
    else:
        labels=list(returns.columns);scale=np.ones(X.shape[1]);good=np.ones(X.shape[1],dtype=bool)
    if X.shape[1]<4:st.warning('Menos de cuatro emisiones con variación válida.');return
    A=(X-center)/scale
    U,S,Vh=np.linalg.svd(A,full_matrices=False)
    variance=S**2; explained=variance/variance.sum()*100
    n=min(3,len(explained)); comps=Vh[:n].copy();scores=(U[:,:n]*S[:n]);
    # Orientar el primer factor hacia un movimiento positivo paralelo (solo signo de presentación)
    if comps[0].sum()<0: comps[0]*=-1;scores[:,0]*=-1
    st1,st2,st3=st.columns(3)
    for col,k in zip([st1,st2,st3],range(3)):
        col.metric(f'Varianza explicada PC{k+1}',f'{explained[k]:.1f}%' if k<len(explained) else 'n/d')
    st.caption(f'{len(labels)} emisiones · {len(returns)} cambios diarios coincidentes · cobertura ≥85% antes de alinear. Varianza acumulada 3 factores: {explained[:n].sum():.1f}%')
    bar=go.Figure(go.Bar(x=[f'PC{i+1}' for i in range(min(8,len(explained)))],y=explained[:8],marker_color=COLORS[0],text=[f'{v:.1f}%' for v in explained[:8]],textposition='outside'))
    bar.update_yaxes(title='Varianza explicada (%)');st.plotly_chart(_standard_plot(bar,320),use_container_width=True,key='pca_explained')
    dates=[]
    for s in labels:
        mt=re.search(r'(\d{6})',str(s))
        try: date=pd.to_datetime(mt.group(1),format='%y%m%d') if mt else pd.NaT
        except:date=pd.NaT
        dates.append((date-pd.Timestamp(asof)).days/365.25 if pd.notna(date) else np.nan)
    loads=pd.DataFrame({'Serie':labels,'Tenor (años)':dates})
    for i in range(n):loads[f'PC{i+1}']=comps[i]
    loads=loads.sort_values('Tenor (años)')
    fig=go.Figure()
    for i in range(n):fig.add_trace(go.Scatter(x=loads['Tenor (años)'],y=loads[f'PC{i+1}'],mode='lines+markers',name=f'PC{i+1}',text=loads['Serie'],line=dict(color=COLORS[i],width=2),hovertemplate='%{text}<br>Tenor %{x:.2f} años<br>Carga %{y:+.3f}<extra></extra>'))
    fig.update_xaxes(title='Tenor remanente (años)');fig.update_yaxes(title='Carga del factor')
    st.plotly_chart(_standard_plot(fig,440),use_container_width=True,key='pca_loadings')
    scores_fig=go.Figure()
    for i in range(n):scores_fig.add_trace(go.Scatter(x=returns.index,y=scores[:,i],name=f'PC{i+1}',line=dict(color=COLORS[i],width=1.8)))
    scores_fig.update_yaxes(title='Score de factores (unidades del método seleccionado)')
    st.plotly_chart(_standard_plot(scores_fig,430),use_container_width=True,key='pca_scores')
    st.dataframe(loads.style.format({ 'Tenor (años)':'{:.2f}',**{f'PC{i+1}':'{:+.4f}' for i in range(n)}}),hide_index=True,use_container_width=True)
    st.download_button('Exportar cargas PCA',loads.to_csv(index=False).encode('utf-8-sig'),file_name='neutrino_pca_loadings.csv',mime='text/csv',key='pca_export')
    st.caption('El PCA utiliza cambios de rendimiento, no niveles; no sustituye un modelo de valuación ni recomienda por sí mismo una compra o venta. La selección de emisiones y los faltantes condicionan los factores.')

    # Diagnóstico transversal en los mismos cambios de rendimiento usados para ajustar la PCA.
    # Se reconstruye el movimiento diario explicado por PC1-3 y se mide el residual.
    # El Z de cada emisión utiliza SOLO sus residuos de días anteriores como referencia.
    explained_standardized = scores @ comps   # (observaciones x emisiones)
    residual_pb = (A - explained_standardized) * scale
    modeled_pb = explained_standardized * scale + center
    residuals = pd.DataFrame(residual_pb, index=returns.index, columns=labels)
    modeled = pd.DataFrame(modeled_pb, index=returns.index, columns=labels)
    stats_rows = []
    for symbol in labels:
        history = residuals[symbol].dropna()
        if len(history) < 21:
            continue
        previous = history.iloc[:-1]
        sigma = float(previous.std(ddof=1))
        avg = float(previous.mean())
        today = float(history.iloc[-1])
        z = (today - avg) / sigma if np.isfinite(sigma) and sigma > 1e-10 else np.nan
        latest_observed = float(returns.loc[history.index[-1], symbol])
        latest_predicted = float(modeled.loc[history.index[-1], symbol])
        if not np.isfinite(z):
            signal = '⚪ Insuficiente'
            rank = 0
        elif z >= 1.5:
            signal = '🟢 Rendimiento alto'
            rank = 3
        elif z <= -1.5:
            signal = '🔴 Rendimiento bajo'
            rank = 3
        elif abs(z) >= 0.75:
            signal = '🟡 En observación'
            rank = 2
        else:
            signal = '⚪ Normal'
            rank = 1
        tenor = float(loads.set_index('Serie').loc[symbol, 'Tenor (años)'])
        stats_rows.append({
            'Serie': symbol,
            'Tenor (años)':tenor,
            'Cambio observado (pb)': latest_observed,
            'Cambio explicado (pb)': latest_predicted,
            'Residual (pb)': today,
            'Media residual previa (pb)': avg,
            'Sigma residual (pb)': sigma,
            'Z residual': z,
            'Percentil residual (%)': 100.0*float((previous<=today).mean()),
            'Semáforo': signal,
            'Orden señal': rank,
            'Observaciones': len(history),
        })
    st.divider()
    st.subheader('PCA Relative Value · Residuales por emisión')
    st.caption('Diferencia entre el cambio diario de rendimiento observado y el movimiento explicado por los primeros tres componentes. Cada Z-score se contrasta con el historial de residuales de ESA emisión, excluyendo la última observación.')
    if not stats_rows:
        st.warning('No hay suficientes residuales para calcular el Z-score por emisión.')
        return
    rv = pd.DataFrame(stats_rows)
    rv['|Z residual|']=rv['Z residual'].abs()
    rv=rv.sort_values(['|Z residual|','Tenor (años)'],ascending=[False,True]).reset_index(drop=True)
    a1,a2,a3,a4=st.columns(4)
    a1.metric('Emisiones analizadas',len(rv))
    a2.metric('Mayor |Z residual|',f"{rv['|Z residual|'].max():.2f}" if rv['|Z residual|'].notna().any() else 'n/d')
    a3.metric('Rendimientos altos (Z ≥ +1.5)',int((rv['Z residual']>=1.5).sum()))
    a4.metric('Rendimientos bajos (Z ≤ −1.5)',int((rv['Z residual']<=-1.5).sum()))

    st.markdown('**Semáforo interpretativo:** 🟢 rendimiento residual inusualmente alto (posible abaratamiento); 🔴 inusualmente bajo (posible encarecimiento); 🟡 desviación moderada; ⚪ normal. No es una recomendación automática de compra o venta.')
    display_cols=['Semáforo','Serie','Tenor (años)','Cambio observado (pb)','Cambio explicado (pb)','Residual (pb)','Z residual','Percentil residual (%)','Observaciones']
    display=rv[display_cols].copy()
    def color_z(v):
        if pd.isna(v):return ''
        if v>=1.5:return 'background-color: #c7eedb; color: #135b3e; font-weight: bold'
        if v<=-1.5:return 'background-color: #f8d4d7; color: #922b39; font-weight: bold'
        if abs(v)>=.75:return 'background-color: #fff0c3; color: #785700; font-weight: bold'
        return 'background-color: #eef2f6; color: #475569'
    st.dataframe(display.style.format({'Tenor (años)':'{:.2f}', 'Cambio observado (pb)':'{:+.2f}',
            'Cambio explicado (pb)':'{:+.2f}','Residual (pb)':'{:+.2f}',
            'Z residual':'{:+.2f}','Percentil residual (%)':'{:.1f}'}).map(color_z,subset=['Z residual']),
        hide_index=True,use_container_width=True,height=430)
    st.download_button('Exportar diagnóstico PCA RV',rv.drop(columns=['Orden señal']).to_csv(index=False).encode('utf-8-sig'),
        file_name='neutrino_pca_relative_value.csv',mime='text/csv',key='pca_rv_export')

    st.subheader('Interpretación automática')
    positive=rv.loc[rv['Z residual']>=1.5]
    negative=rv.loc[rv['Z residual']<=-1.5]
    pc1_share=float(explained[0]) if len(explained) else np.nan
    pc2_share=float(explained[1]) if len(explained)>1 else np.nan
    if pc1_share>=70:
        st.info(f'PC1 explica {pc1_share:.1f}% de la variación conjunta: los movimientos de nivel dominan esta ventana. PC2 explica {pc2_share:.1f}%.')
    else:
        st.info(f'PC1 explica {pc1_share:.1f}% y PC2 {pc2_share:.1f}%: hay una mayor participación de factores relativos, aunque el significado económico depende de sus cargas.')
    if len(positive):
        r=positive.iloc[0]
        st.success(f"🟢 {r['Serie']}: residual de {r['Residual (pb)']:+.2f} pb, Z {r['Z residual']:+.2f}. Su rendimiento subió más (o cayó menos) de lo que explican los factores: investigar posible abaratamiento relativo.")
    if len(negative):
        r=negative.iloc[0]
        st.warning(f"🔴 {r['Serie']}: residual de {r['Residual (pb)']:+.2f} pb, Z {r['Z residual']:+.2f}. Su rendimiento bajó más (o subió menos) de lo explicado: investigar posible encarecimiento relativo.")
    if positive.empty and negative.empty:
        st.info('No se identifican desviaciones residuales superiores a ±1.5σ en el último día.')

    detail=st.selectbox('Histórico del residual · Seleccionar emisión',rv['Serie'].tolist(),key='pca_rv_selected')
    r=rv.set_index('Serie').loc[detail]
    h=residuals[detail].dropna()
    reference=h.iloc[:-1]
    mu=float(reference.mean());sig=float(reference.std(ddof=1))
    fg=go.Figure()
    if np.isfinite(sig) and sig>0:
        for k,c in ((2,'#e6a545'),(1,'#007f83')):
            fg.add_hrect(y0=mu-k*sig,y1=mu+k*sig,opacity=.10,fillcolor=c,line_width=0,
                annotation_text=f'±{k}σ',annotation_position='top left')
    fg.add_trace(go.Scatter(x=h.index,y=h.values,name='Residual diario',line=dict(color='#355e96',width=2)))
    fg.add_trace(go.Scatter(x=[h.index[-1]],y=[h.iloc[-1]],mode='markers',name='Último residual',marker=dict(size=11,color='#d97706')))
    fg.add_hline(y=mu,line_dash='dash',line_color='#007f83',annotation_text='Media histórica previa')
    fg.update_xaxes(title='Fecha');fg.update_yaxes(title='Residual en cambios de rendimiento (pb)')
    st.plotly_chart(_standard_plot(fg,420),use_container_width=True,key='pca_residual_history')
    hg=go.Figure(go.Histogram(x=reference.values,nbinsx=24,name='Histórico previo',marker_color='#74b7c4',opacity=.8))
    hg.add_vline(x=float(h.iloc[-1]),line_dash='dash',line_color='#bc3e51',annotation_text=f"Actual · Z={r['Z residual']:+.2f}")
    hg.update_xaxes(title='Residual diario (pb)');hg.update_yaxes(title='Frecuencia')
    st.plotly_chart(_standard_plot(hg,330),use_container_width=True,key='pca_residual_distribution')
    st.caption('Limitación: la PCA se ajusta utilizando la ventana completa, incluido el último día. Los Z-scores excluyen el residual del último día de la referencia estadística, pero la base PCA no es completamente fuera de muestra. Es una herramienta diagnóstica, NO un backtest ni un modelo de precio justo. La interpretación puede cambiar con la ventana, método, cobertura o número de factores.')

