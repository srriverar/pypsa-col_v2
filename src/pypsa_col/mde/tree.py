"""Demand tree (MDE-Colombia). Homologates BECO sectors ↔ PEN LEAP anexo.

This is NOT claimed identical to the unpublished LEAP branch IDs inside the
.leap NexusDB. It is the functional tree used for Motor A v1, mapped to the
six blocks of the anexo PEN 2022–2052.
"""

from __future__ import annotations

BRANCHES = [
    # id, parent, sector, end_use, methodology, leap_ref, beco, ipcc
    ("0", None, "supuestos", None, "driver", "Key parameters", "—", "—"),
    ("0.pob", "0", "supuestos", "poblacion", "driver", "Población", "DANE", "—"),
    ("0.hog", "0", "supuestos", "hogares", "driver", "Hogares urbano/rural", "DANE", "—"),
    ("1", None, "residencial", None, "hybrid", "Residencial", "Residencial", "1A4b"),
    ("1.u", "1", "residencial", "urbano", "useful", "Urbano", "Residencial", "1A4b"),
    ("1.r", "1", "residencial", "rural", "useful", "Rural", "Residencial", "1A4b"),
    ("1.coccion", "1", "residencial", "coccion", "useful", "Cocción", "Residencial", "1A4b"),
    ("1.refri", "1", "residencial", "refrigeracion", "stock", "Refrigeración", "Residencial", "1A4b"),
    ("1.ilum", "1", "residencial", "iluminacion", "stock", "Iluminación", "Residencial", "1A4b"),
    ("1.clima", "1", "residencial", "climatizacion", "useful", "Climatización", "Residencial", "1A4b"),
    ("1.agua", "1", "residencial", "agua_caliente", "useful", "Agua caliente", "Residencial", "1A4b"),
    ("1.elec", "1", "residencial", "electronicos", "stock", "Electrónicos", "Residencial", "1A4b"),
    ("2", None, "transporte", None, "stock", "Transporte", "Transporte", "1A3"),
    ("2.pax", "2", "transporte", "pasajeros_carretero", "stock", "Pasajeros", "Transporte", "1A3b"),
    ("2.carga", "2", "transporte", "carga_carretera", "stock", "Carga", "Transporte", "1A3b"),
    ("2.aereo", "2", "transporte", "aereo_nacional", "intensity", "Aviación nacional", "Transporte", "1A3a"),
    ("2.bunker", "2", "transporte", "bunker_internacional", "intensity", "Búnker (cuenta separada)", "Búnker", "1A3a/d"),
    ("2.fluv", "2", "transporte", "fluvial", "intensity", "Fluvial", "Transporte", "1A3d"),
    ("2.fer", "2", "transporte", "ferreo", "intensity", "Férreo", "Transporte", "1A3c"),
    ("3", None, "industria", None, "intensity", "Industria", "Industria", "1A2"),
    ("3.cal", "3", "industria", "calor", "useful", "Calor de proceso", "Industria", "1A2"),
    ("3.fm", "3", "industria", "fuerza_motriz", "stock", "Fuerza motriz", "Industria", "1A2"),
    ("3.none", "3", "industria", "no_energetico", "intensity", "Uso no energético (separado)", "No energético", "2"),
    ("3.cog", "3", "industria", "cogeneracion", "transformation", "Cogeneración (cuenta propia)", "Transformación", "1A1"),
    ("4", None, "terciario", None, "intensity", "Terciario / comercial-público", "Comercial y público", "1A4a"),
    ("4.clima", "4", "terciario", "climatizacion", "useful", "Climatización", "Comercial y público", "1A4a"),
    ("4.ilum", "4", "terciario", "iluminacion", "stock", "Iluminación", "Comercial y público", "1A4a"),
    ("4.dc", "4", "terciario", "centros_datos", "intensity", "Centros de datos", "Comercial y público", "1A4a"),
    ("5", None, "agro_const_mineria", None, "intensity", "Agropecuario, construcción y minería", "Resto BECO", "1A4c/1A2"),
    ("5.riego", "5", "agro_const_mineria", "bombeo", "stock", "Riego", "Agropecuario", "1A4c"),
    ("5.min", "5", "agro_const_mineria", "mineria", "intensity", "Minería", "Minería", "1A2"),
    ("6", None, "no_energetico", None, "intensity", "No energético", "No energético", "2"),
    ("9.zni", None, "cuentas", "electricidad_zni", "intensity", "Electricidad ZNI", "Electricidad", "1A1"),
    ("9.sin", None, "cuentas", "electricidad_sin", "intensity", "Electricidad SIN", "Electricidad", "1A1"),
]


def as_frame():
    import pandas as pd

    cols = ["branch_id", "parent", "sector", "end_use", "methodology", "leap_ref", "beco", "ipcc"]
    return pd.DataFrame(BRANCHES, columns=cols)
