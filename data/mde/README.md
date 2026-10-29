# Motor A — fuentes clonadas (corte 28 oct 2026)

| Archivo | Origen | Uso |
| --- | --- | --- |
| `leap/escbase2022v26_20_06_2023.leap` | [UPME PEN 2022–2052](https://www.upme.gov.co/simec/planeacion-energetica/plan-energetico-nacional-1/) — *Archivo de simulación en LEAP* | Modelo de referencia. NexusDB cifrado AES; **no se ejecuta** en esta app. Hash local al descargar. |
| `leap/escbase2020v25_13_11_2020.leap` | UPME PEN 2020–2050 | Antecesor. Zip NexusDB; metadatos en `sysinfo` (base 2019, escenarios Tendencial / Pop-Ac / Modernización / Inflexión / Disrupción, 16 time-slices). |
| `leap/Anexo_Resultados_PEN_2022_2052.xlsx` | Mismo portal UPME | **Exportación numérica oficial** del LEAP 2022 (consumo final y emisiones por sector × energético × año × escenario). Es el contrato de equivalencia v1. |
| `leap/Supuestos_PEN_2020_2050.xlsx` | UPME PEN 2020 | Supuestos del plan anterior. |
| `pen_consumo_emisiones.csv` | Generado por `pypsa_col.mde.pen_import` | Tabla larga (36 312 filas) lista para el motor. |

**No se afirma equivalencia bit a bit con LEAP.** El archivo `.leap` 2022 está cifrado; el anexo es lo que UPME publicó para reproducir resultados. El árbol de ramas de Motor A es una homologación funcional (BECO ↔ PEN ↔ IPCC), no una extracción de `masterstructure.nx1`.

Manual LEAP-Colombia NDC 2020 (MinAmbiente/PMR): otro objeto, no el PEN.
https://www.minambiente.gov.co/wp-content/uploads/2022/09/PMR_LEAPColombia-Manual_20201209.pdf
