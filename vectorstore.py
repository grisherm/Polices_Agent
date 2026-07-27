# Construye y administra el índice FAISS de vectores.
# Si los PDFs no cambiaron, carga el índice existente; si cambiaron, lo reconstruye.

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

import config


NOMBRE_MANIFIESTO = "indice_manifest.json"
NUMERO_CANDIDATOS = 12


def sub_vectorstore_identidad_embeddings() -> str:
    """Devuelve una cadena que identifica proveedor y modelo de embeddings activos."""
    proveedor = config.EMBEDDINGS_PROVIDER

    if proveedor == "cohere":
        modelo = config.COHERE_EMBEDDING_MODEL
    elif proveedor == "gemini":
        modelo = config.GEMINI_EMBEDDING_MODEL
    else:
        modelo = "desconocido"

    return f"{proveedor}:{modelo}"


def sub_vectorstore_huella_chunks(chunks: List[Document]) -> str:
    """Calcula hash SHA-256 del contenido de los chunks e identidad de embeddings."""
    hasher = hashlib.sha256()
    hasher.update(sub_vectorstore_identidad_embeddings().encode("utf-8"))

    elementos = []
    for chunk in chunks:
        source    = str(chunk.metadata.get("source") or "")
        page      = str(chunk.metadata.get("page", ""))
        contenido = str(chunk.page_content)
        elementos.append((source, page, contenido))

    # Ordenar elementos para que el hash sea determinista
    for source, page, contenido in sorted(elementos):
        hasher.update(source.encode("utf-8", errors="ignore"))
        hasher.update(b"\0")
        hasher.update(page.encode("utf-8", errors="ignore"))
        hasher.update(b"\0")
        hasher.update(contenido.encode("utf-8", errors="ignore"))
        hasher.update(b"\0")

    return hasher.hexdigest()


def sub_vectorstore_ruta_manifiesto(faiss_dir: Path) -> Path:
    """Devuelve la ruta al JSON del manifiesto del índice."""
    return faiss_dir / NOMBRE_MANIFIESTO


def sub_vectorstore_leer_huella(faiss_dir: Path) -> str:
    """Lee la huella guardada en el manifiesto."""
    ruta = sub_vectorstore_ruta_manifiesto(faiss_dir)
    if not ruta.exists():
        return ""

    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return str(datos.get("huella") or "")
    except (OSError, ValueError, TypeError):
        return ""


def sub_vectorstore_guardar_manifiesto(
    faiss_dir: Path,
    huella: str,
    cantidad_chunks: int,
) -> None:
    """Guarda en disco la huella e identidad del índice."""
    datos = {
        "huella": huella,
        "cantidad_chunks": cantidad_chunks,
        "embeddings": sub_vectorstore_identidad_embeddings(),
    }
    sub_vectorstore_ruta_manifiesto(faiss_dir).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sub_vectorstore_indice_completo(faiss_dir: Path) -> bool:
    """Verifica la existencia de los archivos físicos de FAISS en disco."""
    return (
        (faiss_dir / "index.faiss").exists()
        and (faiss_dir / "index.pkl").exists()
    )


def sub_vectorstore_construir_en_lotes(
    chunks: List[Document],
    modelo_embeddings: Embeddings,
    faiss_dir: Path,
) -> FAISS:
    """Construye el índice FAISS por lotes con reintentos para no saturar APIs."""
    tamano_lote    = config.TAMANO_LOTE_EMBEDDINGS
    pausa_segundos = config.PAUSA_SEGUNDOS_EMBEDDINGS
    total_lotes    = (len(chunks) + tamano_lote - 1) // tamano_lote
    vectorstore    = None

    for inicio in range(0, len(chunks), tamano_lote):
        lote        = chunks[inicio : inicio + tamano_lote]
        numero_lote = inicio // tamano_lote + 1
        print(f"Embebiendo lote {numero_lote}/{total_lotes} ({len(lote)} chunks)...")

        for intento in range(1, 4):
            try:
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(lote, modelo_embeddings)
                else:
                    vectorstore.add_documents(lote)
                break
            except Exception as exc:
                if intento == 3:
                    raise
                print(
                    f"Error en lote {numero_lote}: {exc}. "
                    f"Reintentando en {pausa_segundos}s ({intento}/3)..."
                )
                time.sleep(pausa_segundos)

        vectorstore.save_local(str(faiss_dir))

        if numero_lote < total_lotes:
            time.sleep(pausa_segundos)

    if vectorstore is None:
        raise RuntimeError("No se pudo construir el índice FAISS.")

    return vectorstore


def sub_vectorstore_huella_archivos(pdf_dir: Path) -> str:
    """
    Calcula un hash SHA-256 basado en los archivos PDF de la carpeta y los embeddings activos.
    Se excluye la fecha de modificación (mtime) porque Git no la preserva al clonar en la nube (Render).
    Solo usamos el nombre del archivo y su tamaño en bytes.
    """
    hasher = hashlib.sha256()
    hasher.update(sub_vectorstore_identidad_embeddings().encode("utf-8"))

    if pdf_dir.exists():
        for archivo in sorted(pdf_dir.glob("*.pdf")):
            try:
                stat = archivo.stat()
                hasher.update(archivo.name.encode("utf-8", errors="ignore"))
                hasher.update(b"\0")
                hasher.update(str(stat.st_size).encode("utf-8"))
                hasher.update(b"\0")
            except OSError:
                hasher.update(archivo.name.encode("utf-8", errors="ignore"))

    return hasher.hexdigest()


def construir_o_cargar_vectorstore(
    modelo_embeddings: Embeddings,
) -> FAISS:
    """
    Carga el índice FAISS si sigue siendo válido, o lo reconstruye si cambió algo.
    Válido significa que los archivos existen y la huella coincide con los metadatos de los PDFs actuales.
    """
    proveedor = config.EMBEDDINGS_PROVIDER
    if modelo_embeddings is None or proveedor not in {"cohere", "gemini"}:
        raise RuntimeError(
            "No hay un proveedor de embeddings válido. "
            "Configura EMBEDDINGS_PROVIDER como 'cohere' o 'gemini' en el .env."
        )

    faiss_dir       = Path(config.FAISS_INDEX_DIR)
    pdf_dir         = Path(config.PDF_DIR)
    huella_actual   = sub_vectorstore_huella_archivos(pdf_dir)
    huella_guardada = sub_vectorstore_leer_huella(faiss_dir)

    indice_existe      = faiss_dir.exists() and sub_vectorstore_indice_completo(faiss_dir)
    indice_actualizado = huella_guardada == huella_actual

    if indice_existe and indice_actualizado:
        print(f"Cargando índice FAISS vigente desde '{faiss_dir}'...")
        return FAISS.load_local(
            str(faiss_dir),
            modelo_embeddings,
            allow_dangerous_deserialization=True,
        )

    if faiss_dir.exists():
        print("Los documentos o el modelo de embeddings cambiaron. Reconstruyendo el índice...")
        shutil.rmtree(faiss_dir)

    print(f"Construyendo nuevo índice FAISS en '{faiss_dir}'...")
    
    # Importaciones diferidas para evitar cargar PyMuPDF y Transformers (que consume >512MB RAM)
    # a menos que realmente se necesite reconstruir el índice localmente.
    from documentos import cargar_documentos, trocear_documentos
    
    docs = cargar_documentos(pdf_dir)
    chunks = trocear_documentos(docs)
    
    vectorstore = sub_vectorstore_construir_en_lotes(chunks, modelo_embeddings, faiss_dir)

    sub_vectorstore_guardar_manifiesto(faiss_dir, huella_actual, len(chunks))
    print(f"Índice FAISS guardado con {len(chunks)} fragmentos.")

    return vectorstore


def construir_retriever(vectorstore: FAISS):
    """
    Crea el retriever que busca los fragmentos más relevantes en FAISS.
    Recupera 12 candidatos; busqueda_rag.py luego elige los 4 mejores.
    """
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": NUMERO_CANDIDATOS},
    )
def cargar_vectorstore_si_existe(modelo_embeddings):
    faiss_dir = Path(config.FAISS_INDEX_DIR)

    indice_completo = (
        (faiss_dir / "index.faiss").exists()
        and (faiss_dir / "index.pkl").exists()
    )

    if not indice_completo:
        print("No existe un índice FAISS completo.")
        return None

    print(f"Cargando índice FAISS desde '{faiss_dir}'...")

    return FAISS.load_local(
        str(faiss_dir),
        modelo_embeddings,
        allow_dangerous_deserialization=True,
    )