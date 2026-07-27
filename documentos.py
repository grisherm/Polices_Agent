# Carga los PDF de políticas de Alicorp, los divide en fragmentos y genera
# la lista de políticas disponibles para el triaje.

from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document


import config


def obtener_nombres_politicas(pdf_dir: Optional[Path] = None) -> List[str]:
    """
    Obtiene los nombres únicos de las políticas directamente de los archivos
    disponibles en la carpeta PDF sin cargarlos en memoria.
    """
    pdf_dir = pdf_dir or config.PDF_DIR
    if not pdf_dir.exists():
        return []
    return sorted([archivo.stem for archivo in pdf_dir.glob("*.pdf")])


def cargar_documentos(pdf_dir: Optional[Path] = None) -> List[Document]:
    """
    Lee todos los PDF de la carpeta configurada y los devuelve como objetos Document.
    Lanza un error si la carpeta no existe o está vacía.
    """
    pdf_dir = pdf_dir or config.PDF_DIR
    docs: List[Document] = []

    if not pdf_dir.exists():
        raise FileNotFoundError(
            f"No existe la carpeta '{pdf_dir}'. "
            "Crea la carpeta y coloca ahí los PDF de las políticas."
        )

    for archivo in pdf_dir.glob("*.pdf"):
        try:
            loader = PyMuPDFLoader(str(archivo))
            docs.extend(loader.load())
            print(f"Archivo cargado: {archivo.name}")
        except Exception as error:
            print(f"Error cargando '{archivo.name}': {error}")

    print(f"Total de documentos cargados: {len(docs)}")

    if not docs:
        raise RuntimeError(
            f"No se cargó ningún PDF desde '{pdf_dir}'. "
            "Verifica que la carpeta contenga archivos .pdf válidos."
        )

    return docs


def trocear_documentos(
    docs: List[Document],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Document]:
    """
    Divide los documentos en fragmentos de tamaño controlado en tokens.
    Agrega un encabezado con el nombre de la política y la página a cada fragmento.
    """
    chunk_size    = chunk_size    or config.CHUNK_SIZE_TOKENS
    chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP_TOKENS
    
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from transformers import AutoTokenizer
# Mide tamaño en tokens, no en caracteres
    tokenizer = AutoTokenizer.from_pretrained(config.HF_TOKENIZER_MODEL)

    splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer=tokenizer,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(docs)

    for chunk in chunks:
        source          = chunk.metadata.get("source", "")
        nombre_politica = Path(source).stem

        try:
            pagina = int(chunk.metadata.get("page", 0)) + 1
        except (TypeError, ValueError):
            pagina = 1

        chunk.page_content = (
            f"Política: {nombre_politica}\n"
            f"Página: {pagina}\n\n"
            f"{chunk.page_content}"
        )

    print(f"Total de fragmentos a indexar: {len(chunks)}")
    return chunks


def generar_lista_politicas(docs: List[Document]) -> str:
    """Extrae nombres únicos de PDFs cargados formateados como lista con viñetas."""
    nombres = sorted(
        {
            Path(doc.metadata.get("source", "")).stem
            for doc in docs
            if doc.metadata.get("source")
        }
    )
    lista = "\n".join(f"- {nombre}." for nombre in nombres)
    print(f"Políticas detectadas: {nombres}")
    return lista
