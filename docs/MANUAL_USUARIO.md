# Manual de usuario — PyPSA-col (toma de decisión tipo UPME)

Esta aplicación **no es XM en vivo para planear**. Es el **Motor B** de una plataforma tipo *UPME Abierta*: **expansión y operación del sistema eléctrico** con PyPSA + HiGHS. No es LEAP, ni SDDP, ni el PET AC, ni el PIEC.

**Dónde estamos (oct 2026).** Chile documentó PyPSA-CL como modelo de *expansión eléctrica* (PELP 2028–2032), no como reemplazo conjunto de LEAP y PLEXOS. Esta app sigue esa lección: un núcleo eléctrico abierto, escenarios trazables, y módulos futuros (demanda de usos finales, hidrología estocástica, confiabilidad) **aparte**. Por ahora el producto es expansión/despacho ilustrativo del SIN.

Esta aplicación **no es XM en vivo para planear** el despacho real. El solver **HiGHS sí corre** en la pestaña GUI.

---

## 1. Mapa mental (léalo antes de pulsar Run)

```
ESCENARIO  = un futuro plausible (C2 BAU, U3 UPME favorable, Niño, …)
             └── contiene una o VARIAS ÉPOCAS (tramos del horizonte)
                   2026–2030  →  2031–2035  →  2036–2040
COLA       = varios escenarios que quiere comparar en la misma corrida
RUN        = HiGHS despacha cada época de cada escenario
RESULTADO  = tabla comparativa + mapas de Colombia por escenario/época
```

| Palabra | Qué es | Analogía UPME |
| --- | --- | --- |
| **Escenario** | Un *mundo*: demanda alta/media/baja, Niño/Niña, precio de combustible, cierre de carbón. | PEN: “caso medio”, “caso crítico hidrológico”. |
| **Época** | Un *tramo de tiempo* dentro de ese mundo (años de inicio–fin). Un escenario **puede tener varias épocas**. | “Corto plazo 2026-2030” vs “mediano 2031-2035” **con el mismo relato**. |
| **Red** | Sobre qué topología se despacha: El Modelo STN, 18 subáreas, 7 nodos o OSM. | Nivel de representación, no un escenario. |
| **Último mes XM** | Pestañas Generación / Demanda: **hecho observado**, ventana D-1 de 30 días. | Diagnóstico coyuntural, **no** el plan. |
| **Inversiones** | Capas que usted pone en **zonas concretas** del SIN y se comparan contra el caso base. | Análisis de alternativas de expansión. |

**Flujo recomendado (decisor):**

1. Elija la **red** (para un comité UPME: empiece por **18 subáreas**; el STN es para ver congestión nodal).
2. Elija el **escenario global** (C1…U3). Eso **bloquea** demanda, hidrología y clima.
3. Añada **una o más épocas** (Add Epoch) = tramos del horizonte de ese escenario.
4. **Cierre el escenario** (Add scenario to queue). Si quiere otro mundo (p. ej. Niño vs Niña), cambie el paquete, añada épocas, y vuelva a encolar.
5. **Run all scenarios**. En la subpestaña **Resumen de escenarios** compare costos, energía no servida y **mapas**.
6. En **Inversiones**, pruebe eólica en Guajira, solar en Cesar, BESS en Bogotá, un enlace Costa–Interior, etc.

---

## 2. Pestañas de la app

| Pestaña | Para qué | No es |
| --- | --- | --- |
| **GUI (PyPSA-COL)** | Armar escenarios/épocas y correr HiGHS. Subpestañas: configuración, resumen, demanda (año + lun–dom), generación. Los mapas viven en el resumen. | XM del mes pasado. |
| **Motor A** | Demanda energética y emisiones (LEAP PEN 2022–2052 + BECO). | El despacho eléctrico (eso es Motor B / GUI). |
| **Inversiones** | Poner MW en **cualquier subárea** (eólica, solar, gas, BESS, refuerzo de red, cierre de carbón zonal) y ver si **mejora la operación**. | Un PGE oficial. Capex es orden de magnitud. |
| **Generación (último mes)** | Mix y CEN **XM**, último mes cerrado D-1. | El despacho de sus épocas. |
| **Demanda (último mes)** | DemaReal XM, mismo mes cerrado. | El escenario de demanda C1/C2. |
| **Explorador de planta** | Una planta XM de esa ventana. | |
| **Red SIN** | Tres modelos + Grid2Poster OSM. | Unifilar PARATEC. |
| **Resultados HiGHS** | CSV de la última corrida. | |
| **Manual** | Este texto. | |

---

## 3. Escenario con varias épocas — ejemplo

Quiere el **caso UPME medio (U2)** en dos tramos:

1. Global scenario = `U2 - UPME medio`.
2. Epoch name = `Corto plazo`, Start 2026, Representative years = 5 → Add Epoch.
3. Epoch name = `Mediano plazo`, (la fecha de inicio sigue sola) → Add Epoch.
4. Add scenario to queue. En la cola verá **1 escenario, 2 épocas**.
5. Opcional: cambie a `C1 - Conservador (Niño)`, añada épocas, encole. Ahora hay **2 escenarios**.
6. Run all scenarios. El resumen muestra **una fila por época**, agrupada por escenario, y **un mapa por época**.

Si no encola y solo tiene épocas sueltas, Run las trata como un escenario “en edición”.

---

## 4. Cómo leer los mapas

Fondo: **Grid2Poster** (geometría OSM de Colombia) cuando está disponible; si no, el contorno del país.

| Capa | Significado para el decisor |
| --- | --- |
| **Demanda** | Tamaño naranja = MW medios de carga en el nodo/subárea. Dónde duele el crecimiento. |
| **Generación** | Tamaño verde = MW medios despachados. Dónde se produce vs. dónde se consume. |
| **Precios nodales (LMP)** | Color = escasez relativa. Un LMP alto en Bogotá con LMP bajo en Guajira = **falta de transporte**, no falta de MW nacionales. |
| **Flujos** | Grosor/color del enlace = carga del corredor (N-1 en 18 subáreas). Rojo ≈ congestión. |

Estos LMP y flujos son del **modelo** (año representativo × palancas), no del despacho real de XM. Hay **un atlas por escenario/época**.

---

## 5. Inversiones (lógica de alternativas UPME)

Pregunta típica: *“Si pongo 500 MW eólicos en Guajira y 800 MW de evacuación hacia Cesar, ¿baja la energía no servida y el costo operativo del caso Niño?”*

1. Deje en la GUI el escenario (p. ej. C1 Niño) que quiere como **fondo**.
2. En Inversiones, **añada filas**: tipo + zona + MW (+ zona destino si es refuerzo de red).
3. Compare. Métricas:
   - **Costo operativo** (debería bajar si la alternativa es buena).
   - **Energía no servida** (shedding): la más importante para seguridad.
   - **FNCE (GWh y %)** : cumplimiento de política FNCER.
   - Mix carbón/gas/hidro.

Puede mezclar: solar en Cesar **y** Santander, BESS en Bogotá, refuerzo Caribe–Interior. El capex se suma de forma ilustrativa (USD 2024 de orden de magnitud).

La pestaña **explica** el resultado: si baja el costo operativo, si cae la ENS, cuánto FNCE gana, si se desplaza carbón/gas, y un payback ilustrativo (capex / ahorro de la ventana). Eso **no** es un GEP: el LP no tiene variable de inversión.

---

## 5b. Año representativo y crecimiento de demanda

El `network.nc` trae **un día típico (24 h)**. PyPSA-col lo **expande** a meses × tipos de día (1 día típico o laboral/sábado/domingo/máxima) y pone `snapshot_weightings` para que \(\sum P\cdot w\) sea energía anual. En la GUI use *Representative months* (1/2/4/6/12) y *days* (1 o 4).

**Entre épocas la demanda crece** con el escenario: C1 ~2 %/año, C2 ~2,8 %, C3 ~3,8 % (U1–U3 análogos), compuestos desde 2026 hasta el año de inicio de la época. Una época 2031 en C2 no es el mismo MW que 2026.

Referencias: PyPSA *snapshot_weightings*; Hörsch, Brown et al., PyPSA-Eur; GUI PyPSA-CL (PELP).

## 6. Límites (para no sobre-interpretar en un comité)

- No es un GEP completo tipo PELP/UPME (no dimensiona la red año a año con capex endógeno).
- La demanda nodal del STN físico es una **aproximación**; el modelo de 18 subáreas es el que mejor cierra con XM.
- El “último mes” XM recorta días preliminares (~¼ del SIN) para no distorsionar curvas.
- HiGHS en 18 nodos tarda décimas de segundo; el STN, segundos.

---

## 7. Arranque local

```bash
cd pypsa-col
pip install -r requirements.txt
PYTHONPATH=src streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
