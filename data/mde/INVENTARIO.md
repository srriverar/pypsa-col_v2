# LEAP Colombia — paquete de referencia para el Motor A

Fecha de descarga: **28 de octubre de 2026**.

**No es un clon ejecutable de LEAP ni una reproducción validada de sus ecuaciones.**
PEN (UPME) y NDC (MinAmbiente) son **modelos distintos**: no se fusionan.

## Integridad (SHA-256)

| Archivo | SHA-256 | Estado |
| --- | --- | --- |
| `escbase2022v26_20_06_2023.leap` (alias `PEN_2022_2052.leap`) | `86620f414fdc492ee0bc3e0d8ef080601f2ddceb994731f21cb714e584c0ac9d` | coincide |
| `Anexo_Resultados_PEN_2022_2052.xlsx` | `f454451ca02b7fa9d232d617103b81591d86681e83223509baf5625c28f1dc7c` | coincide |
| `ndc_col_2020.zip` | `d14664c50af681af0577abab60f31a58ad3171f04582b70dc3bc95c84b5dd05f` | coincide |

Los `.leap` son ZIP/NexusDB con **AES**. Se lista el interior; **no** se extraen fórmulas. No se elude el cifrado.

El ZIP NDC contiene `ndc_col_2020.leap` (~72 MB). Se conserva en el ZIP para no duplicar.

## Qué sí usamos ya

`resultados_PEN_2022_2052.csv` — celdas de energético del anexo (hoja, celda Excel, escenario, año, valor, unidad). `data_only=True`, sin recalcular fórmulas.

Controles (Actualización, transporte, 2030):

- Gasolina `Consumo Final A!I23` = 372,7692759648167 PJ/año
- Diésel `J23` = 280,9960516564333 PJ/año
- GEI gasolina `Emisiones Consumo Final A!I23` = 26,35848190858241 MtCO₂eq/año
- GEI diésel `J23` = 20,91980979353673 MtCO₂eq/año

Son **resultados de un escenario histórico publicado**, no mediciones ni proyecciones oficiales vigentes.

## Derechos

Archivos de portales públicos, con atribución. Eso no abre la licencia de LEAP ni autoriza redistribuir datos confidenciales.
