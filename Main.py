# Punto de entrada del proyecto. Levanta un servidor FastAPI en el puerto 8000
# expone endpoints para consultar al agente e interactuar con el frontend.
# Ejecutar con: python Main.py

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

import config
from busqueda_rag import construir_cadena_rag, construir_cadena_verificacion
from documentos import obtener_nombres_politicas
from grafo import construir_grafo, guardar_diagrama_grafo
from memoria import (
    borrar_historial,
    condensar_pregunta,
    guardar_turno,
    obtener_historial,
    obtener_lock,
)
from providers import construir_embeddings, construir_llm
from triaje import (
    construir_cadena_triaje,
    construir_prompt_triaje,
    ejecutar_triaje,
)
from tickets import TicketRequest, TicketResponse, enviar_ticket_por_correo
from vectorstore import (
    construir_o_cargar_vectorstore,
    construir_retriever,
)

# Estado global en memoria para guardar el grafo compilado y componentes cargados
state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga e inicializa todos los componentes del agente al arrancar el servidor."""
    print("Iniciando componentes del agente de IA y RAG de Alicorp...")
    try:
        llm = construir_llm()
        modelo_embeddings = construir_embeddings()

        # Obtiene nombres de políticas sin cargar PDFs en memoria
        nombres_politicas = obtener_nombres_politicas()
        lista_politicas = "\n".join(f"- {nombre}." for nombre in nombres_politicas)

        prompt_triaje = construir_prompt_triaje(lista_politicas)
        cadena_triaje = construir_cadena_triaje(llm)

        # Carga el índice existente. Reconstruye internamente cargando PDFs/chunks
        # solo si la huella del directorio de documentos cambió.
        vectorstore = construir_o_cargar_vectorstore(
            modelo_embeddings,
        )
        retriever = construir_retriever(vectorstore)
        cadena_rag = construir_cadena_rag(llm)
        cadena_verificacion = construir_cadena_verificacion(llm)

        grafo = construir_grafo(
            cadena_triaje,
            prompt_triaje,
            nombres_politicas,
            retriever,
            cadena_rag,
            cadena_verificacion,
        )

        guardar_diagrama_grafo(grafo)

        state["grafo"]   = grafo
        state["llm"]     = llm
        state["cadena_triaje"]  = cadena_triaje
        state["prompt_triaje"]  = prompt_triaje
        state["politicas"]      = nombres_politicas

        print("¡El agente de IA se ha inicializado y compilado correctamente!")
    except Exception as e:
        print(f"Error crítico durante la inicialización del agente: {e}")
        raise e
    yield
    state.clear()


app = FastAPI(
    title="Alicorp RAG Agent API",
    description="API REST para interactuar con el Agente de Políticas Corporativas de Alicorp.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    pregunta: str = Field(..., description="La pregunta o consulta del colaborador.")
    thread_id: str = Field(default="default", description="Identificador único de la sesión.")


class Citation(BaseModel):
    texto: str = Field(..., description="Fragmento de texto citado.")
    fuente: str = Field(..., description="Nombre del archivo PDF origen de la cita.")
    pagina: int = Field(..., description="Número de página en el PDF.")


class TriageInfo(BaseModel):
    decision: str = Field(..., description="Decisión tomada en el triaje.")
    urgencia: str = Field(..., description="Nivel de urgencia detectado.")

    campos_faltantes: List[str] = Field(
        default_factory=list,
        description="Lista de datos faltantes.",
    )

    usa_historial: bool = Field(
        default=False,
        description="Indica si la consulta necesitó el historial conversacional.",
    )

class ChatResponse(BaseModel):
    pregunta: str
    respuesta: str
    accion_final: str
    triaje: TriageInfo
    citaciones: List[Citation] = Field(default_factory=list)


class TriageOnlyResponse(BaseModel):
    pregunta: str
    respuesta: str
    accion_final: str
    triaje: TriageInfo
    citaciones: List[Citation] = Field(default_factory=list)


@app.get("/health", summary="Diagnóstico de la API")
def health_check():
    """Retorna el estado de la API para confirmar que está activa."""
    if "grafo" not in state:
        return {"status": "starting or error"}
    return {"status": "ok"}


@app.get("/api/politicas", summary="Listar políticas cubiertas")
def get_politicas():
    """Retorna la lista de nombres de políticas que el agente tiene indexadas."""
    if "politicas" not in state:
        raise HTTPException(status_code=503, detail="La API no está completamente cargada aún.")
    return {"politicas": state["politicas"]}


@app.delete("/api/chat/historial/{thread_id}", summary="Borrar historial de una conversación")
def delete_historial(thread_id: str):
    """Borra el historial de conversación de un hilo específico."""
    borrar_historial(thread_id)
    return {"mensaje": f"Historial de la sesión '{thread_id}' eliminado correctamente."}


@app.post("/api/tickets", response_model=TicketResponse)
def crear_ticket(ticket: TicketRequest):
    """Recibe el formulario y envía el correo."""
    try:
        return enviar_ticket_por_correo(ticket)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        print(f"Error enviando ticket: {type(error).__name__}: {error}")
        raise HTTPException(status_code=502, detail="No se pudo enviar el ticket.") from error


@app.post("/api/triaje", response_model=TriageOnlyResponse, summary="Clasificar una consulta sin ejecutar el RAG")
def classify_question(req: ChatRequest):
    """Ejecuta únicamente el triaje para clasificar la consulta."""
    if "cadena_triaje" not in state:
        raise HTTPException(status_code=503, detail="El triaje aún no está listo.")

    pregunta = req.pregunta.strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    thread_id = req.thread_id.strip() or "default"

    try:
        with obtener_lock(thread_id):
            resultado = ejecutar_triaje(
                pregunta,
                state["cadena_triaje"],
                state["prompt_triaje"],
            )
    except Exception as error:
        print(f"Error clasificando la consulta '{pregunta}': {error}")
        raise HTTPException(status_code=500, detail=f"Error interno en el triaje: {error}")

    acciones = {
        "SALUDO": "SALUDO",
        "FUERA_DE_AMBITO": "FUERA_DE_AMBITO",
        "PEDIR_MAS_INFORMACION": "PEDIR_INFO",
        "ABRIR_TICKET": "ABRIR_TICKET",
        "CONSULTAR_RAG": "CONSULTAR_RAG",
        "LISTAR_POLITICAS": "LISTAR_POLITICAS",
    }
    decision = resultado["decision"]

    return TriageOnlyResponse(
        pregunta=pregunta,
        respuesta=f"Clasificación de triaje: {decision}",
        accion_final=acciones.get(decision, "ERROR_TRIAJE"),
        triaje=TriageInfo(**resultado),
        citaciones=[],
    )


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Enviar una consulta al agente",
)
def ask_question(req: ChatRequest):
    """Procesa una consulta usando triaje, memoria, RAG y verificación."""

    if "grafo" not in state:
        raise HTTPException(status_code=503, detail="El agente no está listo.")

    pregunta_original = req.pregunta.strip()
    thread_id = req.thread_id.strip() or "default"

    if not pregunta_original:
        raise HTTPException(
            status_code=400,
            detail="La pregunta no puede estar vacía.",
        )

    try:
        with obtener_lock(thread_id):
            historial = obtener_historial(thread_id)

            # 1. Primero se clasifica exclusivamente el mensaje original.
            triaje_inicial = ejecutar_triaje(
                pregunta_original,
                state["cadena_triaje"],
                state["prompt_triaje"],
            )

            pregunta_para_grafo = pregunta_original
            triaje_para_grafo = triaje_inicial

            # 2. Solo se consulta la memoria cuando el triaje determina
            #    semánticamente que el mensaje depende del historial.
            if historial and triaje_inicial.get("usa_historial", False):
                pregunta_para_grafo = condensar_pregunta(
                    pregunta_original,
                    historial,
                    state["llm"],
                )

                # Se vuelve a clasificar la pregunta ahora autónoma.
                triaje_para_grafo = ejecutar_triaje(
                    pregunta_para_grafo,
                    state["cadena_triaje"],
                    state["prompt_triaje"],
                )

                # Conservamos el dato de que sí se utilizó memoria.
                triaje_para_grafo["usa_historial"] = True

            # 3. El grafo recibe y reutiliza el triaje ya calculado.
            resultado = state["grafo"].invoke(
                {
                    "pregunta": pregunta_para_grafo,
                    "triaje": triaje_para_grafo,
                }
            )

            # 4. Formatear las fuentes recuperadas.
            citaciones_originales = resultado.get("citaciones") or []
            citaciones_formateadas = []

            for doc in citaciones_originales:
                source = doc.metadata.get("source", "Desconocido")
                filename = Path(source).name

                try:
                    page = int(doc.metadata.get("page", 0)) + 1
                except (TypeError, ValueError):
                    page = 1

                citaciones_formateadas.append(
                    Citation(
                        texto=doc.page_content,
                        fuente=filename,
                        pagina=page,
                    )
                )

            # 5. Obtener el triaje final.
            triaje_datos = resultado.get("triaje") or {}

            triage_info = TriageInfo(
                decision=triaje_datos.get(
                    "decision",
                    "PEDIR_MAS_INFORMACION",
                ),
                urgencia=triaje_datos.get("urgencia", "BAJA"),
                campos_faltantes=triaje_datos.get(
                    "campos_faltantes"
                ) or [],
                usa_historial=triaje_datos.get(
                    "usa_historial",
                    False,
                ),
            )

            respuesta_final = (
                resultado.get("respuesta")
                or "No se pudo generar una respuesta a tu consulta."
            )

            # 6. Los mensajes sociales y fuera de ámbito no contaminan
            #    la memoria del tema corporativo.
            decision_final = triage_info.decision

            if decision_final not in {"SALUDO", "FUERA_DE_AMBITO"}:
                guardar_turno(
                    thread_id,
                    pregunta_original,
                    respuesta_final,
                )

        return ChatResponse(
            pregunta=pregunta_original,
            respuesta=respuesta_final,
            accion_final=resultado.get("accion_final") or "PEDIR_INFO",
            triaje=triage_info,
            citaciones=citaciones_formateadas,
        )

    except Exception as error:
        print(
            f"Error procesando la consulta "
            f"'{pregunta_original}': {error}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar la consulta: {error}",
        )

# La compilación de React se sirve desde el mismo proceso y dominio que la API.
# Este montaje debe ir después de declarar todas las rutas /api.
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )
else:
    @app.get("/", include_in_schema=False)
    def frontend_no_compilado():
        raise HTTPException(
            status_code=503,
            detail=(
                "El frontend todavía no está compilado. Ejecuta: "
                "cd frontend && npm install && npm run build"
            ),
        )


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Iniciando el servidor API en http://{host}:{port}...")
    uvicorn.run(app, host=host, port=port, reload=False, workers=1)
