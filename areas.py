# Clasifica políticas y consultas por área de la empresa (RRHH, Tecnología,
# Salud y Seguridad, Finanzas). Es una capa determinista, sin LLM: se basa en
# el nombre del archivo de la política y en palabras clave de la pregunta.

from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

AREA_GENERAL = "General"

AREA_POR_POLITICA: Dict[str, str] = {
    "Código de Ética y Conducta": "Recursos Humanos y Convivencia",
    "Política de Cero Tolerancia al Acoso y Hostigamiento": "Recursos Humanos y Convivencia",
    "Política de Trabajo Híbrido y Teletrabajo": "Recursos Humanos y Convivencia",
    "Política de Uso Aceptable de Activos Tecnológicos": "Tecnología y Seguridad de la Información",
    "Política de Confidencialidad y Protección de Datos": "Tecnología y Seguridad de la Información",
    "Política de Control de Accesos y Contraseñas": "Tecnología y Seguridad de la Información",
    "Política de Prevención de Riesgos Laborales": "Salud y Seguridad en el Trabajo",
    "Política de Alcohol, Drogas y Sustancias Prohibidas": "Salud y Seguridad en el Trabajo",
    "Política de Viáticos y Reembolso de Gastos": "Finanzas y Administración",
}

# Orden fijo en el que se muestran las áreas (catálogo, panel de métricas).
ORDEN_AREAS: List[str] = [
    "Recursos Humanos y Convivencia",
    "Tecnología y Seguridad de la Información",
    "Salud y Seguridad en el Trabajo",
    "Finanzas y Administración",
    AREA_GENERAL,
]

PALABRAS_CLAVE_POR_AREA: Dict[str, List[str]] = {
    "Recursos Humanos y Convivencia": [
        "acoso", "hostigamiento", "discriminacion", "etica", "conducta",
        "teletrabajo", "hibrido", "convivencia", "diversidad",
    ],
    "Tecnología y Seguridad de la Información": [
        "contrasena", "clave", "acceso", "confidencial", "datos", "laptop",
        "correo", "phishing", "ciberseguridad", "credenciales", "vpn",
        "software", "codigo fuente",
    ],
    "Salud y Seguridad en el Trabajo": [
        "accidente", "epp", "proteccion personal", "bodega", "montacargas",
        "riesgo laboral", "alcohol", "droga", "alcoholemia", "casco",
        "carga", "evacuacion",
    ],
    "Finanzas y Administración": [
        "viatico", "reembolso", "factura", "gasto", "hospedaje", "viaje",
        "comprobante", "anticipo", "movilidad",
    ],
}


def area_de_politica(nombre_politica: str) -> str:
    """Devuelve el área de una política según su nombre de archivo (sin extensión)."""
    return AREA_POR_POLITICA.get(nombre_politica, AREA_GENERAL)


def area_de_documentos(documentos: Optional[Iterable]) -> str:
    """
    Determina el área dominante entre los documentos recuperados por el RAG,
    según cuál área aparece con más frecuencia entre sus fuentes.
    """
    documentos = list(documentos or [])
    if not documentos:
        return AREA_GENERAL

    areas = [
        area_de_politica(Path(str(doc.metadata.get("source") or "")).stem)
        for doc in documentos
    ]
    return Counter(areas).most_common(1)[0][0]


def sub_areas_normalizar(texto: str) -> str:
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(texto).casefold())
    return "".join(c for c in texto if not unicodedata.combining(c))


def area_por_palabras_clave(texto: str) -> str:
    """Clasifica el área de una consulta por coincidencia de palabras clave, sin LLM."""
    normalizado = sub_areas_normalizar(texto)
    for area, palabras in PALABRAS_CLAVE_POR_AREA.items():
        if any(palabra in normalizado for palabra in palabras):
            return area
    return AREA_GENERAL


def agrupar_politicas_por_area(nombres_politicas: Iterable[str]) -> Dict[str, List[str]]:
    """Agrupa la lista de políticas por área, en el orden fijo de ORDEN_AREAS."""
    agrupado = defaultdict(list)
    for nombre in nombres_politicas:
        agrupado[area_de_politica(nombre)].append(nombre)

    return {
        area: sorted(agrupado[area])
        for area in ORDEN_AREAS
        if agrupado.get(area)
    }
