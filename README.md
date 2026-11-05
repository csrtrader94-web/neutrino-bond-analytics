# NEUTRINO — PCA RV Semáforo · Reporte institucional

Esta edición conserva la aplicación original y sus extensiones PCA, RV Scanner y estabilidad. **Solo se reemplaza la generación del PDF** en la pestaña `DESCARGA`; el motor `report_engine.py` sigue intacto.

## Reporte nuevo

El PDF institucional (orientación horizontal, fondo blanco, tablas de alto contraste) presenta:

1. Lectura ejecutiva y focos estadísticos del mercado.
2. Curvas nominal y real.
3. Relative Value Scanner de Bonos M y Udibonos, con Z-score por historia individual y ventanas coincidentes.
4. Gráficas y bandas de los pares más extremos.
5. Monitor de estabilidad de Z-scores (30, 60, 120, 250 observaciones).
6. PCA de curvas y semáforo residual por emisión.
7. Cargas de factores PC1 a PC3.
8. Breakeven por Udibono y ranking histórico de cada emisión.
9. Carry, DV01, theta y préstamo teórico del motor preexistente.
10. CETES, tasas equivalentes y notas metodológicas.

En `DESCARGA` puedes seleccionar ventana PCA, escalamiento y ventana del scanner. El reporte usa las bases que estén en esta carpeta al momento de ejecutarse: si agregaste nuevas fechas en tu PC, **sustituye aquí** `BASE M.xlsx`, `base udis.xlsx` y/o `vector.csv` por sus archivos actualizados. El ZIP incluye la fotografía de bases disponible al generar esta entrega (30/10/2026).

## Arranque sin reinstalar librerías

```cmd
cd /d "C:\Users\cerodriguez\Desktop\NEUTRINO_PCA_RV_REPORTE_INSTITUCIONAL_v4"
"C:\Users\cerodriguez\Desktop\NEUTRINO_ORIGINAL_PCA_RV_ESTABILIDAD_v2\.venv\Scripts\python.exe" -m streamlit run app.py
```

Si tu entorno virtual tiene una ruta distinta, utiliza el Python de ese entorno. Instala dependencias solo cuando falte alguna.

## Limitaciones

- La señal PCA se estima en la muestra seleccionada y no está validada fuera de muestra.
- Una observación extrema no equivale a una recomendación operativa.
- Los datos históricos y los precios del vector pueden tener fechas distintas; el PDF las identifica por separado.
- Los cálculos de carry/préstamo teórico permanecen exactamente en el motor original, con sus supuestos y convenciones.
- Verifica permisos de uso y publicación de los datos de Valmer.
