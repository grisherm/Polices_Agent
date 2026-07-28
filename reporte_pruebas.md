# Reporte de Pruebas Automatizadas del Agente Nexus Logistics & Tech

## Estado: pendiente de ejecución

Los 45 casos de `test_agente_ligero.py` fueron reescritos para usar preguntas
y datos concretos (montos, plazos, porcentajes) verificables en los 9 PDFs de
políticas de Nexus Logistics & Tech. Sin embargo, este reporte todavía no
contiene una ejecución real de la suite: el reporte anterior correspondía al
proyecto original (Alicorp) y se retiró para no dejar resultados que no
corresponden al código ni a los documentos actuales del proyecto.

La suite necesita, para ejecutarse:

1. Un backend corriendo (`python Main.py`) con una API key válida de Cohere o
   Gemini en `.env`.
2. Acceso de red a Hugging Face (`huggingface.co`) la primera vez que se
   construye el índice FAISS, porque `documentos.py` descarga el tokenizador
   `BAAI/bge-m3` para trocear los PDFs por tokens. En un entorno con política
   de red restringida (por ejemplo, algunas sesiones de Claude Code en la
   nube) esa descarga puede estar bloqueada; en una máquina local normal no
   debería serlo.

## Cómo generar este reporte

```bash
# Terminal 1
python Main.py

# Terminal 2, una vez que /health responda "ok"
python test_agente_ligero.py
```

El script sobrescribe este archivo automáticamente, caso por caso, con los
resultados reales de la ejecución (acción esperada vs. obtenida, respuesta
completa del agente y citaciones devueltas).
