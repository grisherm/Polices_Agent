# Suite de pruebas del agente Alicorp con control de carga.
# Ejecuta los casos de forma secuencial contra /api/chat para validar la acción
# y conservar la respuesta completa que recibiría el usuario.
# Incluye pausas y descansos entre solicitudes.
# Admite filtros por grupo (triaje / rag) y por rango de número de caso.
#
# Ejemplos de uso:
#   python test_agente_ligero.py
#   python test_agente_ligero.py --grupo triaje
#   python test_agente_ligero.py --grupo rag
#   python test_agente_ligero.py --desde 1 --hasta 10
#   python test_agente_ligero.py --modo normal --pausa 5

import argparse
import json
import socket
import time
import unicodedata
import urllib.error
import urllib.request
from typing import Any

BASE_URL     = "http://localhost:8000"
RUTA_REPORTE = "reporte_pruebas.md"

VERDE   = "\033[92m"
ROJO    = "\033[91m"
AMARILLO = "\033[93m"
AZUL    = "\033[94m"
RESET   = "\033[0m"
NEGRITA = "\033[1m"


CASOS_DE_PRUEBA = [

    # SALUDOS
    {"pregunta": "Hola, ¿cómo estás?",                  "esperado": "SALUDO",    "categoria": "Triaje -> Saludo",              "grupo": "triaje"},
    {"pregunta": "Buenas tardes, necesito ayuda",         "esperado": "PEDIR_INFO","categoria": "Triaje -> Pedir Información",   "grupo": "triaje"},
    {"pregunta": "Buen día a todos en el soporte",        "esperado": "SALUDO",    "categoria": "Triaje -> Saludo",              "grupo": "triaje"},
    {"pregunta": "Muchas gracias por tu tiempo",          "esperado": "SALUDO",    "categoria": "Triaje -> Saludo",              "grupo": "triaje"},
    {"pregunta": "Adiós, nos vemos luego",                "esperado": "SALUDO",    "categoria": "Triaje -> Saludo",              "grupo": "triaje"},

    # FUERA DE ÁMBITO
    {"pregunta": "¿Quién ganó el mundial de fútbol de 2022?",                         "esperado": "FUERA_DE_AMBITO", "categoria": "Triaje -> Fuera de Ámbito", "grupo": "triaje"},
    {"pregunta": "Dame una receta para preparar ceviche peruano paso a paso",         "esperado": "FUERA_DE_AMBITO", "categoria": "Triaje -> Fuera de Ámbito", "grupo": "triaje"},
    {"pregunta": "¿Cuál es la distancia entre la Tierra y la Luna?",                  "esperado": "FUERA_DE_AMBITO", "categoria": "Triaje -> Fuera de Ámbito", "grupo": "triaje"},
    {"pregunta": "Escribe un poema corto sobre el mar y el viento",                   "esperado": "FUERA_DE_AMBITO", "categoria": "Triaje -> Fuera de Ámbito", "grupo": "triaje"},
    {"pregunta": "¿Cómo va a estar el clima mañana en Lima?",                         "esperado": "FUERA_DE_AMBITO", "categoria": "Triaje -> Fuera de Ámbito", "grupo": "triaje"},

    # PEDIR MÁS INFORMACIÓN
    {"pregunta": "Quiero ver los requisitos mínimos",                     "esperado": "PEDIR_INFO", "categoria": "Triaje -> Pedir Información", "grupo": "triaje"},
    {"pregunta": "¿De qué trata la política corporativa?",                "esperado": "PEDIR_INFO", "categoria": "Triaje -> Pedir Información", "grupo": "triaje"},
    {"pregunta": "Tengo una consulta rápida sobre las vacaciones",        "esperado": "PEDIR_INFO", "categoria": "Triaje -> Pedir Información", "grupo": "triaje"},
    {"pregunta": "Necesito descargar el formato oficial",                  "esperado": "PEDIR_INFO", "categoria": "Triaje -> Pedir Información", "grupo": "triaje"},
    {"pregunta": "¿Me podrías detallar el procedimiento administrativo?", "esperado": "PEDIR_INFO", "categoria": "Triaje -> Pedir Información", "grupo": "triaje"},

    # ABRIR TICKET
    {"pregunta": "Necesito una excepción para contratar a mi hermano en mi mismo departamento",                           "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Quiero reportar un caso grave de fraude y desvío de fondos que descubrí",                               "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Solicito una autorización especial para aceptar un regalo de $600 de un proveedor clave",               "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Quiero denunciar acoso laboral y malos tratos por parte de mi gerente de área",                         "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Por favor, libérenme un acceso especial permanente al servidor principal de base de datos de producción","esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},

    # RAG EXITOSO
    {"pregunta": "¿Cuáles son los compromisos éticos de Alicorp según su guía?",                                    "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Qué es un regalo o atención según la política corporativa de regalos?",                          "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Puedo recibir dinero en efectivo de un proveedor como obsequio corporativo?",                    "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Cómo define Alicorp el concepto de fraude en su política corporativa?",                          "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Cuál es el compromiso de Alicorp frente a la defensa de los derechos humanos?",                  "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Qué medidas y pautas de seguridad de la información debemos seguir?",                            "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Cómo define Alicorp los lineamientos de su marketing responsable?",                              "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿A quiénes aplican las restricciones en la política de sanciones económicas de Alicorp?",         "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Qué debemos hacer en caso de detectar o sospechar un conflicto de interés?",                     "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},
    {"pregunta": "¿Qué principios establece la política para proteger la información de clientes y colaboradores?", "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Triaje -> RAG -> Verificador -> Exitoso", "grupo": "rag"},

    # RAG SIN INFORMACIÓN
    {"pregunta": "¿Cuál es el monto máximo permitido para los viáticos de viaje de trabajo nacional?",  "esperado": "SIN_INFORMACION", "tipo_respuesta": "no_se", "categoria": "Triaje -> RAG -> Verificador -> No sé", "grupo": "rag"},
    {"pregunta": "¿Cuántos días hábiles de licencia por mudanza me corresponden por ley en la empresa?","esperado": "SIN_INFORMACION", "tipo_respuesta": "no_se", "categoria": "Triaje -> RAG -> Verificador -> No sé", "grupo": "rag"},
    {"pregunta": "¿Cómo puedo realizar la solicitud para el préstamo corporativo de vivienda?",          "esperado": "SIN_INFORMACION", "tipo_respuesta": "no_se", "categoria": "Triaje -> RAG -> Verificador -> No sé", "grupo": "rag"},
    {"pregunta": "¿Cuál es el porcentaje de cobertura del plan de salud EPS para mis cónyuges?",        "esperado": "SIN_INFORMACION", "tipo_respuesta": "no_se", "categoria": "Triaje -> RAG -> Verificador -> No sé", "grupo": "rag"},
    {"pregunta": "¿Cómo puedo pedir el reembolso por estudios de maestría o diplomado externo?",        "esperado": "SIN_INFORMACION", "tipo_respuesta": "no_se", "categoria": "Triaje -> RAG -> Verificador -> No sé", "grupo": "rag"},

    # TICKETS DIRECTOS DESDE TRIAJE
    {"pregunta": "¿Puedo solicitar una excepción para recibir un regalo de un proveedor que excede los montos?",           "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Quiero solicitar la aprobación de un viático extraordinario no contemplado en el viaje",                 "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Necesito pedir la liberación y desbloqueo de mi laptop personal bloqueada por seguridad de la información","esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "¿Ante qué área pido una autorización para saltarme una regla de la política de ciberseguridad?",         "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},
    {"pregunta": "Quiero abrir un ticket de soporte técnico para el canal de denuncias de ética",                          "esperado": "ABRIR_TICKET", "categoria": "Triaje -> Abrir Ticket", "grupo": "triaje"},

    # PRUEBAS DE MEMORIA DE CORTO PLAZO
    {"pregunta": "¿Cuál es el límite permitido para recibir un regalo de un proveedor?", "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Memoria -> Sesión Regalos -> Turno 1", "grupo": "rag", "sesion": "regalos"},
    {"pregunta": "¿Y si se trata de dinero en efectivo?",                                "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Memoria -> Sesión Regalos -> Turno 2", "grupo": "rag", "sesion": "regalos"},
    {"pregunta": "¿Qué operaciones prohíbe la política de sanciones económicas de Alicorp?", "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Memoria -> Sesión Sanciones -> Turno 1", "grupo": "rag", "sesion": "sanciones"},
    {"pregunta": "¿Existen excepciones para estas prohibiciones?",                       "esperado": "AUTO_RESOLVER", "tipo_respuesta": "rag_exitoso", "categoria": "Memoria -> Sesión Sanciones -> Turno 2", "grupo": "rag", "sesion": "sanciones"},
]


MODOS = {
    # Conserva pausas amplias para respetar los límites de la API
    "ligero": {
        "pausa": 10.0,
        "descanso_cada": 5,
        "descanso": 60.0,
        "extra_rag": 15.0,
    },
    # Equilibrio entre tiempo y temperatura
    "normal": {
        "pausa": 4.0,
        "descanso_cada": 10,
        "descanso": 30.0,
        "extra_rag": 5.0,
    },
    # Recomendable solo si el LLM está en la nube y el equipo no se recalienta
    "rapido": {
        "pausa": 1.0,
        "descanso_cada": 20,
        "descanso": 10.0,
        "extra_rag": 0.0,
    },
}


def verificar_api(timeout: int = 10) -> bool:
    """Comprueba que la API esté disponible antes de iniciar las pruebas."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
            return datos.get("status") == "ok"
    except Exception:
        return False


def post_chat(pregunta: str, thread_id: str, timeout: int, endpoint: str = "/api/chat") -> dict:
    """Envía una consulta al endpoint indicado y devuelve la respuesta como dict."""
    payload = json.dumps(
        {"pregunta": pregunta, "thread_id": thread_id},
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        try:
            detalle = error.read().decode("utf-8")
        except Exception:
            detalle = f"HTTP Error {error.code}"
        return {"error": detalle, "status": error.code}

    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            return {"error": f"Timeout del cliente después de {timeout} segundos", "status": "TIMEOUT"}
        return {"error": str(error), "status": "CONEXION"}

    except (TimeoutError, socket.timeout):
        return {"error": f"Timeout del cliente después de {timeout} segundos", "status": "TIMEOUT"}

    except Exception as error:
        return {"error": str(error), "status": "CLIENTE"}


def normalizar_respuesta(texto: str) -> str:
    """Convierte a minúsculas y elimina tildes, espacios extra y puntuación final."""
    # NFKD separa letras de sus tildes para poder filtrarlas
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )
    return " ".join(sin_tildes.strip().lower().rstrip(".!? ").split())


def validar_contenido_respuesta(caso: dict, respuesta_api: dict) -> tuple:
    """
    Valida el contenido de la respuesta según el tipo esperado.
    - rag_exitoso: debe tener respuesta útil y al menos una citación.
    - no_se: debe devolver exactamente 'No lo sé.' sin citaciones.
    - sin tipo: no necesita validación adicional.
    """
    if "error" in respuesta_api:
        return False, f"La API devolvió un error: {respuesta_api['error']}"

    tipo_respuesta = caso.get("tipo_respuesta")

    if not tipo_respuesta:
        return True, "No requiere validación adicional de RAG"

    respuesta            = str(respuesta_api.get("respuesta", ""))
    respuesta_normalizada = normalizar_respuesta(respuesta)
    citaciones           = respuesta_api.get("citaciones") or []

    if tipo_respuesta == "no_se":
        if respuesta_normalizada != "no lo se":
            return False, f"Se esperaba exactamente 'No lo sé.', pero se obtuvo: {respuesta}"
        if citaciones:
            return False, "Una respuesta 'No lo sé.' no debe incluir citaciones."
        return True, "Respuesta negativa normalizada correctamente"

    if tipo_respuesta == "rag_exitoso":
        if respuesta_normalizada in {"", "no lo se"}:
            return False, f"El RAG debía responder con información, pero devolvió: {respuesta}"
        if len(respuesta_normalizada) < 20:
            return False, "La respuesta del RAG es demasiado corta para considerarse útil."
        if not citaciones:
            return False, "El RAG respondió, pero no devolvió ninguna citación."
        return True, f"Respuesta respaldada por {len(citaciones)} citación(es)"

    return False, f"Tipo de respuesta desconocido en el test: {tipo_respuesta}"


def seleccionar_casos(grupo: str, desde: int | None, hasta: int | None) -> list:
    """
    Filtra los casos por grupo y rango de número.
    Los parámetros desde y hasta son inclusivos y usan el número original del caso.
    """
    seleccionados = list(enumerate(CASOS_DE_PRUEBA, start=1))

    if grupo != "todos":
        seleccionados = [(n, c) for n, c in seleccionados if c["grupo"] == grupo]

    if desde is not None:
        seleccionados = [(n, c) for n, c in seleccionados if n >= desde]

    if hasta is not None:
        seleccionados = [(n, c) for n, c in seleccionados if n <= hasta]

    return seleccionados


def escribir_reporte_md(exitosos: int, fallidos: int, detalles: list, interrumpido: bool = False) -> None:
    """Guarda el reporte en Markdown. Si la suite fue interrumpida, lo indica al inicio."""
    total     = len(detalles)
    tasa_exito = (exitosos / total * 100) if total else 0.0

    with open(RUTA_REPORTE, "w", encoding="utf-8") as archivo:
        archivo.write("# Reporte de Pruebas Automatizadas del Agente Alicorp\n\n")

        if interrumpido:
            archivo.write(
                "> Ejecución interrumpida manualmente. "
                "Este reporte contiene únicamente los casos completados.\n\n"
            )

        archivo.write("## Resumen Ejecutivo\n\n")
        archivo.write("| Métrica | Valor |\n")
        archivo.write("| :--- | :--- |\n")
        archivo.write(f"| **Casos ejecutados** | {total} |\n")
        archivo.write(f"| **Pasados** | {exitosos} |\n")
        archivo.write(f"| **Fallidos** | {fallidos} |\n")
        archivo.write(f"| **Tasa de éxito** | **{tasa_exito:.1f}%** |\n\n")

        archivo.write("## Detalle de los Casos de Prueba\n\n")
        archivo.write(
            "| # | Categoría | Pregunta | Respuesta del Agente | "
            "Acción Esperada | Acción Obtenida | Validación | Duración | Estado |\n"
        )
        archivo.write(
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        )

        for detalle in detalles:
            estado    = "🟢 PASS" if detalle["resultado"] == "PASS" else "🔴 FAIL"
            pregunta  = detalle["pregunta"].replace("|", "\\|")
            validacion = detalle["validacion"].replace("|", "\\|")
            respuesta_tabla = (
                str(detalle["respuesta"])
                .replace("|", "\\|")
                .replace("\r\n", "<br>")
                .replace("\n", "<br>")
            )

            archivo.write(
                f"| {detalle['num']} | {detalle['categoria']} | {pregunta} | "
                f"{respuesta_tabla} | "
                f"`{detalle['esperado']}` | `{detalle['obtenido']}` | "
                f"{validacion} | {detalle['duracion']} | **{estado}** |\n"
            )

        archivo.write("\n\n## Respuestas del Agente\n\n")

        for detalle in detalles:
            respuesta = str(detalle["respuesta"]).replace("\n", "\n> ")
            archivo.write(f"### Caso {detalle['num']}: {detalle['categoria']}\n\n")
            archivo.write(f"**Pregunta:** \"{detalle['pregunta']}\"\n\n")
            archivo.write(f"**Acción obtenida:** `{detalle['obtenido']}`\n\n")
            archivo.write(f"**Respuesta obtenida:**\n> {respuesta}\n\n")
            archivo.write(f"**Validación:** {detalle['validacion']}\n\n")

            citaciones = detalle.get("citaciones") or []
            if citaciones:
                archivo.write("**Citaciones devueltas:**\n\n")
                for numero_cita, cita in enumerate(citaciones, start=1):
                    fuente = str(cita.get("fuente") or "Fuente no indicada")
                    pagina = cita.get("pagina")
                    texto  = str(cita.get("texto") or "").strip().replace("\n", " ")
                    ubicacion = f", página {pagina}" if pagina is not None else ""
                    archivo.write(
                        f"{numero_cita}. **{fuente}{ubicacion}:** {texto}\n"
                    )
                archivo.write("\n")

            archivo.write("---\n\n")


def esperar(segundos: float, mensaje: str) -> None:
    """Hace una pausa visible en consola. No hace nada si el valor es cero o negativo."""
    if segundos <= 0:
        return
    print(f"{AZUL}{mensaje} ({segundos:.0f} s)...{RESET}")
    time.sleep(segundos)


def ejecutar_pruebas(args: argparse.Namespace) -> None:
    """Corre la suite completa con pausas, guarda el reporte después de cada caso."""
    configuracion = MODOS[args.modo].copy()
    suite_timestamp = int(time.time())

    # El triaje es una inferencia corta; el RAG puede encadenar triaje, generación y verificación
    timeout_triaje = args.timeout if args.timeout is not None else 75
    timeout_rag    = args.timeout if args.timeout is not None else 360

    if args.pausa is not None:
        configuracion["pausa"] = max(0.0, args.pausa)

    if args.descanso_cada is not None:
        configuracion["descanso_cada"] = max(0, args.descanso_cada)

    if args.descanso is not None:
        configuracion["descanso"] = max(0.0, args.descanso)

    if args.extra_rag is not None:
        configuracion["extra_rag"] = max(0.0, args.extra_rag)

    casos = seleccionar_casos(args.grupo, args.desde, args.hasta)

    if not casos:
        print(f"{ROJO}No hay casos que coincidan con los filtros indicados.{RESET}")
        return

    if not verificar_api():
        print(
            f"{ROJO}La API no está lista en {BASE_URL}. "
            f"Verifica que Main.py esté ejecutándose y que /health responda 'ok'."
            f"{RESET}"
        )
        return

    print(f"\n{NEGRITA}{AZUL}{'=' * 72}")
    print("  INICIANDO SUITE DE PRUEBAS CON CONTROL DE CARGA")
    print(f"{'=' * 72}{RESET}")
    print(f"  Modo                 : {args.modo}")
    print(f"  Grupo                : {args.grupo}")
    print(f"  Casos seleccionados  : {len(casos)}")
    print(f"  Pausa entre casos    : {configuracion['pausa']} s")
    print(f"  Descanso cada        : {configuracion['descanso_cada']} casos")
    print(f"  Duración descanso    : {configuracion['descanso']} s")
    print(f"  Pausa extra por RAG  : {configuracion['extra_rag']} s")
    print(f"  Timeout triaje/RAG   : {timeout_triaje}/{timeout_rag} s")
    print(f"{'=' * 72}{RESET}")

    detalles: list[dict[str, Any]] = []
    exitosos   = 0
    fallidos   = 0
    completados = 0

    try:
        for posicion, (numero_original, caso) in enumerate(casos, start=1):
            pregunta  = caso["pregunta"]
            esperado  = caso["esperado"]
            categoria = caso["categoria"]
            grupo     = caso["grupo"]

            timeout_solicitud = timeout_rag if grupo == "rag" else timeout_triaje

            # Todos los casos usan /api/chat. El endpoint /api/triaje solo devuelve
            # una clasificación (por ejemplo, "Clasificación de triaje: SALUDO")
            # y no la respuesta final que recibiría el usuario.
            endpoint = "/api/chat"
            
            if "sesion" in caso:
                thread_id = f"suite_test_memoria_{caso['sesion']}_{suite_timestamp}"
            else:
                thread_id = f"suite_test_{numero_original:03d}_{int(time.time())}"

            print(
                f"\n[{posicion}/{len(casos)} | caso original {numero_original}] "
                f"{AMARILLO}{categoria}{RESET}\n"
                f"Pregunta: '{pregunta}'"
            )

            inicio       = time.time()
            respuesta_api = post_chat(
                pregunta=pregunta,
                thread_id=thread_id,
                timeout=timeout_solicitud,
                endpoint=endpoint,
            )
            duracion = time.time() - inicio

            accion_real = respuesta_api.get("accion_final", "ERROR")

            if "error" in respuesta_api:
                accion_real = f"ERROR ({respuesta_api.get('status', 500)})"

            accion_correcta   = accion_real == esperado
            contenido_correcto, detalle_contenido = validar_contenido_respuesta(caso, respuesta_api)
            correcto          = accion_correcta and contenido_correcto

            if correcto:
                exitosos += 1
                print(
                    f"  {VERDE}[PASS]{RESET} "
                    f"Acción: {accion_real} | {duracion:.2f}s\n"
                    f"  Validación: {detalle_contenido}"
                )
            else:
                fallidos += 1
                print(
                    f"  {ROJO}[FAIL]{RESET} "
                    f"Esperado: {esperado} | Obtenido: {accion_real} | "
                    f"{duracion:.2f}s\n"
                    f"  Validación: {detalle_contenido}"
                )

            respuesta_agente = str(
                respuesta_api.get("respuesta", respuesta_api.get("error", "N/A"))
            )
            print(f"  {AZUL}Respuesta del agente:{RESET} {respuesta_agente}")

            citaciones_respuesta = respuesta_api.get("citaciones") or []
            if citaciones_respuesta:
                print(f"  {AZUL}Citaciones devueltas:{RESET} {len(citaciones_respuesta)}")

            detalles.append({
                "num":       numero_original,
                "categoria": categoria,
                "pregunta":  pregunta,
                "esperado":  esperado,
                "obtenido":  accion_real,
                "resultado": "PASS" if correcto else "FAIL",
                "validacion": detalle_contenido,
                "duracion":  f"{duracion:.2f}s",
                "respuesta": respuesta_agente,
                "citaciones": citaciones_respuesta,
            })

            completados += 1

            # Guardado incremental para no perder resultados si se interrumpe
            escribir_reporte_md(exitosos=exitosos, fallidos=fallidos, detalles=detalles)

            es_ultimo = posicion == len(casos)
            if es_ultimo:
                continue

            if grupo == "rag":
                esperar(configuracion["extra_rag"], "Pausa adicional después del RAG")

            esperar(configuracion["pausa"], "Pausa entre pruebas")

            descanso_cada = configuracion["descanso_cada"]
            if descanso_cada > 0 and completados % descanso_cada == 0:
                esperar(configuracion["descanso"], "Descanso prolongado")

    except KeyboardInterrupt:
        print(f"\n{AMARILLO}Ejecución detenida con Ctrl+C. Se guardará el reporte parcial.{RESET}")
        escribir_reporte_md(exitosos=exitosos, fallidos=fallidos, detalles=detalles, interrumpido=True)
        return

    total = len(detalles)
    tasa  = (exitosos / total * 100) if total else 0.0

    print(f"\n{NEGRITA}{AZUL}{'=' * 72}")
    print("  PRUEBAS COMPLETADAS")
    print(f"  Ejecutadas    : {total}")
    print(f"  Aprobadas     : {VERDE}{exitosos}{RESET}")
    print(f"  Fallidas      : {ROJO}{fallidos}{RESET}")
    print(f"  Tasa de éxito : {NEGRITA}{tasa:.1f}%{RESET}")
    print(f"  Reporte       : {RUTA_REPORTE}")
    print(f"{'=' * 72}{RESET}\n")


def construir_argumentos() -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta las pruebas del agente Alicorp con pausas y descansos "
            "para reducir el uso sostenido de CPU."
        )
    )

    parser.add_argument(
        "--modo",
        choices=MODOS.keys(),
        default="ligero",
        help="Perfil de carga. Por defecto: ligero.",
    )
    parser.add_argument(
        "--grupo",
        choices=["todos", "triaje", "rag"],
        default="todos",
        help="Ejecuta todos los casos, solo triaje o solo RAG.",
    )
    parser.add_argument(
        "--desde",
        type=int,
        default=None,
        help="Número original del primer caso que se ejecutará.",
    )
    parser.add_argument(
        "--hasta",
        type=int,
        default=None,
        help="Número original del último caso que se ejecutará.",
    )
    parser.add_argument(
        "--pausa",
        type=float,
        default=None,
        help="Sobrescribe los segundos de pausa entre pruebas.",
    )
    parser.add_argument(
        "--descanso-cada",
        type=int,
        default=None,
        help="Sobrescribe cada cuántos casos se realiza un descanso largo.",
    )
    parser.add_argument(
        "--descanso",
        type=float,
        default=None,
        help="Sobrescribe la duración del descanso largo en segundos.",
    )
    parser.add_argument(
        "--extra-rag",
        type=float,
        default=None,
        help="Pausa adicional después de cada caso RAG.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Sobrescribe el timeout de todas las solicitudes. Por defecto: 75 s triaje / 360 s RAG.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    ejecutar_pruebas(construir_argumentos())
