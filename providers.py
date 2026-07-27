# Construye y devuelve el LLM y el modelo de embeddings según lo que esté en el .env.
# Soporta Cohere y Gemini; se elige con LLM_PROVIDER y EMBEDDINGS_PROVIDER.

from langchain_cohere import ChatCohere, CohereEmbeddings
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)

import config


def construir_llm():
    """Devuelve el modelo de chat configurado (Cohere o Gemini)."""
    if config.LLM_PROVIDER == "cohere":
        print(f"LLM: usando Cohere, modelo '{config.COHERE_CHAT_MODEL}'")
        return ChatCohere(
            model=config.COHERE_CHAT_MODEL,
            temperature=0,
            cohere_api_key=config.COHERE_API_KEY,
            timeout_seconds=config.COHERE_TIMEOUT_SECONDS,
        )

    if config.LLM_PROVIDER == "gemini":
        print(f"LLM: usando Gemini API, modelo '{config.GEMINI_CHAT_MODEL}'")
        return ChatGoogleGenerativeAI(
            model=config.GEMINI_CHAT_MODEL,
            temperature=0,
            google_api_key=config.GEMINI_API_KEY,
        )

    raise ValueError(
        f"LLM_PROVIDER='{config.LLM_PROVIDER}' no reconocido. "
        "Usa 'cohere' o 'gemini' en el .env."
    )


def construir_embeddings():
    """Devuelve el modelo de embeddings configurado (Cohere o Gemini)."""
    if config.EMBEDDINGS_PROVIDER == "cohere":
        print(f"Embeddings: usando Cohere, modelo '{config.COHERE_EMBEDDING_MODEL}'")
        return CohereEmbeddings(
            model=config.COHERE_EMBEDDING_MODEL,
            cohere_api_key=config.COHERE_API_KEY,
            request_timeout=config.COHERE_TIMEOUT_SECONDS,
            max_retries=3,
        )

    if config.EMBEDDINGS_PROVIDER == "gemini":
        print(f"Embeddings: usando Gemini API, modelo '{config.GEMINI_EMBEDDING_MODEL}'")
        return GoogleGenerativeAIEmbeddings(
            model=config.GEMINI_EMBEDDING_MODEL,
            google_api_key=config.GEMINI_API_KEY,
        )

    raise ValueError(
        f"EMBEDDINGS_PROVIDER='{config.EMBEDDINGS_PROVIDER}' no reconocido. "
        "Usa 'cohere' o 'gemini' en el .env."
    )
