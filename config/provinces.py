"""
Configuración de TODAS las provincias de España y códigos del BOE.
Incluye las 50 provincias + Ceuta y Melilla (52 total)
"""

# Todas las provincias de España con sus códigos INE
PROVINCIAS_ESPANA = {
    "01": {"nombre": "Álava", "slug": "alava", "comunidad": "País Vasco"},
    "02": {"nombre": "Albacete", "slug": "albacete", "comunidad": "Castilla-La Mancha"},
    "03": {"nombre": "Alicante", "slug": "alicante", "comunidad": "Comunidad Valenciana"},
    "04": {"nombre": "Almería", "slug": "almeria", "comunidad": "Andalucía"},
    "05": {"nombre": "Ávila", "slug": "avila", "comunidad": "Castilla y León"},
    "06": {"nombre": "Badajoz", "slug": "badajoz", "comunidad": "Extremadura"},
    "07": {"nombre": "Baleares", "slug": "baleares", "comunidad": "Islas Baleares"},
    "08": {"nombre": "Barcelona", "slug": "barcelona", "comunidad": "Cataluña"},
    "09": {"nombre": "Burgos", "slug": "burgos", "comunidad": "Castilla y León"},
    "10": {"nombre": "Cáceres", "slug": "caceres", "comunidad": "Extremadura"},
    "11": {"nombre": "Cádiz", "slug": "cadiz", "comunidad": "Andalucía"},
    "12": {"nombre": "Castellón", "slug": "castellon", "comunidad": "Comunidad Valenciana"},
    "13": {"nombre": "Ciudad Real", "slug": "ciudad-real", "comunidad": "Castilla-La Mancha"},
    "14": {"nombre": "Córdoba", "slug": "cordoba", "comunidad": "Andalucía"},
    "15": {"nombre": "A Coruña", "slug": "a-coruna", "comunidad": "Galicia"},
    "16": {"nombre": "Cuenca", "slug": "cuenca", "comunidad": "Castilla-La Mancha"},
    "17": {"nombre": "Girona", "slug": "girona", "comunidad": "Cataluña"},
    "18": {"nombre": "Granada", "slug": "granada", "comunidad": "Andalucía"},
    "19": {"nombre": "Guadalajara", "slug": "guadalajara", "comunidad": "Castilla-La Mancha"},
    "20": {"nombre": "Guipúzcoa", "slug": "guipuzcoa", "comunidad": "País Vasco"},
    "21": {"nombre": "Huelva", "slug": "huelva", "comunidad": "Andalucía"},
    "22": {"nombre": "Huesca", "slug": "huesca", "comunidad": "Aragón"},
    "23": {"nombre": "Jaén", "slug": "jaen", "comunidad": "Andalucía"},
    "24": {"nombre": "León", "slug": "leon", "comunidad": "Castilla y León"},
    "25": {"nombre": "Lleida", "slug": "lleida", "comunidad": "Cataluña"},
    "26": {"nombre": "La Rioja", "slug": "la-rioja", "comunidad": "La Rioja"},
    "27": {"nombre": "Lugo", "slug": "lugo", "comunidad": "Galicia"},
    "28": {"nombre": "Madrid", "slug": "madrid", "comunidad": "Comunidad de Madrid"},
    "29": {"nombre": "Málaga", "slug": "malaga", "comunidad": "Andalucía"},
    "30": {"nombre": "Murcia", "slug": "murcia", "comunidad": "Región de Murcia"},
    "31": {"nombre": "Navarra", "slug": "navarra", "comunidad": "Navarra"},
    "32": {"nombre": "Ourense", "slug": "ourense", "comunidad": "Galicia"},
    "33": {"nombre": "Asturias", "slug": "asturias", "comunidad": "Principado de Asturias"},
    "34": {"nombre": "Palencia", "slug": "palencia", "comunidad": "Castilla y León"},
    "35": {"nombre": "Las Palmas", "slug": "las-palmas", "comunidad": "Canarias"},
    "36": {"nombre": "Pontevedra", "slug": "pontevedra", "comunidad": "Galicia"},
    "37": {"nombre": "Salamanca", "slug": "salamanca", "comunidad": "Castilla y León"},
    "38": {"nombre": "Santa Cruz de Tenerife", "slug": "santa-cruz-tenerife", "comunidad": "Canarias"},
    "39": {"nombre": "Cantabria", "slug": "cantabria", "comunidad": "Cantabria"},
    "40": {"nombre": "Segovia", "slug": "segovia", "comunidad": "Castilla y León"},
    "41": {"nombre": "Sevilla", "slug": "sevilla", "comunidad": "Andalucía"},
    "42": {"nombre": "Soria", "slug": "soria", "comunidad": "Castilla y León"},
    "43": {"nombre": "Tarragona", "slug": "tarragona", "comunidad": "Cataluña"},
    "44": {"nombre": "Teruel", "slug": "teruel", "comunidad": "Aragón"},
    "45": {"nombre": "Toledo", "slug": "toledo", "comunidad": "Castilla-La Mancha"},
    "46": {"nombre": "Valencia", "slug": "valencia", "comunidad": "Comunidad Valenciana"},
    "47": {"nombre": "Valladolid", "slug": "valladolid", "comunidad": "Castilla y León"},
    "48": {"nombre": "Vizcaya", "slug": "vizcaya", "comunidad": "País Vasco"},
    "49": {"nombre": "Zamora", "slug": "zamora", "comunidad": "Castilla y León"},
    "50": {"nombre": "Zaragoza", "slug": "zaragoza", "comunidad": "Aragón"},
    "51": {"nombre": "Ceuta", "slug": "ceuta", "comunidad": "Ciudad Autónoma"},
    "52": {"nombre": "Melilla", "slug": "melilla", "comunidad": "Ciudad Autónoma"},
}

# Mantener compatibilidad con código existente
PROVINCIAS_ANDALUCIA = {k: v for k, v in PROVINCIAS_ESPANA.items()
                        if v.get("comunidad") == "Andalucía"}

# Tipos de subasta
TIPOS_SUBASTA = {
    "J": "Judicial",
    "N": "Notarial",
    "A": "AEAT",
    "R": "Otras administraciones tributarias",
    "G": "Subastas administrativas generales",
}

# Estados de subasta
ESTADOS_SUBASTA = {
    "PU": "Próxima apertura",
    "EJ": "Celebrándose",
    "SU": "Suspendida",
    "CA": "Cancelada",
    "PC": "Concluida en Portal",
    "FS": "Finalizada por Autoridad",
}

# Tipos de bien
TIPOS_BIEN = {
    "I": "Inmuebles",
    "V": "Vehículos",
    "M": "Otros bienes muebles",
}

# Subtipos de inmueble
SUBTIPOS_INMUEBLE = {
    "vivienda": "Vivienda",
    "garaje": "Garaje",
    "trastero": "Trastero",
    "local": "Local comercial",
    "nave": "Nave industrial",
    "finca": "Finca rústica",
    "solar": "Solar",
    "otros": "Otros inmuebles",
}


def get_provincia_nombre(codigo: str) -> str:
    """Obtiene el nombre de la provincia por su código."""
    return PROVINCIAS_ESPANA.get(codigo, {}).get("nombre", "Desconocida")


def get_provincia_slug(codigo: str) -> str:
    """Obtiene el slug de la provincia por su código."""
    return PROVINCIAS_ESPANA.get(codigo, {}).get("slug", "desconocida")


def get_provincia_comunidad(codigo: str) -> str:
    """Obtiene la comunidad autónoma de la provincia."""
    return PROVINCIAS_ESPANA.get(codigo, {}).get("comunidad", "Desconocida")


def get_estado_nombre(codigo: str) -> str:
    """Obtiene el nombre del estado por su código."""
    return ESTADOS_SUBASTA.get(codigo, "Desconocido")


def get_tipo_subasta_nombre(codigo: str) -> str:
    """Obtiene el nombre del tipo de subasta por su código."""
    return TIPOS_SUBASTA.get(codigo, "Desconocido")


def get_todas_provincias() -> list:
    """Retorna lista de todos los códigos de provincia."""
    return list(PROVINCIAS_ESPANA.keys())


def get_provincias_por_comunidad(comunidad: str) -> dict:
    """Retorna provincias filtradas por comunidad autónoma."""
    return {k: v for k, v in PROVINCIAS_ESPANA.items()
            if v.get("comunidad") == comunidad}
