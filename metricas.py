# Contador de uso en memoria: consultas por área y por acción final.
# Se reinicia cuando se reinicia el servicio; no se persiste en disco ni en BD.

import threading
from collections import Counter
from typing import Dict

_lock = threading.Lock()
_total_preguntas = 0
_por_area = Counter()
_por_accion = Counter()


def registrar_evento(area: str, accion_final: str) -> None:
    """Incrementa los contadores tras procesar una consulta del chat."""
    global _total_preguntas
    with _lock:
        _total_preguntas += 1
        if area:
            _por_area[area] += 1
        if accion_final:
            _por_accion[accion_final] += 1


def obtener_metricas() -> Dict:
    """Devuelve una foto actual de los contadores acumulados."""
    with _lock:
        return {
            "total_preguntas": _total_preguntas,
            "por_area": dict(_por_area),
            "por_accion": dict(_por_accion),
        }
