"""Envía los tickets del formulario por correo."""

from datetime import datetime, timezone
from email.message import EmailMessage
import smtplib
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

import config


class TicketRequest(BaseModel):
    thread_id: str = "default"
    nombre: str = ""
    correo: str = ""
    area: str = ""
    categoria: str = "Consulta corporativa"
    urgencia: Literal["BAJA", "MEDIA", "ALTA"] = "ALTA"
    pregunta_original: str = Field(min_length=3, max_length=1800)
    detalle: str = Field(min_length=10, max_length=5000)


class TicketResponse(BaseModel):
    ticket_id: str
    estado: str
    mensaje: str


def validar_ticket(ticket: TicketRequest):
    """Comprueba los datos básicos del formulario."""
    if not ticket.nombre.strip() or not ticket.area.strip():
        raise ValueError("Completa tu nombre y área.")

    correo = ticket.correo.strip()
    if "@" not in correo or "." not in correo.split("@")[-1]:
        raise ValueError("Escribe un correo válido.")


def crear_codigo_ticket() -> str:
    fecha = datetime.now(timezone.utc).strftime("%Y%m%d")
    codigo = uuid4().hex[:8].upper()
    return f"ALC-{fecha}-{codigo}"


def enviar_ticket_por_correo(ticket: TicketRequest) -> TicketResponse:
    """Crea el mensaje y lo envía al correo configurado."""
    if not config.SMTP_USER or not config.SMTP_APP_PASSWORD or not config.TICKET_DESTINO:
        raise RuntimeError("Falta completar la configuración SMTP.")

    validar_ticket(ticket)
    ticket_id = crear_codigo_ticket()

    contenido = f"""
NUEVO TICKET DE ALICORP IA

Código: {ticket_id}
Categoría: {ticket.categoria}
Urgencia: {ticket.urgencia}
Conversación: {ticket.thread_id}

DATOS DEL SOLICITANTE
Nombre: {ticket.nombre.strip()}
Correo: {ticket.correo.strip()}
Área: {ticket.area.strip()}

PREGUNTA ORIGINAL
{ticket.pregunta_original.strip()}

DETALLE DEL TICKET
{ticket.detalle.strip()}
""".strip()

    categoria = ticket.categoria.replace("\n", " ")[:80]
    mensaje = EmailMessage()
    mensaje["From"] = f"Alicorp IA Tickets <{config.SMTP_USER}>"
    mensaje["To"] = config.TICKET_DESTINO
    mensaje["Subject"] = f"[{ticket.urgencia}] {ticket_id} - {categoria}"

    # Las respuestas llegarán al correo escrito en el formulario.
    mensaje["Reply-To"] = ticket.correo.strip()
    mensaje.set_content(contenido)

    with smtplib.SMTP(
        config.SMTP_HOST,
        config.SMTP_PORT,
        timeout=config.SMTP_TIMEOUT_SECONDS,
    ) as servidor:
        servidor.starttls()
        servidor.login(config.SMTP_USER, config.SMTP_APP_PASSWORD)
        servidor.send_message(mensaje)

    return TicketResponse(
        ticket_id=ticket_id,
        estado="ENVIADO",
        mensaje="El ticket fue enviado correctamente.",
    )
