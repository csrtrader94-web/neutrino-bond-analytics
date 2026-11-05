"""NEUTRINO | Reporte institucional. Capa editorial, sin alterar el motor de calculos."""
from __future__ import annotations
import io
import math
import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether,HRFlowable
import report_engine as eng
from quant_modules import _active_data,_scout,_pca

NAVY='#17344D'; TEAL='#0D8382'; CYAN='#D7F1EE'; PALE='#F4F8FB'; GRAY='#627589'; RED='#B53E50'; AMBER='#A96E11'; GREEN='#187858'; INK='#23384D'
PAGE=landscape(A4); WIDTH=PAGE[0]-3.1*cm

def p(x):return colors.HexColor(x)
def fmt(x,d=2,signed=False):
    try:
        if not np.isfinite(float(x)):return 'n/d'
        return f'{float(x):+,.{d}f}' if signed else f'{float(x):,.{d}f}'
    except:return 'n/d'
def safe(s):return escape(str(s))

def build_styles():
    st=getSampleStyleSheet()
    st.add(ParagraphStyle(name='HeroN',fontName='Helvetica-Bold',fontSize=24,leading=29,textColor=p(NAVY),spaceAfter=8))
    st.add(ParagraphStyle(name='DeckN',fontName='Helvetica',fontSize=10.4,leading=15,textColor=p(GRAY),spaceAfter=10))
    st.add(ParagraphStyle(name='H1N',fontName='Helvetica-Bold',fontSize=14,leading=18,textColor=p(NAVY),spaceBefore=5,spaceAfter=8))
    st.add(ParagraphStyle(name='H2N',fontName='Helvetica-Bold',fontSize=10.3,leading=13,textColor=p(TEAL),spaceBefore=8,spaceAfter=5))
    st.add(ParagraphStyle(name='BodyN',fontName='Helvetica',fontSize=9.0,leading=13.2,textColor=p(INK),spaceAfter=7))
    st.add(ParagraphStyle(name='SmallN',fontName='Helvetica',fontSize=7.5,leading=10.3,textColor=p(GRAY),spaceAfter=5))
    st.add(ParagraphStyle(name='THN',fontName='Helvetica-Bold',fontSize=7.2,leading=9.4,textColor=colors.white))
    st.add(ParagraphStyle(name='TDN',fontName='Helvetica',fontSize=7.2,leading=9.3,textColor=p(INK)))
    st.add(ParagraphStyle(name='KLabN',fontName='Helvetica',fontSize=8.1,leading=10,textColor=p(GRAY)))
    st.add(ParagraphStyle(name='KValN',fontName='Helvetica-Bold',fontSize=16,leading=19,textColor=p(NAVY)))
    return st

def tbl(df, cols=None, rename=None, maxrows=12, widths=None, styles=None, highlights=None):
    styles=styles or build_styles()
    if df is None or df.empty:return Paragraph('Sin observaciones suficientes para mostrar esta tabla.',styles['SmallN'])
    dt=df.copy(); cols=cols or list(dt.columns); rename=rename or {}; dt=dt[cols].head(maxrows)
    content=[[Paragraph(safe(rename.get(c,c)),styles['THN']) for c in cols]]
    for _,r in dt.iterrows():
        row=[]
        for c in cols:
            v=r[c]
            if isinstance(v,(float,np.floating)): t=fmt(v,2,False)
            elif isinstance(v,pd.Timestamp):t=v.strftime('%d/%m/%Y')
            else:t=str(v)
            row.append(Paragraph(safe(t),styles['TDN']))
        content.append(row)
    widths=widths or [WIDTH/len(cols)]*len(cols)
    t=Table(content,colWidths=widths,repeatRows=1,hAlign='LEFT')
    instructions=[('BACKGROUND',(0,0),(-1,0),p(NAVY)),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,0),8),('BOTTOMPADDING',(0,0),(-1,0),8),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,-1),(-1,-1),.5,p('#DDE7EE'))]
    for i in range(1,len(content)):
        if i%2==0:instructions.append(('BACKGROUND',(0,i),(-1,i),p(PALE)))
        instructions.append(('BOTTOMPADDING',(0,i),(-1,i),6));instructions.append(('TOPPADDING',(0,i),(-1,i),6))
    if highlights:
        for i,row in enumerate(dt.itertuples(index=False,name=None),start=1):
            for col,name in enumerate(cols):
                if name in highlights:
                    try:
                        z=float(row[col]); bg=('#DBF2E5' if z>=1.5 else '#FBE2E4' if z<=-1.5 else '#FFF1CB' if abs(z)>=.75 else None)
                        if bg: instructions.append(('BACKGROUND',(col,i),(col,i),p(bg)))
                    except:pass
    t.setStyle(TableStyle(instructions))
    return t

def kpi_line(pairs,st):
    n=len(pairs)
    widths=[WIDTH/n]*n
    cells=[]
    for label,val in pairs:
        cells.append([Paragraph(safe(label),st['KLabN']),Paragraph(safe(val),st['KValN'])])
    t=Table([cells],colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),p(PALE)),('BOX',(0,0),(-1,-1),.6,p('#E0E9F0')),('INNERGRID',(0,0),(-1,-1),.5,p('#E0E9F0')),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    return t

def figure_plot(data,kind='curve',date=None,comparison=None):
    fig,ax=plt.subplots(figsize=(10.8,2.9),dpi=150)
    fig.patch.set_facecolor('#ffffff');ax.set_facecolor('#ffffff')
    ax.spines[['top','right']].set_visible(False)
    ax.grid(alpha=.20,color='#9cb3c4');ax.tick_params(colors=GRAY,labelsize=8)
    if kind=='curve':
        df=data.dropna(subset=['ACTUAL','TENOR']).sort_values('TENOR');ax.plot(df['TENOR'],df['ACTUAL'],'o-',color=TEAL,lw=2,label='Actual',ms=4)
        if df['HACE_30D'].notna().any():
            past=df.dropna(subset=['HACE_30D']);ax.plot(past['TENOR'],past['HACE_30D'],'--',color=AMBER,lw=1.8,label='Comparación')
        ax.set(xlabel='Años al vencimiento',ylabel='Rendimiento (%)');ax.legend(loc='best',frameon=False,fontsize=8)
    elif kind=='be':
        d=data.sort_values('TENOR');ax.plot(d['TENOR'],d['BREAKEVEN'],'o-',color=TEAL,lw=2,ms=4)
        for _,r in d.iterrows():ax.annotate(str(r['UDI']), (r['TENOR'],r['BREAKEVEN']),xytext=(1,5),textcoords='offset points',fontsize=6.2,color=GRAY,rotation=35)
        ax.set(xlabel='Años remanentes del Udibono',ylabel='Breakeven (%)')
    elif kind=='pca':
        for i,(label,vals) in enumerate(data.items()):ax.plot(vals[0],vals[1],marker='o',ms=3,lw=1.7,label=label,color=[TEAL,'#D6A04D','#42658F'][i])
        ax.axhline(0,lw=.8,color='#C2CFDA');ax.set(xlabel='Tenor (años)',ylabel='Carga PCA');ax.legend(fontsize=8,frameon=False)
    elif kind=='spread':
        hist=data;ax.plot(hist.index,hist.values*100,color=TEAL,lw=1.7,label='Spread observado')
        prior=hist.iloc[:-1];mu=prior.mean()*100;sd=prior.std()*100
        if np.isfinite(sd) and sd>0:
            ax.axhspan(mu-2*sd,mu+2*sd,color='#E9C993',alpha=.15,label='±2 desviaciones')
            ax.axhspan(mu-sd,mu+sd,color=TEAL,alpha=.12,label='±1 desviación')
        ax.axhline(mu,color=AMBER,ls='--',lw=1.3,label='Media previa')
        ax.set(xlabel='Fecha',ylabel='Spread (pb)');ax.tick_params(axis='x',rotation=20);ax.legend(frameon=False,fontsize=7)
    fig.tight_layout(pad=1.35)
    bio=io.BytesIO();fig.savefig(bio,format='png',bbox_inches='tight',dpi=145);plt.close(fig);bio.seek(0)
    return Image(bio,width=WIDTH,height=WIDTH*2.9/10.8)

def paragraph(text,sty):return Paragraph(text,sty)
def sec(story,title,st):story.append(Paragraph(safe(title),st['H1N']));story.append(HRFlowable(width='100%',thickness=.7,color=p('#D7E6EC'),spaceAfter=10))
def note(story,text,st):story.append(Paragraph(safe(text),st['SmallN']))
def page(story):story.append(PageBreak())

def get_pca(ds,asof,window=120,mode='Covarianza (pb)'):
    piv=_active_data(ds,asof)
    res=_pca(piv,asof,window,.85,0)
    if res is None:return None
    _,ret=res;ret=ret.tail(window)
    X=ret.to_numpy(float);center=X.mean(axis=0);std=X.std(axis=0,ddof=1)
    if mode.startswith('Correlación'):
        good=std>1e-10;X=X[:,good];center=center[good];std=std[good];scale=std;labels=list(ret.columns[good]);ret=ret[labels]
    else:scale=np.ones(X.shape[1]);labels=list(ret.columns)
    if len(labels)<4:return None
    A=(X-center)/scale
    U,S,Vh=np.linalg.svd(A,full_matrices=False)
    exp=(S**2)/(S**2).sum()*100
    n=min(3,len(S));comps=Vh[:n].copy();scores=U[:,:n]*S[:n]
    if comps[0].sum()<0:comps[0]*=-1;scores[:,0]*=-1
    fit=scores@comps
    resid=pd.DataFrame((A-fit)*scale,index=ret.index,columns=labels)
    modeled=pd.DataFrame(fit*scale+center,index=ret.index,columns=labels)
    rows=[];loadings={f'PC{i+1}':([],[]) for i in range(n)}
    for j,sym in enumerate(labels):
        mt=re.search(r'(\d{6})',sym)
        try:ten=(pd.to_datetime(mt.group(1),format='%y%m%d')-asof).days/365.25
        except:ten=np.nan
        for i in range(n):loadings[f'PC{i+1}'][0].append(ten);loadings[f'PC{i+1}'][1].append(comps[i,j])
        h=resid[sym].dropna();old=h.iloc[:-1]
        if len(old)<20:continue
        sig=old.std(ddof=1)
        z=(h.iloc[-1]-old.mean())/sig if sig>1e-10 else np.nan
        rows.append({'Serie':sym,'Tenor (años)':ten,'Obs. (pb)':ret[sym].iloc[-1], 'Modelo (pb)':modeled[sym].iloc[-1], 'Residual (pb)':h.iloc[-1], 'Z residual':z,'Percentil (%)':100*(old<=h.iloc[-1]).mean()})
    frame=pd.DataFrame(rows)
    if not frame.empty:frame=frame.assign(AZ=lambda x:x['Z residual'].abs()).sort_values('AZ',ascending=False)
    return {'exp':exp,'loads':loadings,'rv':frame,'n':len(labels),'dates':len(ret),'mode':mode}

def get_stability(scout):
    if scout.empty:return pd.DataFrame()
    d=scout.copy();zcols=['Z30','Z60','Z120','Z250']
    d['Validas']=d[zcols].notna().sum(axis=1)
    d['Consistente']=d[zcols].apply(lambda v: bool((v.dropna()>0).all() or (v.dropna()<0).all()) if v.notna().sum()>=2 else False,axis=1)
    d['Dispersión']=d[zcols].std(axis=1)
    d['Score']=d[zcols].abs().mean(axis=1)/(1+d['Dispersión'].fillna(0))
    d.loc[~d['Consistente'],'Score']*=.5
    return d.sort_values(['Consistente','Score'],ascending=[False,False])

def onpage(canvas,doc):
    canvas.saveState();w,h=PAGE
    canvas.setFillColor(p(NAVY));canvas.rect(0,h-1.03*cm,w,1.03*cm,fill=1,stroke=0)
    canvas.setFont('Helvetica-Bold',9);canvas.setFillColor(colors.white);canvas.drawString(1.55*cm,h-.68*cm,'NEUTRINO  /  FIXED INCOME RESEARCH')
    canvas.setFillColor(p(TEAL));canvas.rect(1.55*cm,.82*cm,w-3.1*cm,.027*cm,fill=1,stroke=0)
    canvas.setFillColor(p(GRAY));canvas.setFont('Helvetica',7);canvas.drawString(1.55*cm,.5*cm,'Uso interno | Análisis estadístico, no cotización ni recomendación de inversión')
    canvas.drawRightString(w-1.55*cm,.5*cm,f'{doc.page}')
    canvas.restoreState()

def build_report(bonos,udis,vector_path,out_path,asof,matrix_days=60,curve_days=30,top_n=5,funding=6.50,amount=100_000_000,pca_window=120,pca_mode='Covarianza (pb)',rv_window=120):
    st=build_styles();asof=pd.Timestamp(asof);out_path=Path(out_path);out_path.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(out_path),pagesize=PAGE,leftMargin=1.55*cm,rightMargin=1.55*cm,topMargin=1.48*cm,bottomMargin=1.22*cm,title='NEUTRINO | Informe institucional de renta fija',author='NEUTRINO Fixed Income')
    story=[]
    pivm=_active_data(bonos,asof);pivu=_active_data(udis,asof)
    mdate=pd.Timestamp(pivm.index.max());udate=pd.Timestamp(pivu.index.max())
    scout_m=_scout(pivm);scout_u=_scout(pivu)
    pcam=get_pca(bonos,asof,pca_window,pca_mode);pcau=get_pca(udis,asof,pca_window,pca_mode)
    be,be_date=eng.compute_breakeven_snapshot(bonos,udis,asof)
    curve_m,_,_=eng.compute_curve_table(bonos,asof,asof-pd.Timedelta(days=curve_days))
    curve_u,_,_=eng.compute_curve_table(udis,asof,asof-pd.Timedelta(days=curve_days))
    try:carry_m=eng.load_carry_table(str(vector_path),funding,amount)
    except Exception:carry_m=pd.DataFrame()
    try:carry_u=eng.load_udibono_carry_table(str(vector_path),funding,amount)
    except Exception:carry_u=pd.DataFrame()
    try:cetes=eng.load_general_cetes_bi_table(str(vector_path),funding,amount)
    except Exception:cetes=pd.DataFrame()
    try:eq=eng.load_bonos_equivalent_rate_table(str(vector_path))
    except Exception:eq=pd.DataFrame()
    try:source=pd.read_csv(vector_path,encoding='latin1',usecols=['Fecha']);vect_date=str(source['Fecha'].iloc[0])
    except: vect_date='Consultar vector'

    # Page 1 - Executive
    story.append(Spacer(1,.3*cm));story.append(Paragraph('Reporte de mercado y valor relativo',st['HeroN']))
    story.append(Paragraph(f'Bonos M  ·  Udibonos  ·  CETES  |  Corte seleccionado: {asof:%d/%m/%Y}',st['DeckN']))
    story.append(kpi_line([('Bonos M activos',str(len(pivm.columns))),('Udibonos activos',str(len(pivu.columns))),('Pares RV M',str(len(scout_m))),('Pares RV UDI',str(len(scout_u)))],st));story.append(Spacer(1,.4*cm))
    sec(story,'Lectura ejecutiva',st)
    explanations=[]
    for fam,df in [('Bonos M',scout_m),('Udibonos',scout_u)]:
        if not df.empty:
            d=df.dropna(subset=['Z120']).copy()
            if not d.empty:
                row=d.loc[d['Z120'].abs().idxmax()]
                explanations.append(f'<b>{fam}:</b> el par {safe(row["Par"])} presenta Z120 de <b>{fmt(row["Z120"],2,True)}</b> y spread de {fmt(row["Spread actual (pb)"])} pb frente a su propia historia coincidente.')
    for fam,pc in [('M',pcam),('UDI',pcau)]:
        if pc is not None and not pc['rv'].empty:
            r=pc['rv'].iloc[0]
            explanations.append(f'<b>PCA {fam}:</b> la emisión {safe(r["Serie"])} muestra Z residual {fmt(r["Z residual"],2,True)} ({"movimiento de rendimiento por arriba" if r["Z residual"]>0 else "por debajo"} de lo explicado por factores).')
    for line in explanations[:4]:story.append(Paragraph(line,st['BodyN']))
    story.append(Spacer(1,.25*cm));story.append(Paragraph('<b>Cómo usar el reporte:</b> el Z-score indica una desviación estadística, no una operación ejecutable. Confirmar liquidez, carry, DV01, fechas coincidentes y consistencia entre ventanas.',st['BodyN']))
    note(story,f'Fecha efectiva Bonos M: {mdate:%d/%m/%Y}. Udibonos: {udate:%d/%m/%Y}. Vector (datos de precios): {vect_date}. Los resultados del vector solo son comparables con curvas históricas si las fechas coinciden.',st)
    page(story)

    # Page 2 - M curves
    sec(story,'01  |  Curvas nominal y real',st)
    story.append(Paragraph('Comparación de rendimientos por tenor remanente. Las curvas históricas se obtienen de cada emisión a sus días remanentes de cada fecha, no de un plazo fijo sintético.',st['BodyN']))
    story.append(Paragraph('Bonos M',st['H2N']));story.append(figure_plot(curve_m))
    story.append(KeepTogether([Paragraph('Udibonos | Curva real',st['H2N']),figure_plot(curve_u)]))
    page(story)

    # Page 3 - RV scanner
    sec(story,'02  |  Relative Value Scanner',st)
    story.append(Paragraph(f'Spread = rendimiento largo - corto. Z-scores sobre ventanas de observaciones coincidentes, con la última observación excluida de la media y desviación de referencia. Se ordena por valor absoluto de Z{rv_window}.',st['BodyN']))
    for fam,sco in [('Bonos M',scout_m),('Udibonos',scout_u)]:
        story.append(Paragraph(fam,st['H2N']))
        if not sco.empty:
            rank=sco.dropna(subset=[f'Z{rv_window}']).copy()
            if not rank.empty:
                rank=rank.assign(absz=rank[f'Z{rv_window}'].abs()).sort_values('absz',ascending=False)
                view=rank[['Par','Spread actual (pb)',f'Z{rv_window}','Hist. conjunto']].rename(columns={'Spread actual (pb)':'Spread (pb)',f'Z{rv_window}':'Z histórico','Hist. conjunto':'N'})
                story.append(tbl(view,maxrows=6,styles=st,widths=[10.2*cm,4.7*cm,4.4*cm,2.9*cm],highlights=['Z histórico']))
        story.append(Spacer(1,.18*cm))
    note(story,'Lectura: Z positivo = spread más amplio que lo habitual; Z negativo = spread más estrecho. La matriz visual original de la app conserva su propia metodología; aquí se utiliza la del Scanner RV excluyendo el último dato.',st)
    page(story)

    # Page 4 selected spreads
    sec(story,'03  |  Detalle de los pares más extremos',st)
    for fam,piv,sco in [('Bonos M',pivm,scout_m),('Udibonos',pivu,scout_u)]:
        if sco.empty:continue
        d=sco.dropna(subset=[f'Z{rv_window}']).copy()
        if d.empty:continue
        d=d.assign(absz=d[f'Z{rv_window}'].abs()).sort_values('absz',ascending=False)
        row=d.iloc[0];hist=(piv[row['Largo']]-piv[row['Corto']]).dropna().tail(rv_window+1)
        story.append(Paragraph(f'{fam} | {safe(row["Par"])} | Z={fmt(row[f"Z{rv_window}"],2,True)}',st['H2N']))
        story.append(figure_plot(hist,'spread'))
    page(story)

    # Page 5 stability
    sec(story,'04  |  Monitor de estabilidad de las señales',st)
    story.append(Paragraph('Una señal es más consistente cuando mantiene signo y magnitud en varias ventanas. Los scores son heurísticos y no representan probabilidad de convergencia.',st['BodyN']))
    for fam,sco in [('Bonos M',scout_m),('Udibonos',scout_u)]:
        stab=get_stability(sco);story.append(Paragraph(fam,st['H2N']))
        if not stab.empty:
            d=stab[['Par','Z30','Z60','Z120','Z250','Consistente','Score']].copy()
            d['Consistente']=d['Consistente'].map({True:'Sí',False:'No'});story.append(tbl(d,maxrows=7,styles=st,widths=[7.0*cm,2.7*cm,2.7*cm,2.7*cm,2.7*cm,2.8*cm,3.6*cm]))
        story.append(Spacer(1,.18*cm))
    page(story)

    # Page 6 PCA
    sec(story,'05  |  PCA de curvas y semáforo de residuales',st)
    story.append(Paragraph(f'Escalamiento: {safe(pca_mode)} | Ventana: {pca_window} cambios diarios. El residual compara el cambio observado con el explicado por PC1 a PC3. Z del residual frente al histórico propio de cada emisión, excluyendo la última observación.',st['BodyN']))
    for fam,pc in [('Bonos M',pcam),('Udibonos',pcau)]:
        story.append(Paragraph(fam,st['H2N']))
        if pc is None:note(story,'Datos insuficientes para el PCA de esta familia.',st);continue
        story.append(Paragraph(f'Varianza explicada: PC1 {fmt(pc["exp"][0],1)}%  |  PC2 {fmt(pc["exp"][1],1)}%  |  PC3 {fmt(pc["exp"][2],1)}%. Emisiones: {pc["n"]}; cambios alineados: {pc["dates"]}.',st['BodyN']))
        view=pc['rv'][['Serie','Obs. (pb)','Modelo (pb)','Residual (pb)','Z residual','Percentil (%)']].copy()
        story.append(tbl(view,maxrows=7,styles=st,widths=[3.7*cm,3.3*cm,3.5*cm,3.9*cm,3.4*cm,4.4*cm],highlights=['Z residual']))
    page(story)

    # Page 7 loadings and BE
    sec(story,'06  |  Factores PCA e inflación breakeven',st)
    if pcam is not None:
        story.append(Paragraph('Cargas de PC1–PC3, Bonos M',st['H2N']));story.append(figure_plot(pcam['loads'],'pca'))
    if not be.empty:
        story.append(Paragraph('Breakeven calculado para cada Udibono',st['H2N']))
        story.append(Paragraph('La tasa nominal se interpola al vencimiento remanente específico de cada emisión UDI; el breakeven es una aproximación por rendimientos y no elimina todas las primas de riesgo.',st['SmallN']))
        columns=['UDI','TENOR','NOMINAL_INTERP','REAL','BREAKEVEN']
        story.append(tbl(be,cols=columns,rename={'UDI':'Udibono','TENOR':'Años','NOMINAL_INTERP':'Nominal %','REAL':'Real %','BREAKEVEN':'BE %'},maxrows=8,styles=st,widths=[4.6*cm,4.0*cm,4.5*cm,4.5*cm,4.6*cm]))
    page(story)

    # Page 8 BE history
    sec(story,'07  |  Breakeven por emisión: desviación histórica',st)
    rows=[]
    if not be.empty:
        for _,r in be.iterrows():
            hist=eng.breakeven_history(bonos,udis,str(r['UDI']),asof-pd.Timedelta(days=max(250,matrix_days*2)),asof)
            if len(hist)<21:continue
            curr=float(hist['BREAKEVEN'].iloc[-1]);prev=hist['BREAKEVEN'].iloc[:-1];sd=prev.std(ddof=1)
            z=(curr-prev.mean())/sd if sd>1e-10 else np.nan
            rows.append({'Udibono':str(r['UDI']),'Tenor (años)':r['TENOR'],'BE actual (%)':curr,'Media previa (%)':prev.mean(),'Z histórico':z,'Percentil (%)':100*(prev<=curr).mean(),'Obs.':len(hist)})
    be_rank=pd.DataFrame(rows)
    if not be_rank.empty:
        be_rank=be_rank.assign(az=lambda x:x['Z histórico'].abs()).sort_values('az',ascending=False)
        story.append(tbl(be_rank,cols=['Udibono','Tenor (años)','BE actual (%)','Media previa (%)','Z histórico','Percentil (%)','Obs.'],maxrows=12,styles=st,widths=[3.4*cm,3.1*cm,3.3*cm,3.5*cm,3.2*cm,3.1*cm,2.6*cm],highlights=['Z histórico']))
        top=be_rank.iloc[0]
        story.append(Spacer(1,.35*cm));story.append(Paragraph(f'Lectura destacada: el Udibono {safe(top["Udibono"])} presenta breakeven de {fmt(top["BE actual (%)"],3)}% y Z histórico {fmt(top["Z histórico"],2,True)}. Un breakeven inusualmente bajo puede indicar una menor compensación implícita por inflación, pero debe contrastarse contra inflación esperada, liquidez y prima de riesgo.',st['BodyN']))
    page(story)

    # Page 9 carry/cetes
    sec(story,'08  |  Carry, riesgo, fondeo y préstamos teóricos',st)
    story.append(Paragraph(f'Supuestos seleccionados en NEUTRINO: monto de referencia ${amount:,.0f} y fondeo {funding:.2f}% anual. Estas métricas provienen del motor existente; no sustituyen precios de ejecución. El vector tiene su propia fecha de referencia.',st['BodyN']))
    if not carry_m.empty:
        story.append(Paragraph('Bonos M — métricas del motor original',st['H2N']))
        cols=[c for c in ['Serie','Rend (%)','DV01','Theta','Carry','Dias recup 1pb','Préstamo Teórico','Tasa 1 Día (%)'] if c in carry_m]
        story.append(tbl(carry_m,cols=cols,maxrows=10,styles=st,widths=[WIDTH/len(cols)]*len(cols)))
    if not carry_u.empty:
        story.append(Paragraph('Udibonos — métricas del motor original',st['H2N']))
        cols=[c for c in ['Serie','Rendimiento','DV01','THETA','Carry Neto','Prestamo Teorico','T.1Dia (%)'] if c in carry_u]
        story.append(tbl(carry_u,cols=cols,maxrows=5,styles=st,widths=[WIDTH/len(cols)]*len(cols)))
    page(story)

    # Page 10 CETES
    sec(story,'09  |  CETES, equivalencias y curva cupón cero',st)
    story.append(Paragraph('Monitoreo de CETES: rendimiento, tasa de un día, DV0 y carry neto de fondeo. Se conserva la metodología del módulo original.',st['BodyN']))
    if not cetes.empty:
        cols=[c for c in ['Serie','DiasPorVencer','Rendimiento','1 DIA','DV0','CARRY','DIAS_RECUP_DV0','PRECIO'] if c in cetes]
        story.append(tbl(cetes,cols=cols,maxrows=20,styles=st,widths=[WIDTH/len(cols)]*len(cols)))
    if not eq.empty:
        story.append(Spacer(1,.25*cm));story.append(Paragraph('Bonos M: tasas equivalentes 1, 28 y 90 días',st['H2N']))
        cols=list(eq.columns)[:7];story.append(tbl(eq,cols=cols,maxrows=5,styles=st,widths=[WIDTH/len(cols)]*len(cols)))
    page(story)

    sec(story,'10  |  Metodología, uso y limitaciones',st)
    topics=[
        ('RV', 'La diferencia se define como rendimiento del vencimiento largo menos el corto. El Z del Scanner se calcula sobre cada par y excluye la observación actual de la estadística de referencia.'),
        ('PCA', 'Los componentes son factores estadísticos de cambios diarios, no valores razonables de rendimiento. La varianza explicada, las cargas y el residual dependen de la selección de emisiones, observaciones y escalamiento. Los scores no constituyen una predicción.'),
        ('Semáforo', 'Verde: Z residual >= 1.5; rojo <= -1.5; amarillo: |Z| >= 0.75; neutro en otros casos. Un movimiento residual no implica necesariamente un abaratamiento persistente del nivel del bono.'),
        ('Breakeven', 'Se estima por el cociente entre rendimiento nominal interpolado al vencimiento del Udibono y su rendimiento real. Las estadísticas son por emisión, pero pueden incluir efecto roll-down y cambios de tenor.'),
        ('Carry y riesgos', 'Las cifras dependen del vector cargado, del monto de referencia y de la tasa de fondeo. El motor existente calcula sus propias métricas de préstamo teórico y sensibilidad; son indicativas.'),
        ('Fechas', 'Las series históricas y el vector pueden estar fechados de manera distinta. El reporte deja explícita la fecha efectiva de cada fuente. No deben tratarse como valuación simultánea si difieren.'),
        ('Datos', 'Este reporte puede incorporar datos sujetos a licencia de Valmer. No publicarlo ni distribuirlo sin verificar los permisos aplicables.'),
    ]
    for title,body in topics:story.append(Paragraph(f'<b>{title}.</b> {safe(body)}',st['BodyN']))
    story.append(Spacer(1,.4*cm));story.append(Paragraph('NEUTRINO / Informe institucional | Elaborado automáticamente a partir de las bases y parámetros seleccionados en la aplicación.',st['SmallN']))
    doc.build(story,onFirstPage=onpage,onLaterPages=onpage)
    return out_path
