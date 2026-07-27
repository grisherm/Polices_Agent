
# memoria.py

# Funciones (llamadas desde Main.py):
#   - obtener_historial()  → devuelve los mensajes anteriores de una sesión
#   - guardar_turno()      → guarda un par pregunta+respuesta en el historial
#   - borrar_historial()   → elimina el historial de una sesión
#   - condensar_pregunta() → reformula la pregunta nueva usando el historial


from threading import Lock
from typing import Dict, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


MAX_MENSAJES = 4

# Almacén en RAM: { thread_id: [{role, content}, ...] }
_historiales: Dict[str, List[Dict[str, str]]] = {}

# Un lock por sesión para no mezclar mensajes de la misma conversación
_locks_por_thread: Dict[str, Lock] = {}

# Lock auxiliar solo para crear nuevas entradas en el diccionario anterior
_lock_creacion = Lock()


def obtener_lock(thread_id: str) -> Lock:
    """Devuelve el lock de una sesión, creándolo si no existe."""
    with _lock_creacion:
        return _locks_por_thread.setdefault(thread_id, Lock())


def obtener_historial(thread_id: str) -> List[Dict[str, str]]:
    """Devuelve los mensajes anteriores de una sesión. Lista vacía si no existe."""
    return _historiales.get(thread_id, [])


def guardar_turno(thread_id: str, pregunta_original: str, respuesta: str) -> None:
    """Agrega un par pregunta+respuesta al historial y descarta los más viejos si supera el límite."""
    historial = _historiales.setdefault(thread_id, [])

    historial.append({"role": "user",      "content": pregunta_original})
    historial.append({"role": "assistant", "content": respuesta})

    limite = MAX_MENSAJES * 2
    if len(historial) > limite:
        _historiales[thread_id] = historial[-limite:]


def borrar_historial(thread_id: str) -> None:
    """Elimina el historial de una sesión por completo."""
    _historiales.pop(thread_id, None)
    with _lock_creacion:
        _locks_por_thread.pop(thread_id, None)


def condensar_pregunta(
    pregunta_nueva: str,
    historial: List[Dict[str, str]],
    llm: BaseChatModel,
) -> str:
    """
    Convierte un mensaje dependiente del historial en uno autónomo.
    No cambia la intención original ni inventa un tema.
    """
    if not historial:
        return pregunta_nueva

    historial_texto = "\n".join(
        f"{'Usuario' if m['role'] == 'user' else 'Asistente'}: {m['content']}"
        for m in historial
    )

    prompt_condensacion = (
        "Reformula el mensaje nuevo para que pueda entenderse sin leer el "
        "historial. Utiliza el historial únicamente para resolver referencias "
        "como 'eso', 'ese trámite', 'lo anterior', 'esa política' o temas "
        "omitidos claramente relacionados con la conversación.\n\n"

        "Reglas obligatorias:\n"
        "- Conserva exactamente la intención original del usuario.\n"
        "- No conviertas una solicitud de acción en una pregunta informativa.\n"
        "- No conviertas un saludo o mensaje social en una consulta corporativa.\n"
        "- No inventes políticas, trámites, personas, montos ni temas.\n"
        "- Si no existe un antecedente claro, devuelve el mensaje sin cambios.\n"
        "- No respondas la consulta.\n"
        "- Devuelve únicamente el mensaje reformulado.\n\n"

        f"Historial:\n{historial_texto}\n\n"
        f"Mensaje nuevo: {pregunta_nueva}\n\n"
        "Mensaje autónomo:"
    )

    respuesta = llm.invoke(
        [
            SystemMessage(
                content=(
                    "Reescribes mensajes usando contexto conversacional sin "
                    "inventar información ni cambiar la intención del usuario."
                )
            ),
            HumanMessage(content=prompt_condensacion),
        ]
    )

    pregunta_condensada = respuesta.content.strip()

    print(f"[MEMORIA] Pregunta original: '{pregunta_nueva}'")
    print(f"[MEMORIA] Pregunta autónoma: '{pregunta_condensada}'")

    return pregunta_condensada