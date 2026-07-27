# Implementa el clasificador de mensajes del agente.
# Decide qué hacer con cada consulta antes de buscar en los PDFs.

import json
import time
from typing import Dict, List, Literal

import config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


PROMPT_TRIAJE_TEMPLATE = """
Eres el clasificador de rutas de un asistente interno de Alicorp.
Elige una sola decisión. No respondas la consulta ni expliques tu razonamiento.

Políticas disponibles:
{lista_politicas}

Decisiones y reglas:
- SALUDO: interacción social, saludo, agradecimiento o despedida sin una
  necesidad de información. Si expresa intención de consultar pero no precisa
  el asunto, no es SALUDO: es PEDIR_MAS_INFORMACION.
- FUERA_DE_AMBITO: asunto sin relación con Alicorp, sus políticas o el trabajo
  interno; por ejemplo información general o una solicitud creativa, recreativa
  o cotidiana.
- PEDIR_MAS_INFORMACION: parece una consulta interna, pero es tan vaga o
  incompleta que no permite identificar la información solicitada. Indica en
  campos_faltantes qué debe precisar.
  REGLA OBLIGATORIA: Si el usuario menciona "el formato", "los requisitos", "el trámite",
  "el procedimiento", "el formulario", "las vacaciones" o "la política" de forma genérica
  (por ejemplo: "Quiero descargar el formato oficial" o "Pásame los requisitos mínimos")
  sin especificar a qué beneficio, trámite, documento o política se refiere, debes clasificarlo
  SIEMPRE como PEDIR_MAS_INFORMACION. No intentes buscar en el RAG un "formato general" inexistente.
  IMPORTANTE: Si la pregunta ya es una consulta informativa muy concreta (p. ej., solicita un porcentaje, un monto o límite específico de un beneficio como el plan de salud EPS o viáticos), NO debe ir a PEDIR_MAS_INFORMACION, sino a CONSULTAR_RAG, incluso si el término (como EPS) no está en la lista de políticas disponibles.
- ABRIR_TICKET: pide que el sistema inicie una gestión real, como registrar una
  denuncia, crear un ticket, pedir acceso o tramitar una autorización.
  Si solo pregunta cómo, dónde, ante quién o por qué canal se hace la gestión,
  usa CONSULTAR_RAG. Si busca saltarse una regla o conseguir una excepción para
  hacerlo, usa ABRIR_TICKET.
- LISTAR_POLITICAS: el usuario solicita conocer el catálogo completo, la
  cantidad total, el universo de información, los documentos disponibles o
  todas las políticas sobre las que el asistente puede responder.
  Clasifica por la intención semántica, no por coincidencias exactas de palabras.
  Incluye variantes ortográficas y expresiones equivalentes.
  NO uses LISTAR_POLITICAS cuando el usuario pregunte por el contenido de una
  política específica; en ese caso usa CONSULTAR_RAG.
  Ejemplos: "¿Cuántas políticas conoces?" → LISTAR_POLITICAS;
  "¿Sobre qué documentos puedes responder?" → LISTAR_POLITICAS;
  "¿Cuál es todo tu universo de información?" → LISTAR_POLITICAS;
  "¿Qué dice la política de regalos?" → CONSULTAR_RAG.
- CONSULTAR_RAG: pregunta informativa concreta sobre Alicorp, sus políticas,
  reglas, beneficios, compromisos, prohibiciones, requisitos o procedimientos.

Preguntar cómo se hace una gestión es CONSULTAR_RAG; pedir que la ejecutes es
ABRIR_TICKET. Una consulta corporativa concreta va a CONSULTAR_RAG aunque no
sepas si el PDF contiene la respuesta: el RAG comprobará el respaldo.
Urgencia por decisión: ABRIR_TICKET es ALTA, PEDIR_MAS_INFORMACION es MEDIA, y todas las demás decisiones (SALUDO, FUERA_DE_AMBITO, LISTAR_POLITICAS, CONSULTAR_RAG) son obligatoriamente BAJA.
campos_faltantes debe estar vacío salvo en PEDIR_MAS_INFORMACION.

Ejemplos importantes:
- "Quiero ver los requisitos mínimos" -> PEDIR_MAS_INFORMACION porque no
  identifica los requisitos de qué trámite, beneficio o política.
  Campos faltantes sugeridos: ["el trámite, beneficio o política de interés"].
- "¿De qué trata la política corporativa?" -> PEDIR_MAS_INFORMACION porque no
  identifica cuál política corporativa.
  Campos faltantes sugeridos: ["el nombre de la política específica"].
- "Tengo una consulta rápida sobre las vacaciones" -> PEDIR_MAS_INFORMACION porque no
  formula una pregunta concreta.
  Campos faltantes sugeridos: ["la duda o consulta específica sobre vacaciones"].
- "Necesito descargar el formato oficial" -> PEDIR_MAS_INFORMACION porque no
  identifica el formato, el trámite ni la política correspondiente.
  Campos faltantes sugeridos: ["el formato o trámite de interés"].
- "¿Cuál es el porcentaje de cobertura del plan de salud EPS para mis cónyuges?" ->
  CONSULTAR_RAG porque es una consulta concreta de información de beneficios (EPS),
  aunque "EPS" no figure en la lista de políticas disponibles.
- "¿Ante qué área pido una autorización para saltarme una regla de la política de ciberseguridad?" ->
  ABRIR_TICKET porque solicita u orienta a obtener una autorización/excepción para omitir o evadir una regla de seguridad.
- "¿Cuáles son los requisitos para aceptar un regalo de un proveedor?" ->
  CONSULTAR_RAG porque identifica claramente el tema y solicita información.
- "¿Cómo se debe registrar una denuncia por un intento de soborno?" ->
  CONSULTAR_RAG porque pide información sobre el procedimiento, no que el
  sistema ejecute la denuncia.
- "¿Dónde puedo reportar un intento de soborno?" -> CONSULTAR_RAG porque solo
  solicita conocer el canal correspondiente.
- "Registra una denuncia por un intento de soborno" -> ABRIR_TICKET porque pide
  iniciar una gestión real.
- "Abre un ticket para reportar este incidente" -> ABRIR_TICKET porque solicita
  expresamente que el sistema cree la gestión.
- "¿Qué políticas crees que son más importantes?" -> PEDIR_MAS_INFORMACION porque
  pide una opinión subjetiva y no formula una pregunta concreta sobre información específica.
  Indica en campos_faltantes que precise qué política o tema le interesa consultar.
- "¿Cuál es la diferencia entre todas las políticas?" -> PEDIR_MAS_INFORMACION porque
  es demasiado amplia y no identifica un tema concreto.
- "¿Crees que Alicorp cumple bien con sus políticas?" -> PEDIR_MAS_INFORMACION porque
  solicita una valoración u opinión que el agente no puede emitir.
Reglas para determinar usa_historial:

El campo usa_historial no indica si la consulta es completa o incompleta.
Indica si el significado del mensaje depende de algo dicho anteriormente.

Evalúa la dependencia por la intención comunicativa, no mediante coincidencias
exactas de palabras. Tolera mayúsculas, espacios, alargamientos, errores
ortográficos menores y formas diferentes de expresar la misma intención.

usa_historial=true cuando el mensaje sea una continuación que necesite recuperar
información anterior, incluyendo:

- Referencias a elementos anteriores mediante expresiones como eso, lo anterior,
  ese punto, ese caso, esa política, dicho requisito o el trámite.
- Preguntas de aclaración sobre algo expresado anteriormente, aunque repitan el
  término: preguntar a qué se refiere, qué significa, por qué se mencionó o
  solicitar que se explique mejor un concepto anterior.
- Correcciones o reparaciones del mensaje anterior: indicar que quiso decir otra
  palabra, que se expresó mal, que se refería a otro término o corregir una
  expresión previa.
- Continuaciones elípticas que omiten el tema principal: preguntar por los pasos,
  el monto, el límite, los requisitos o las consecuencias sin volver a identificar
  la política o situación.
- Respuestas breves que completan información solicitada anteriormente.

usa_historial=false cuando el mensaje:

- Sea un saludo, agradecimiento, despedida o interacción social.
- Plantee una consulta completamente independiente.
- Identifique por sí mismo la política, situación y dato solicitado.
- Cambie claramente a un tema nuevo.

REGLA DE PRIORIDAD:
Antes de clasificar un mensaje incompleto como PEDIR_MAS_INFORMACION, comprueba
si su falta de contexto se debe a una referencia, continuación, aclaración o
corrección de algo anterior. En ese caso:

- decision puede seguir siendo PEDIR_MAS_INFORMACION.
- usa_historial debe ser true.

Main.py utilizará la memoria para completar el mensaje y después volverá a
ejecutar el triaje sobre la pregunta autónoma.
Ejemplos para usa_historial:

- "¿A qué te refieres con momento apropiado?"
  -> decision=PEDIR_MAS_INFORMACION, usa_historial=true

- "Perdón, quise decir momento apropiado"
  -> decision=PEDIR_MAS_INFORMACION, usa_historial=true

- "¿Y cuáles son los pasos?"
  -> decision=PEDIR_MAS_INFORMACION, usa_historial=true

- "¿Qué significa momento apropiado en la Política Corporativa de Regalos?"
  -> decision=CONSULTAR_RAG, usa_historial=false

Los ejemplos representan intenciones comunicativas; no deben tratarse como
comparaciones literales de texto.
Genera exclusivamente un objeto JSON con esta estructura:
{{
  "decision": "CONSULTAR_RAG | LISTAR_POLITICAS | PEDIR_MAS_INFORMACION | ABRIR_TICKET | FUERA_DE_AMBITO | SALUDO",
  "urgencia": "BAJA | MEDIA | ALTA",
  "campos_faltantes": [],
  "usa_historial": false
}}
"""


class TriajeOut(BaseModel):
    """Estructura de la respuesta que debe devolver el LLM del triaje."""

    decision: Literal[
        "CONSULTAR_RAG",
        "LISTAR_POLITICAS",
        "PEDIR_MAS_INFORMACION",
        "ABRIR_TICKET",
        "FUERA_DE_AMBITO",
        "SALUDO",
    ]

    urgencia: Literal["BAJA", "MEDIA", "ALTA"]

    campos_faltantes: List[str] = Field(default_factory=list)

    usa_historial: bool = Field(
        ...,
        description=(
            "Indica si el mensaje necesita información de turnos anteriores "
            "para poder entenderse correctamente."
        ),
    )

def construir_prompt_triaje(lista_politicas: str) -> str:
    """Inserta la lista de políticas en el template del prompt y lo devuelve listo."""
    return PROMPT_TRIAJE_TEMPLATE.format(lista_politicas=lista_politicas)


def construir_cadena_triaje(llm: BaseChatModel):
    """
    Configura el LLM para devolver respuestas en formato JSON estructurado (TriajeOut).
    Cohere requiere json_schema; otros proveedores usan el modo por defecto.
    """
    print(f"[TRIAJE-INIT] Proveedor activo: {config.LLM_PROVIDER}")

    if config.LLM_PROVIDER == "cohere":
        return llm.with_structured_output(TriajeOut, method="json_schema")

    return llm.with_structured_output(TriajeOut)


def sub_triaje_extraer_json(contenido) -> Dict:
    """Extrae el JSON del texto cuando el LLM no devolvió un objeto Pydantic."""
    if not isinstance(contenido, str):
        raise TypeError("La respuesta del LLM no contiene texto")

    texto  = contenido.strip()
    inicio = texto.find("{")
    fin    = texto.rfind("}")

    if inicio == -1 or fin < inicio:
        raise ValueError("La respuesta del LLM no contiene un objeto JSON válido")

    return json.loads(texto[inicio : fin + 1])


def ejecutar_triaje(mensaje: str, cadena_triaje, prompt_triaje: str) -> Dict:
    """
    Envía el mensaje al LLM de triaje y devuelve la decisión como diccionario.
    Aplica reglas fijas para evitar combinaciones inválidas (urgencia ALTA en un SALUDO, etc.).
    """
    print(f"[TRIAJE] Clasificando con '{config.LLM_PROVIDER}'...")
    inicio = time.perf_counter()

    try:
        salida = cadena_triaje.invoke(
            [
                SystemMessage(content=prompt_triaje.strip()),
                HumanMessage(content=mensaje.strip()),
            ]
        )

        if isinstance(salida, TriajeOut):
            resultado = salida.model_dump()
        elif isinstance(salida, dict):
            resultado = TriajeOut.model_validate(salida).model_dump()
        else:
            contenido = getattr(salida, "content", salida)
            resultado = TriajeOut.model_validate(
                sub_triaje_extraer_json(contenido)
            ).model_dump()

    except Exception as error:
        print(f"[TRIAJE] Error del LLM: {type(error).__name__}: {error!r}")
        raise RuntimeError("El LLM de triaje no respondió correctamente") from error

    duracion = time.perf_counter() - inicio
    print(f"[TRIAJE] Respondió en {duracion:.2f}s")

    # Forzar niveles de urgencia según el tipo de decisión
    if resultado["decision"] == "ABRIR_TICKET":
        resultado["urgencia"] = "ALTA"
    elif resultado["decision"] == "PEDIR_MAS_INFORMACION":
        resultado["urgencia"] = "MEDIA"
    else:
        resultado["urgencia"] = "BAJA"

    # Solo PEDIR_MAS_INFORMACION puede tener campos_faltantes
    if resultado["decision"] != "PEDIR_MAS_INFORMACION":
        resultado["campos_faltantes"] = []
    
    # Las interacciones sociales y listados nunca necesitan recuperar el tema anterior
    if resultado["decision"] in {"SALUDO", "LISTAR_POLITICAS"}:
        resultado["usa_historial"] = False

    print(
        f"[TRIAJE] decisión={resultado['decision']} | "
        f"urgencia={resultado['urgencia']} | "
        f"usa_historial={resultado['usa_historial']}"
    )
    return resultado
