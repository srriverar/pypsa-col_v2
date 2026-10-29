# Tesis STN inputs (Juan Moreno, Uniandes)

Copied from [`JuanMoreno2000/Tesis_RedTransmisionColombia`](https://github.com/JuanMoreno2000/Tesis_RedTransmisionColombia)
(undergraduate *proyecto de grado*, 2024) and used by `pypsa_col.stn_tesis`.

| File | Role |
| --- | --- |
| `Lineas_Transmisión(actualizado).xlsx` | PARATEC 220/230/500 kV circuits |
| `SUBESTACIONES.json` | ArcGIS substations (coords, department) |
| `Generacion.xlsx` | Plant → bus mapping (76 units in this dump) |
| `MPODE-PYPSA.xlsx` | MPODE nodal load mapped onto STN names |
| `bus_coords_manual.csv` | Manual lon/lat from `Base.ipynb` |
| `RED_STN_COLOMBIA.nc` | *Proyecto base* 125 buses / 193 lines / 0 transformers |
| `dbus.csv`, `dcirc.csv` | MPODE dumps (not used by the builder) |

The master's thesis (2026) reports **147 buses, 206 lines, 34 transformers**
on a later PARATEC vintage that is **not** in the public repo. PyPSA-col
reconstructs the master's *method* (voltage-split buses + transformers at
multi-kV substations + 18-subarea aggregation) from this extract.

`pypsa-meets-earth/pypsa-colombia` is an OSM/Snakemake Earth workflow — it is
**not** this 147-node STN.
