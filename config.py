# Lee las variables del .env y las expone como constantes para todo el proyecto.
# Aquí se elige qué proveedor de LLM y de embeddings se va a usar.

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# Proveedor de LLM activo
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "cohere").strip().lower()

COHERE_API_KEY         = os.getenv("COHERE_API_KEY", "").strip()
COHERE_CHAT_MODEL      = os.getenv("COHERE_CHAT_MODEL", "command-a-03-2025").strip()
COHERE_TIMEOUT_SECONDS = float(os.getenv("COHERE_TIMEOUT_SECONDS", "120"))

GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.0-flash").strip()

if LLM_PROVIDER == "cohere" and not COHERE_API_KEY:
    raise RuntimeError("Falta COHERE_API_KEY en el archivo .env.")

if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
    raise RuntimeError("Falta GEMINI_API_KEY en el archivo .env.")

if LLM_PROVIDER not in {"cohere", "gemini"}:
    raise RuntimeError(f"LLM_PROVIDER='{LLM_PROVIDER}' no es válido (usa 'cohere' o 'gemini').")


# Proveedor de embeddings activo (cohere o gemini)
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "cohere").strip().lower()

COHERE_EMBEDDING_MODEL = os.getenv("COHERE_EMBEDDING_MODEL", "embed-v4.0").strip()
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-exp-03-07").strip()

if EMBEDDINGS_PROVIDER == "cohere" and not COHERE_API_KEY:
    raise RuntimeError("Falta COHERE_API_KEY en el .env para los embeddings.")

if EMBEDDINGS_PROVIDER == "gemini" and not GEMINI_API_KEY:
    raise RuntimeError("Falta GEMINI_API_KEY en el .env para los embeddings.")

if EMBEDDINGS_PROVIDER not in {"cohere", "gemini"}:
    raise RuntimeError(f"EMBEDDINGS_PROVIDER='{EMBEDDINGS_PROVIDER}' no es válido.")


# Configuración del RAG y procesamiento de documentos
PDF_DIR         = Path(os.getenv("PDF_DIR", "./Documentos"))
FAISS_INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "./faiss_indexv2")

# Tokenizador local para medir longitud de fragmentos
HF_TOKENIZER_MODEL = os.getenv("HF_TOKENIZER_MODEL", "BAAI/bge-m3")

TAMANO_LOTE_EMBEDDINGS    = int(os.getenv("TAMANO_LOTE_EMBEDDINGS", "20"))
PAUSA_SEGUNDOS_EMBEDDINGS = int(os.getenv("PAUSA_SEGUNDOS_EMBEDDINGS", "15"))
CHUNK_SIZE_TOKENS         = int(os.getenv("CHUNK_SIZE_TOKENS", "800"))
CHUNK_OVERLAP_TOKENS      = int(os.getenv("CHUNK_OVERLAP_TOKENS", "120"))

MOSTRAR_MULTIQUERIES = os.getenv("MOSTRAR_MULTIQUERIES", "false").strip().lower() == "true"


# Correo usado para enviar los tickets
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
TICKET_DESTINO = os.getenv("TICKET_DESTINO", "").strip()
SMTP_TIMEOUT_SECONDS = int(os.getenv("SMTP_TIMEOUT_SECONDS", "30"))
