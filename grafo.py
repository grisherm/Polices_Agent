# Define el flujo del agente como un grafo de nodos.
# Cada mensaje entra por el triaje y toma un camino distinto según la decisión del LLM.

from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from busqueda_rag import recuperar_y_generar_respuesta, verificar_respuesta_rag
from triaje import ejecutar_triaje


class AgentState(TypedDict, total=False):
    """Estado compartido que se pasa entre los nodos del grafo."""
    pregunta:         str
    triaje:           dict
    respuesta_rag:    str
    documentos_rag:   list
    verificacion_rag: dict
    respuesta:        Optional[str]
    citaciones:       list
    accion_final:     str


def construir_grafo(
    cadena_triaje,
    prompt_triaje: str,
    nombres_politicas: list,
    retriever,
    cadena_rag,
    cadena_verificacion,
):
    """
    Arma y compila el grafo con todos sus nodos y conexiones.
    Retorna el grafo compilado listo para invocar con .invoke().
    """

    def nodo_triaje(state: AgentState) -> AgentState:
        """
        Reutiliza el triaje realizado por Main.py.
        Si el grafo fue invocado directamente, realiza el triaje normalmente.
        """
        print("[GRAFO] Nodo: triaje")

        triaje_precalculado = state.get("triaje")

        if triaje_precalculado:
            print("[GRAFO] Reutilizando triaje precalculado")
            return {"triaje": triaje_precalculado}

        print("[GRAFO] No se recibió triaje previo; ejecutando triaje")
        resultado = ejecutar_triaje(
            state["pregunta"],
            cadena_triaje,
            prompt_triaje,
        )
        return {"triaje": resultado}

    def nodo_consultar_rag(state: AgentState) -> AgentState:
        """Busca documentos en FAISS y genera una respuesta candidata."""
        print("[GRAFO] Nodo: consultar_rag")
        return recuperar_y_generar_respuesta(state["pregunta"], retriever, cadena_rag)

    def nodo_verificar_rag(state: AgentState) -> AgentState:
        """Verifica si la respuesta candidata está respaldada por los documentos."""
        print("[GRAFO] Nodo: verificar_rag")
        resultado = verificar_respuesta_rag(
            pregunta=state["pregunta"],
            respuesta=state.get("respuesta_rag") or "",
            documentos=state.get("documentos_rag") or [],
            cadena_verificacion=cadena_verificacion,
        )
        print(f"[VERIFICADOR] decisión={resultado.decision} | motivo={resultado.motivo}")
        return {"verificacion_rag": resultado.model_dump()}

    def nodo_respuesta_ok(state: AgentState) -> AgentState:
        """La respuesta está verificada; se envía al usuario con sus citaciones."""
        print("[GRAFO] Nodo: respuesta_ok")
        return {
            "respuesta":    state["respuesta_rag"],
            "citaciones":   state.get("documentos_rag") or [],
            "accion_final": "AUTO_RESOLVER",
        }

    def nodo_no_se(_state: AgentState) -> AgentState:
        """El agente no encontró información suficiente en los PDFs."""
        print("[GRAFO] Nodo: no_se")
        return {
            "respuesta":    "No lo sé.",
            "citaciones":   [],
            "accion_final": "SIN_INFORMACION",
        }

    def nodo_pedir_info(state: AgentState) -> AgentState:
        """Pide al usuario que precise su consulta porque es demasiado vaga."""
        print("[GRAFO] Nodo: pedir_info")

        # Priorizar campos del verificador; si no hay, usar los del triaje
        campos_verificador = (state.get("verificacion_rag") or {}).get("campos_faltantes") or []
        campos_triaje      = (state.get("triaje") or {}).get("campos_faltantes") or []
        campos             = campos_verificador or campos_triaje

        if campos:
            campos_limpios = [str(c).replace("_", " ").strip() for c in campos]
            respuesta = (
                "Para ayudarte mejor necesito más información. "
                "Por favor indícame: " + ", ".join(campos_limpios) + "."
            )
        else:
            respuesta = "Por favor indícame qué política o tema deseas consultar."

        return {
            "respuesta":    respuesta,
            "citaciones":   [],
            "accion_final": "PEDIR_INFO",
        }

    def nodo_abrir_ticket(state: AgentState) -> AgentState:
        """Indica al frontend que debe ofrecer el formulario de ticket."""
        print("[GRAFO] Nodo: abrir_ticket")
        urgencia_verificador = (state.get("verificacion_rag") or {}).get("urgencia")
        urgencia_triaje      = (state.get("triaje") or {}).get("urgencia", "BAJA")
        urgencia             = urgencia_verificador or urgencia_triaje

        return {
            "respuesta": (
                f"Esta solicitud requiere una gestión directa con urgencia "
                f"{urgencia}. Para continuar, completa el formulario del ticket. "
                "Podrás revisar y ampliar la información antes de enviarla."
            ),
            "citaciones":   [],
            "accion_final": "ABRIR_TICKET",
        }

    def nodo_fuera_de_ambito(_state: AgentState) -> AgentState:
        """La pregunta no tiene relación con Alicorp ni sus políticas."""
        print("[GRAFO] Nodo: fuera_de_ambito")
        return {
            "respuesta":    "Lo siento, solo puedo responder consultas sobre las políticas de Alicorp.",
            "citaciones":   [],
            "accion_final": "FUERA_DE_AMBITO",
        }

    def nodo_saludo(_state: AgentState) -> AgentState:
        """El usuario saludó o se despidió."""
        print("[GRAFO] Nodo: saludo")
        return {
            "respuesta": (
                "¡Hola! Soy el asistente virtual de políticas corporativas de "
                "Alicorp. ¿En qué puedo ayudarte hoy?"
            ),
            "citaciones":   [],
            "accion_final": "SALUDO",
        }

    def nodo_listar_politicas(_state: AgentState) -> AgentState:
        """Devuelve el catálogo completo de políticas sin consultar FAISS."""
        print("[GRAFO] Nodo: listar_politicas")
        total   = len(nombres_politicas)
        listado = "\n".join(
            f"{numero}. {nombre}"
            for numero, nombre in enumerate(nombres_politicas, start=1)
        )
        return {
            "respuesta": (
                f"Tengo información sobre {total} políticas de Alicorp:\n\n{listado}"
            ),
            "citaciones":   [],
            "accion_final": "LISTAR_POLITICAS",
        }

    def decidir_ruta_triaje(state: AgentState) -> str:
        """Lee la decisión del triaje y devuelve el nombre de la ruta."""
        decision = (state.get("triaje") or {}).get("decision", "PEDIR_MAS_INFORMACION")
        rutas = {
            "CONSULTAR_RAG":         "rag",
            "LISTAR_POLITICAS":      "listar",
            "PEDIR_MAS_INFORMACION": "info",
            "ABRIR_TICKET":          "ticket",
            "FUERA_DE_AMBITO":       "fuera",
            "SALUDO":                "saludo",
        }
        ruta = rutas.get(decision, "info")
        print(f"[GRAFO] Ruta del triaje: {ruta}")
        return ruta

    def decidir_verificacion(state: AgentState) -> str:
        """Lee la decisión del verificador y devuelve el nombre de la ruta."""
        decision = (state.get("verificacion_rag") or {}).get("decision", "NO_SE")
        rutas = {
            "RESPUESTA_OK": "ok",
            "NO_SE":        "no_se",
            "PEDIR_INFO":   "info",
            "ABRIR_TICKET": "ticket",
        }
        ruta = rutas.get(decision, "no_se")
        print(f"[GRAFO] Ruta posterior al RAG: {ruta}")
        return ruta

    workflow = StateGraph(AgentState)

    workflow.add_node("triaje",           nodo_triaje)
    workflow.add_node("consultar_rag",    nodo_consultar_rag)
    workflow.add_node("verificar_rag",    nodo_verificar_rag)
    workflow.add_node("respuesta_ok",     nodo_respuesta_ok)
    workflow.add_node("no_se",            nodo_no_se)
    workflow.add_node("listar_politicas", nodo_listar_politicas)
    workflow.add_node("pedir_info",       nodo_pedir_info)
    workflow.add_node("abrir_ticket",     nodo_abrir_ticket)
    workflow.add_node("fuera_de_ambito",  nodo_fuera_de_ambito)
    workflow.add_node("saludo",           nodo_saludo)

    workflow.add_edge(START, "triaje")

    workflow.add_conditional_edges(
        "triaje",
        decidir_ruta_triaje,
        {
            "rag":    "consultar_rag",
            "listar": "listar_politicas",
            "info":   "pedir_info",
            "ticket": "abrir_ticket",
            "fuera":  "fuera_de_ambito",
            "saludo": "saludo",
        },
    )

    workflow.add_edge("consultar_rag", "verificar_rag")
    workflow.add_conditional_edges(
        "verificar_rag",
        decidir_verificacion,
        {
            "ok":     "respuesta_ok",
            "no_se":  "no_se",
            "info":   "pedir_info",
            "ticket": "abrir_ticket",
        },
    )

    for nodo_final in (
        "respuesta_ok", "no_se", "listar_politicas", "pedir_info",
        "abrir_ticket", "fuera_de_ambito", "saludo",
    ):
        workflow.add_edge(nodo_final, END)

    return workflow.compile()


def guardar_diagrama_grafo(grafo, ruta_salida: str = "grafo_agente.png") -> None:
    """Guarda una imagen PNG del diagrama del grafo. Si falla, solo avisa y sigue."""
    try:
        contenido = grafo.get_graph().draw_mermaid_png()
        with open(ruta_salida, "wb") as archivo:
            archivo.write(contenido)
        print(f"Diagrama del grafo guardado en: '{ruta_salida}'")
    except Exception as exc:
        print(f"No se pudo generar el diagrama del grafo: {exc}")
