import { useEffect, useState } from "react";
import { ArrowLeft, BarChart3, RefreshCw } from "lucide-react";

const ETIQUETAS_ACCION = {
  AUTO_RESOLVER: "Respondidas con RAG",
  LISTAR_POLITICAS: "Catálogo solicitado",
  PEDIR_INFO: "Requirieron precisión",
  ABRIR_TICKET: "Derivadas a ticket",
  SALUDO: "Saludos",
  FUERA_DE_AMBITO: "Fuera de ámbito",
  SIN_INFORMACION: "Sin información",
};

function Barra({ etiqueta, valor, total }) {
  const porcentaje = total > 0 ? Math.round((valor / total) * 100) : 0;
  return (
    <div className="stats-bar">
      <div className="stats-bar__label">
        <span>{etiqueta}</span>
        <strong>{valor}</strong>
      </div>
      <div className="stats-bar__track">
        <div className="stats-bar__fill" style={{ width: `${porcentaje}%` }} />
      </div>
    </div>
  );
}

export default function MetricsPage({ apiUrl, onBack }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  async function cargarMetricas() {
    setCargando(true);
    setError("");
    try {
      const respuesta = await fetch(`${apiUrl}/api/metricas`);
      if (!respuesta.ok) throw new Error("No se pudieron cargar las métricas.");
      setDatos(await respuesta.json());
    } catch (errorCarga) {
      setError(errorCarga.message || "No se pudieron cargar las métricas.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarMetricas();
  }, []);

  const totalPreguntas = datos?.total_preguntas || 0;
  const porArea = datos?.por_area || {};
  const porAccion = datos?.por_accion || {};

  return (
    <main className="ticket-page">
      <section className="ticket-container">
        <button className="ticket-back" type="button" onClick={onBack}>
          <ArrowLeft size={17} />
          Volver al chat
        </button>

        <header className="ticket-header">
          <span className="ticket-header__icon"><BarChart3 size={24} /></span>
          <div>
            <span className="eyebrow">Panel interno</span>
            <h1>Uso del agente</h1>
            <p>Conteo acumulado desde que se inició este servicio (se reinicia al reiniciar el servidor).</p>
          </div>
        </header>

        {error && <div className="ticket-error">{error}</div>}

        {!error && (
          <>
            <div className="stats-total">
              <small>Consultas procesadas</small>
              <strong>{cargando ? "…" : totalPreguntas}</strong>
            </div>

            <div className="stats-section">
              <h2>Por área</h2>
              {Object.keys(porArea).length === 0 && !cargando && (
                <p className="stats-empty">Todavía no hay consultas registradas.</p>
              )}
              {Object.entries(porArea)
                .sort((a, b) => b[1] - a[1])
                .map(([area, valor]) => (
                  <Barra key={area} etiqueta={area} valor={valor} total={totalPreguntas} />
                ))}
            </div>

            <div className="stats-section">
              <h2>Por tipo de respuesta</h2>
              {Object.entries(porAccion)
                .sort((a, b) => b[1] - a[1])
                .map(([accion, valor]) => (
                  <Barra
                    key={accion}
                    etiqueta={ETIQUETAS_ACCION[accion] || accion}
                    valor={valor}
                    total={totalPreguntas}
                  />
                ))}
            </div>

            <button className="ticket-back" type="button" onClick={cargarMetricas} disabled={cargando}>
              <RefreshCw size={15} />
              {cargando ? "Actualizando..." : "Actualizar"}
            </button>
          </>
        )}
      </section>
    </main>
  );
}
