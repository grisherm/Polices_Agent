import { useState } from "react";
import { ArrowLeft, CheckCircle2, Mail, Send, ShieldCheck } from "lucide-react";


export default function TicketPage({ draft, apiUrl, onBack }) {
  const [form, setForm] = useState({
    nombre: "",
    correo: "",
    area: "",
    categoria: "Ética y cumplimiento",
    urgencia: draft.urgencia || "BAJA",
    detalle: draft.preguntaOriginal,
  });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState(null);

  function cambiarCampo(event) {
    const { name, value } = event.target;
    setForm({ ...form, [name]: value });
  }

  async function enviarTicket(event) {
    event.preventDefault();
    setEnviando(true);
    setError("");

    const ticket = {
      ...form,
      thread_id: draft.threadId,
      pregunta_original: draft.preguntaOriginal,
    };

    try {
      const respuesta = await fetch(`${apiUrl}/api/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ticket),
      });
      const datos = await respuesta.json();

      if (!respuesta.ok) {
        const mensaje = typeof datos.detail === "string"
          ? datos.detail
          : "No se pudo enviar el ticket.";
        throw new Error(mensaje);
      }

      setResultado(datos);
    } catch (errorEnvio) {
      setError(errorEnvio.message || "No se pudo enviar el ticket.");
    } finally {
      setEnviando(false);
    }
  }

  if (resultado) {
    return (
      <main className="ticket-page">
        <section className="ticket-result">
          <CheckCircle2 size={52} />
          <span className="eyebrow">Solicitud enviada</span>
          <h1>Ticket enviado correctamente</h1>
          <p>El área responsable recibió tu solicitud.</p>

          <div className="ticket-code">
            <small>Código de seguimiento</small>
            <strong>{resultado.ticket_id}</strong>
          </div>

          <button type="button" className="ticket-primary-button" onClick={onBack}>
            Volver al chat
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="ticket-page">
      <section className="ticket-container">
        <button className="ticket-back" type="button" onClick={onBack}>
          <ArrowLeft size={17} />
          Volver al chat
        </button>

        <header className="ticket-header">
          <span className="ticket-header__icon"><Mail size={24} /></span>
          <div>
            <span className="eyebrow">Gestión corporativa</span>
            <h1>Completar ticket</h1>
            <p>Revisa la información antes de enviarla.</p>
          </div>
        </header>

        <form className="ticket-form" onSubmit={enviarTicket}>
          <div className="ticket-grid">
            <label>
              Nombre completo
              <input
                name="nombre"
                value={form.nombre}
                onChange={cambiarCampo}
                maxLength={120}
                required
              />
            </label>

            <label>
              Correo
              <input
                type="email"
                name="correo"
                value={form.correo}
                onChange={cambiarCampo}
                maxLength={180}
                required
              />
            </label>

            <label className="ticket-grid__full">
              Área
              <input
                name="area"
                value={form.area}
                onChange={cambiarCampo}
                maxLength={120}
                required
              />
            </label>
          </div>

          <div className="ticket-grid">
            <label>
              Categoría
              <select name="categoria" value={form.categoria} onChange={cambiarCampo}>
                <option>Ética y cumplimiento</option>
                <option>Seguridad de la información</option>
                <option>Regalos y atenciones</option>
                <option>Derechos humanos</option>
                <option>Otro</option>
              </select>
            </label>

            <label>
              Urgencia
              <select name="urgencia" value={form.urgencia} onChange={cambiarCampo}>
                <option value="BAJA">Baja</option>
                <option value="MEDIA">Media</option>
                <option value="ALTA">Alta</option>
              </select>
            </label>
          </div>

          <div className="ticket-original-question">
            <small>Consulta que originó el ticket</small>
            <p>{draft.preguntaOriginal}</p>
          </div>

          <label>
            Detalle que será enviado
            <textarea
              name="detalle"
              value={form.detalle}
              onChange={cambiarCampo}
              minLength={10}
              maxLength={5000}
              rows={8}
              required
            />
          </label>

          {error && <div className="ticket-error">{error}</div>}

          <div className="ticket-form__footer">
            <span><ShieldCheck size={15} /> Revisa el contenido antes de enviarlo.</span>
            <button type="submit" className="ticket-primary-button" disabled={enviando}>
              {enviando ? "Enviando..." : <><Send size={16} /> Enviar ticket</>}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
