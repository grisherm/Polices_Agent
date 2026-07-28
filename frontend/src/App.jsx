import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  CircleGauge,
  Clock3,
  Database,
  FileText,
  Menu,
  MessageSquareText,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import MetricsPage from "./MetricsPage";
import TicketPage from "./TicketPage";

// En produccion React y FastAPI comparten dominio, por eso la URL base queda
// vacia y las llamadas son relativas (/api/chat, /health, etc.). Vite usa el
// proxy de vite.config.js durante el desarrollo local.
const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const STORAGE_KEY = "nexus-ai-conversations-v1";
const ACTIVE_KEY = "nexus-ai-active-conversation-v1";

const SUGGESTIONS = [
  {
    eyebrow: "Ética",
    title: "Código de conducta",
    prompt: "¿Cuáles son los principios del Código de Ética y Conducta de Nexus Logistics & Tech?",
    icon: ShieldCheck,
  },
  {
    eyebrow: "Seguridad laboral",
    title: "Equipo de protección personal",
    prompt: "¿Qué equipo de protección personal es obligatorio en bodega?",
    icon: Sparkles,
  },
  {
    eyebrow: "Tecnología",
    title: "Protección de datos",
    prompt: "¿Qué medidas de seguridad de la información debemos seguir?",
    icon: Database,
  },
  {
    eyebrow: "Finanzas",
    title: "Viáticos y reembolsos",
    prompt: "¿Cuál es el monto máximo reembolsable por noche de hospedaje?",
    icon: CircleGauge,
  },
];

const ACTION_LABELS = {
  AUTO_RESOLVER:    { label: "Respuesta verificada",    tone: "success" },
  LISTAR_POLITICAS: { label: "Catálogo de políticas",   tone: "success" },
  PEDIR_INFO:       { label: "Requiere precisión",      tone: "warning" },
  ABRIR_TICKET:     { label: "Requiere gestión",        tone: "danger"  },
  SALUDO:           { label: "Conversación",            tone: "neutral" },
  FUERA_DE_AMBITO:  { label: "Fuera de ámbito",         tone: "neutral" },
  SIN_INFORMACION:  { label: "Sin información",         tone: "neutral" },
};

const AREA_META = {
  "Recursos Humanos y Convivencia": { short: "RRHH", tone: "area-indigo" },
  "Tecnología y Seguridad de la Información": { short: "Tecnología", tone: "area-sky" },
  "Salud y Seguridad en el Trabajo": { short: "SST", tone: "area-green" },
  "Finanzas y Administración": { short: "Finanzas", tone: "area-amber" },
  General: { short: "General", tone: "area-slate" },
};

function areaMeta(area) {
  return AREA_META[area] || AREA_META.General;
}

function makeId(prefix = "id") {
  if (globalThis.crypto?.randomUUID) return `${prefix}_${crypto.randomUUID()}`;
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function createConversation() {
  return {
    id: makeId("chat"),
    title: "Nueva conversación",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [],
  };
}

function loadConversations() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (Array.isArray(parsed) && parsed.length) return parsed;
  } catch {
    // Si el almacenamiento local está dañado, se empieza una sesión limpia.
  }
  return [createConversation()];
}

function displayTime(iso) {
  if (!iso) return "";
  return new Intl.DateTimeFormat("es-PE", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function displayPolicyName(name) {
  return String(name || "Política sin nombre")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function createTitle(text) {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > 43 ? `${clean.slice(0, 43)}…` : clean;
}

function getErrorMessage(status, data) {
  if (status === 429) {
    return "Se alcanzó el límite temporal de solicitudes de Cohere. Espera un momento e inténtalo nuevamente.";
  }
  if (status === 503) {
    return "El agente todavía está iniciando. Espera unos segundos mientras carga las políticas y el índice de búsqueda.";
  }
  if (status === 401 || status === 403) {
    return "El backend no pudo autenticarse con su proveedor de IA. Revisa la clave configurada en el servidor.";
  }
  if (status >= 500) {
    return "El agente encontró un problema interno. Revisa los registros del backend e inténtalo otra vez.";
  }
  return data?.detail || data?.message || "No fue posible completar la consulta.";
}

function BrandMark({ compact = false }) {
  return (
    <div className={`brand-mark ${compact ? "brand-mark--compact" : ""}`}>
      <span>N</span>
    </div>
  );
}

function CitationList({ citations }) {
  const [open, setOpen] = useState(false);
  if (!citations?.length) return null;

  return (
    <div className="citations">
      <button className="citations__toggle" type="button" onClick={() => setOpen((v) => !v)}>
        <BookOpen size={15} />
        {citations.length} {citations.length === 1 ? "fuente consultada" : "fuentes consultadas"}
        <ChevronDown size={15} className={open ? "rotate" : ""} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="citations__list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            {citations.map((citation, index) => (
              <div className="citation-card" key={`${citation.fuente}-${citation.pagina}-${index}`}>
                <div className="citation-card__header">
                  <FileText size={15} />
                  <strong>{displayPolicyName(citation.fuente)}</strong>
                  <span>Pág. {citation.pagina}</span>
                </div>
                <p>{citation.texto}</p>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Message({ message, onOpenTicket }) {
  const isUser = message.role === "user";
  const action = ACTION_LABELS[message.action] || ACTION_LABELS.SALUDO;
  const area = !isUser && message.area ? areaMeta(message.area) : null;

  return (
    <motion.article
      className={`card-msg ${isUser ? "card-msg--user" : "card-msg--assistant"} ${
        area ? area.tone : ""
      } ${message.error ? "card-msg--error" : ""}`}
      initial={{ opacity: 0, y: 12, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="card-msg__meta">
        {!isUser && <strong>Nexus</strong>}
        {area && <span className="area-tag">{area.short}</span>}
        <span className="card-msg__time">{displayTime(message.createdAt)}</span>
      </div>
      <div className="card-msg__content markdown-body">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        )}
      </div>
      {!isUser && message.action && (
        <span className={`action-badge action-badge--${action.tone}`}>
          {action.tone === "success" && <Check size={12} />}
          {action.label}
        </span>
      )}
      {!isUser && message.triage && !message.error && (
        <div className="message__diagnostic">
          <Activity size={13} />
          Ruta: {message.triage.decision?.replaceAll("_", " ")}
          <span />
          Urgencia: {message.triage.urgencia}
        </div>
      )}
      <CitationList citations={message.citations} />
      {!isUser && message.action === "ABRIR_TICKET" && message.ticketDraft && (
        <button
          type="button"
          className="ticket-action-button"
          onClick={() => onOpenTicket(message.ticketDraft)}
        >
          <Send size={15} />
          Completar ticket
        </button>
      )}
    </motion.article>
  );
}

function ThinkingMessage() {
  return (
    <motion.div
      className="thinking__card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
    >
      <div className="thinking__dots"><i /><i /><i /></div>
      <span>Consultando políticas y verificando el respaldo…</span>
    </motion.div>
  );
}

function WelcomeCard({ onSuggestion }) {
  return (
    <motion.div className="welcome-card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
      <span className="welcome-card__kicker"><Sparkles size={13} /> Copiloto Nexus</span>
      <h1>Cero rodeos. Directo al dato que necesitas.</h1>
      <p>
        Pregunta lo que sea sobre nuestras políticas internas y recibe una respuesta
        verificada, con su fuente exacta, en segundos.
      </p>
      <div className="welcome-card__chips">
        {SUGGESTIONS.map((suggestion) => {
          const Icon = suggestion.icon;
          return (
            <button
              type="button"
              className="chip-suggestion"
              key={suggestion.title}
              onClick={() => onSuggestion(suggestion.prompt)}
            >
              <Icon size={14} />
              {suggestion.title}
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}

function PoliciesPanel({ open, onClose, policies, status }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button
            aria-label="Cerrar panel de políticas"
            className="drawer-backdrop"
            type="button"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            className="policy-drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
          >
            <div className="policy-drawer__head">
              <div>
                <span className="eyebrow">Base documental</span>
                <h2>Políticas disponibles</h2>
              </div>
              <button className="icon-button" type="button" onClick={onClose} aria-label="Cerrar">
                <X size={19} />
              </button>
            </div>
            <p className="policy-drawer__intro">
              El agente recupera fragmentos de estos documentos y verifica cada respuesta antes de mostrarla.
            </p>
            <div className="policy-drawer__list">
              {status !== "online" && (
                <div className="drawer-empty"><WifiOff size={20} /> Conecta el backend para cargar la lista.</div>
              )}
              {status === "online" && !policies.length && (
                <div className="drawer-empty"><FileText size={20} /> No se encontraron políticas indexadas.</div>
              )}
              {policies.map((policy, index) => (
                <motion.div
                  className="policy-row"
                  key={`${policy}-${index}`}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.035 }}
                >
                  <span><FileText size={16} /></span>
                  <div>
                    <strong>{displayPolicyName(policy)}</strong>
                    <small>Documento indexado</small>
                  </div>
                  <ShieldCheck size={16} />
                </motion.div>
              ))}
            </div>
            <div className="policy-drawer__footer">
              <Database size={16} />
              FAISS · recuperación semántica · verificación RAG
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function HistoryPanel({ open, onClose, conversations, activeId, pendingId, onSelect, onDelete, onNew }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button
            aria-label="Cerrar historial"
            className="drawer-backdrop"
            type="button"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            className="history-drawer"
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
          >
            <div className="policy-drawer__head">
              <div>
                <span className="eyebrow">Tus conversaciones</span>
                <h2>Historial</h2>
              </div>
              <button className="icon-button" type="button" onClick={onClose} aria-label="Cerrar">
                <X size={19} />
              </button>
            </div>
            <button className="new-chat" type="button" onClick={onNew}>
              <Plus size={17} />
              Nueva conversación
            </button>
            <div className="policy-drawer__list">
              {conversations.map((conversation) => (
                <div
                  className={`conversation-item ${conversation.id === activeId ? "conversation-item--active" : ""}`}
                  key={conversation.id}
                >
                  <button className="conversation-item__select" type="button" onClick={() => onSelect(conversation.id)}>
                    <MessageSquareText size={16} />
                    <span>
                      <strong>{conversation.title}</strong>
                      <small>{conversation.messages.length} mensajes</small>
                    </span>
                  </button>
                  <button
                    className="conversation-item__delete"
                    type="button"
                    aria-label="Eliminar conversación"
                    onClick={(event) => onDelete(conversation.id, event)}
                    disabled={conversation.id === pendingId}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function ContextPanel({ open, onClose, area, relatedPolicies, metrics, onOpenMetrics, apiStatus }) {
  const meta = areaMeta(area);
  const entries = Object.entries(metrics?.por_area || {}).sort((a, b) => b[1] - a[1]);
  const maxValue = Math.max(1, ...entries.map(([, value]) => value));

  return (
    <aside className={`context-panel ${open ? "context-panel--open" : ""}`}>
      <button className="context-panel__close icon-button" type="button" onClick={onClose} aria-label="Cerrar panel">
        <X size={18} />
      </button>

      <div className="context-block">
        <h3>Área detectada</h3>
        <div className={`area-badge ${meta.tone}`}>
          <span className="area-badge__dot" />
          <div>
            <strong>{area ? meta.short : "Sin consultas aún"}</strong>
            <small>{area || "Escribe tu primera pregunta"}</small>
          </div>
        </div>
      </div>

      <div className="context-block">
        <h3>Políticas relacionadas</h3>
        {relatedPolicies.length ? (
          <div className="quick-list">
            {relatedPolicies.slice(0, 4).map((policy, index) => (
              <div className="quick-item" key={`${policy.fuente}-${index}`}>
                <span className="quick-item__icon"><FileText size={14} /></span>
                {displayPolicyName(policy.fuente)}
              </div>
            ))}
          </div>
        ) : (
          <p className="context-empty">Aparecerán aquí en cuanto Nexus cite una política.</p>
        )}
      </div>

      <div className="context-block context-block--grow">
        <h3>Pulso del copiloto</h3>
        <div className="stat-widget">
          <div className="stat-widget__head">
            <span>Consultas por área</span>
            <span className={`status-dot status-dot--${apiStatus}`} />
          </div>
          {entries.length ? (
            entries.slice(0, 4).map(([label, value]) => (
              <div className="bar-row" key={label}>
                <span className="bar-row__label">{areaMeta(label).short}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${(value / maxValue) * 100}%` }} />
                </div>
                <span className="bar-row__value">{value}</span>
              </div>
            ))
          ) : (
            <p className="context-empty context-empty--dark">Aún no hay datos de uso.</p>
          )}
          <button className="stat-widget__link" type="button" onClick={onOpenMetrics}>
            Ver panel completo →
          </button>
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  const initialConversations = useMemo(() => loadConversations(), []);
  const [conversations, setConversations] = useState(initialConversations);
  const [activeId, setActiveId] = useState(
    () => localStorage.getItem(ACTIVE_KEY) || initialConversations[0].id,
  );
  const [input, setInput] = useState("");
  const [pendingConversationId, setPendingConversationId] = useState(null);
  const [apiStatus, setApiStatus] = useState("checking");
  const [policies, setPolicies] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [policiesOpen, setPoliciesOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [ticketDraft, setTicketDraft] = useState(null);
  const [showMetrics, setShowMetrics] = useState(false);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) || conversations[0],
    [activeId, conversations],
  );
  const pending = Boolean(pendingConversationId);

  const currentArea = useMemo(() => {
    const msgs = activeConversation?.messages || [];
    for (let i = msgs.length - 1; i >= 0; i -= 1) {
      if (msgs[i].role === "assistant" && msgs[i].area) return msgs[i].area;
    }
    return null;
  }, [activeConversation]);

  const relatedPolicies = useMemo(() => {
    const msgs = activeConversation?.messages || [];
    for (let i = msgs.length - 1; i >= 0; i -= 1) {
      if (msgs[i].role === "assistant" && msgs[i].citations?.length) {
        const seen = new Set();
        return msgs[i].citations.filter((citation) => {
          if (seen.has(citation.fuente)) return false;
          seen.add(citation.fuente);
          return true;
        });
      }
    }
    return [];
  }, [activeConversation]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    localStorage.setItem(ACTIVE_KEY, activeId);
  }, [activeId, conversations]);

  useEffect(() => {
    if (!conversations.some((conversation) => conversation.id === activeId)) {
      setActiveId(conversations[0]?.id || "");
    }
  }, [activeId, conversations]);

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/metricas`, { signal: AbortSignal.timeout(8000) });
      if (response.ok) setMetrics(await response.json());
    } catch {
      // El panel de contexto simplemente queda sin datos de uso.
    }
  }, []);

  const checkBackend = useCallback(async () => {
    setApiStatus("checking");
    try {
      const healthResponse = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(8000) });
      const health = await healthResponse.json();
      if (!healthResponse.ok || health.status !== "ok") throw new Error("Backend no disponible");
      setApiStatus("online");

      const policyResponse = await fetch(`${API_URL}/api/politicas`, {
        signal: AbortSignal.timeout(10000),
      });
      if (policyResponse.ok) {
        const data = await policyResponse.json();
        setPolicies(Array.isArray(data.politicas) ? data.politicas : []);
      }
      fetchMetrics();
    } catch {
      setApiStatus("offline");
      setPolicies([]);
    }
  }, [fetchMetrics]);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  }, [activeConversation?.messages?.length, pending]);

  const updateConversation = useCallback((id, updater) => {
    setConversations((current) =>
      current.map((conversation) => (conversation.id === id ? updater(conversation) : conversation)),
    );
  }, []);

  function startNewConversation() {
    const conversation = createConversation();
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setInput("");
    setHistoryOpen(false);
    window.setTimeout(() => textareaRef.current?.focus(), 120);
  }

  useEffect(() => {
    function handleGlobalShortcut(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "n") {
        event.preventDefault();
        startNewConversation();
      }
      if (event.key === "Escape") {
        setHistoryOpen(false);
        setPoliciesOpen(false);
        setContextOpen(false);
      }
    }

    window.addEventListener("keydown", handleGlobalShortcut);
    return () => window.removeEventListener("keydown", handleGlobalShortcut);
  }, []);

  async function clearCurrentConversation() {
    if (!activeConversation || pending) return;
    try {
      await fetch(
        `${API_URL}/api/chat/historial/${encodeURIComponent(activeConversation.id)}`,
        { method: "DELETE" },
      );
    } catch {
      // El historial visual se puede limpiar aunque el backend esté desconectado.
    }
    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      title: "Nueva conversación",
      messages: [],
      updatedAt: new Date().toISOString(),
    }));
  }

  async function deleteConversation(id, event) {
    event?.stopPropagation();
    if (id === pendingConversationId) return;
    try {
      await fetch(`${API_URL}/api/chat/historial/${encodeURIComponent(id)}`, { method: "DELETE" });
    } catch {
      // La conversación local se elimina aunque el backend no responda.
    }

    const remaining = conversations.filter((conversation) => conversation.id !== id);
    if (remaining.length) {
      setConversations(remaining);
      if (id === activeId) setActiveId(remaining[0].id);
      return;
    }

    const replacement = createConversation();
    setConversations([replacement]);
    setActiveId(replacement.id);
  }

  async function sendMessage(forcedPrompt) {
    const question = String(forcedPrompt ?? input).trim();
    if (!question || pending || !activeConversation) return;

    const conversationId = activeConversation.id;
    const userMessage = {
      id: makeId("message"),
      role: "user",
      content: question,
      createdAt: new Date().toISOString(),
    };

    setInput("");
    setPendingConversationId(conversationId);
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      title: conversation.messages.length ? conversation.title : createTitle(question),
      updatedAt: new Date().toISOString(),
      messages: [...conversation.messages, userMessage],
    }));

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pregunta: question, thread_id: conversationId }),
        signal: AbortSignal.timeout(180000),
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (!response.ok) throw Object.assign(new Error(getErrorMessage(response.status, data)), { status: response.status });

      const assistantMessage = {
        id: makeId("message"),
        role: "assistant",
        content: data.respuesta || "El agente no devolvió contenido.",
        action: data.accion_final,
        area: data.area || null,
        triage: data.triaje,
        ticketDraft:
          data.accion_final === "ABRIR_TICKET"
            ? {
                preguntaOriginal: question,
                urgencia: data.triaje?.urgencia || "BAJA",
                threadId: conversationId,
              }
            : null,
        citations: (data.citaciones || []).map((citation) => ({
          ...citation,
          // Evita llenar localStorage con fragmentos PDF excesivamente largos.
          texto: String(citation.texto || "").slice(0, 900),
        })),
        createdAt: new Date().toISOString(),
      };

      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        updatedAt: new Date().toISOString(),
        messages: [...conversation.messages, assistantMessage],
      }));
      setApiStatus("online");
      fetchMetrics();
    } catch (error) {
      const assistantMessage = {
        id: makeId("message"),
        role: "assistant",
        error: true,
        content:
          error?.name === "TimeoutError"
            ? "La consulta tardó más de tres minutos. El backend puede estar cargando modelos o reconstruyendo el índice."
            : error?.message || "No fue posible conectar con el agente.",
        createdAt: new Date().toISOString(),
      };
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        updatedAt: new Date().toISOString(),
        messages: [...conversation.messages, assistantMessage],
      }));
      if (!error?.status || error.status >= 500) setApiStatus("offline");
    } finally {
      setPendingConversationId(null);
      window.setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  if (ticketDraft) {
    return (
      <TicketPage
        draft={ticketDraft}
        apiUrl={API_URL}
        onBack={() => setTicketDraft(null)}
      />
    );
  }

  if (showMetrics) {
    return <MetricsPage apiUrl={API_URL} onBack={() => setShowMetrics(false)} />;
  }

  const areaEntries = Object.values(AREA_META).filter((entry) => entry !== AREA_META.General);

  return (
    <div className="app-shell">
      <AnimatePresence>
        {(historyOpen || policiesOpen || contextOpen) && (
          <motion.button
            aria-label="Cerrar panel"
            className="mobile-backdrop"
            type="button"
            onClick={() => {
              setHistoryOpen(false);
              setPoliciesOpen(false);
              setContextOpen(false);
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
        )}
      </AnimatePresence>

      <aside className="rail">
        <BrandMark compact />
        <button className="rail__icon rail__icon--accent" type="button" onClick={startNewConversation} aria-label="Nueva conversación" title="Nueva conversación">
          <Plus size={19} />
        </button>
        <nav className="rail__nav">
          <button className="rail__icon" type="button" onClick={() => setHistoryOpen(true)} aria-label="Historial" title="Historial">
            <Clock3 size={19} />
          </button>
          <button className="rail__icon" type="button" onClick={() => setPoliciesOpen(true)} aria-label="Políticas" title="Base de políticas">
            <BookOpen size={19} />
          </button>
          <button className="rail__icon" type="button" onClick={() => setShowMetrics(true)} aria-label="Panel de uso" title="Panel de uso">
            <BarChart3 size={19} />
          </button>
          <button className="rail__icon rail__icon--mobile-only" type="button" onClick={() => setContextOpen(true)} aria-label="Contexto" title="Contexto">
            <Menu size={19} />
          </button>
        </nav>
        <div className={`rail__status status-dot--${apiStatus}`} title={apiStatus === "online" ? "Todo en línea" : apiStatus === "checking" ? "Conectando…" : "Sin conexión"} />
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">Copiloto Nexus</span>
            <h2>{activeConversation?.title || "Nueva conversación"}</h2>
          </div>
          <div className="area-chips">
            {areaEntries.map((entry) => (
              <div
                key={entry.short}
                className={`area-chip ${entry.tone} ${currentArea && areaMeta(currentArea).short === entry.short ? "area-chip--active" : ""}`}
              >
                {entry.short}
              </div>
            ))}
          </div>
          <button
            className="top-action"
            type="button"
            onClick={clearCurrentConversation}
            disabled={pending || !activeConversation?.messages.length}
          >
            <RefreshCw size={15} />
            <span>Reiniciar</span>
          </button>
        </header>

        <section className="feed" ref={scrollRef}>
          <div className="feed-inner">
            {!activeConversation?.messages.length ? (
              <WelcomeCard onSuggestion={sendMessage} />
            ) : (
              <AnimatePresence initial={false}>
                {activeConversation.messages.map((message) => (
                  <Message message={message} key={message.id} onOpenTicket={setTicketDraft} />
                ))}
                {pendingConversationId === activeConversation.id && <ThinkingMessage key="thinking" />}
              </AnimatePresence>
            )}
          </div>
        </section>

        <footer className="composer-wrap">
          <div className="composer">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value.slice(0, 1800))}
              onKeyDown={handleKeyDown}
              placeholder="Escribe tu siguiente pregunta…"
              rows={1}
              disabled={pending}
              aria-label="Mensaje"
            />
            <button
              className="send-button"
              type="button"
              onClick={() => sendMessage()}
              disabled={pending || !input.trim()}
              aria-label="Enviar consulta"
            >
              <Send size={17} />
            </button>
          </div>
          <div className="composer-meta">
            <span><ShieldCheck size={12} /> Respuestas verificadas con documentos internos</span>
          </div>
        </footer>
      </main>

      <ContextPanel
        open={contextOpen}
        onClose={() => setContextOpen(false)}
        area={currentArea}
        relatedPolicies={relatedPolicies}
        metrics={metrics}
        onOpenMetrics={() => setShowMetrics(true)}
        apiStatus={apiStatus}
      />

      <HistoryPanel
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        conversations={conversations}
        activeId={activeId}
        pendingId={pendingConversationId}
        onSelect={(id) => {
          setActiveId(id);
          setHistoryOpen(false);
        }}
        onDelete={deleteConversation}
        onNew={startNewConversation}
      />

      <PoliciesPanel
        open={policiesOpen}
        onClose={() => setPoliciesOpen(false)}
        policies={policies}
        status={apiStatus}
      />
    </div>
  );
}
