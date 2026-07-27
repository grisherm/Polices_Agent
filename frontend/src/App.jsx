import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  CircleGauge,
  Database,
  FileText,
  History,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import TicketPage from "./TicketPage";

// En produccion React y FastAPI comparten dominio, por eso la URL base queda
// vacia y las llamadas son relativas (/api/chat, /health, etc.). Vite usa el
// proxy de vite.config.js durante el desarrollo local.
const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const STORAGE_KEY = "alicorp-ai-conversations-v1";
const ACTIVE_KEY = "alicorp-ai-active-conversation-v1";

const SUGGESTIONS = [
  {
    eyebrow: "Ética",
    title: "Compromisos corporativos",
    prompt: "¿Cuáles son los compromisos éticos de Alicorp según su guía?",
    icon: ShieldCheck,
  },
  {
    eyebrow: "Regalos",
    title: "Proveedores y obsequios",
    prompt: "¿Cuáles son los requisitos para aceptar un regalo de un proveedor?",
    icon: Sparkles,
  },
  {
    eyebrow: "Seguridad",
    title: "Protección de información",
    prompt: "¿Qué medidas de seguridad de la información debemos seguir?",
    icon: Database,
  },
  {
    eyebrow: "Cumplimiento",
    title: "Conflictos de interés",
    prompt: "¿Qué indica la política sobre los conflictos de interés?",
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
      <span>A</span>
      <i />
    </div>
  );
}

function StatusPill({ status }) {
  const checking = status === "checking";
  const online = status === "online";
  const Icon = checking ? RefreshCw : online ? Wifi : WifiOff;
  const label = checking ? "Verificando" : online ? "API conectada" : "API sin conexión";

  return (
    <div className={`status-pill status-pill--${status}`}>
      <Icon size={14} className={checking ? "spin" : ""} />
      <span>{label}</span>
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

  return (
    <motion.article
      className={`message ${isUser ? "message--user" : "message--assistant"} ${message.error ? "message--error" : ""
        }`}
      initial={{ opacity: 0, y: 14, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="message__avatar">
        {isUser ? <UserRound size={17} /> : message.error ? <AlertTriangle size={17} /> : <Bot size={18} />}
      </div>
      <div className="message__body">
        <div className="message__topline">
          <strong>{isUser ? "Tú" : "Alicorp IA"}</strong>
          <span>{displayTime(message.createdAt)}</span>
          {!isUser && message.action && (
            <span className={`action-badge action-badge--${action.tone}`}>
              {action.tone === "success" && <Check size={12} />}
              {action.label}
            </span>
          )}
        </div>
        <div className="message__content markdown-body">
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          )}
        </div>
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
      </div>
    </motion.article>
  );
}

function ThinkingMessage() {
  return (
    <motion.div
      className="message message--assistant thinking"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
    >
      <div className="message__avatar">
        <Bot size={18} />
      </div>
      <div className="thinking__card">
        <div className="thinking__dots"><i /><i /><i /></div>
        <span>Consultando políticas y verificando el respaldo…</span>
      </div>
    </motion.div>
  );
}

function Hero({ onSuggestion }) {
  return (
    <motion.div className="hero" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="hero__visual" aria-hidden="true">
        <motion.div
          className="hero__orbit hero__orbit--one"
          animate={{ rotate: 360 }}
          transition={{ duration: 22, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="hero__orbit hero__orbit--two"
          animate={{ rotate: -360 }}
          transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          animate={{ y: [0, -7, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        >
          <BrandMark />
        </motion.div>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
      >
        <span className="hero__kicker"><Sparkles size={14} /> Inteligencia corporativa</span>
        <h1>Decisiones claras,<br /><em>respaldadas por políticas.</em></h1>
        <p>
          Consulta lineamientos internos y recibe respuestas verificadas con sus fuentes documentales.
        </p>
      </motion.div>
      <div className="suggestion-grid">
        {SUGGESTIONS.map((suggestion, index) => {
          const Icon = suggestion.icon;
          return (
            <motion.button
              type="button"
              className="suggestion-card"
              key={suggestion.title}
              onClick={() => onSuggestion(suggestion.prompt)}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.18 + index * 0.06 }}
              whileHover={{ y: -4 }}
              whileTap={{ scale: 0.98 }}
            >
              <span className="suggestion-card__icon"><Icon size={17} /></span>
              <span>
                <small>{suggestion.eyebrow}</small>
                <strong>{suggestion.title}</strong>
              </span>
              <Send size={14} className="suggestion-card__arrow" />
            </motion.button>
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [policiesOpen, setPoliciesOpen] = useState(false);
  const [ticketDraft, setTicketDraft] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) || conversations[0],
    [activeId, conversations],
  );
  const pending = Boolean(pendingConversationId);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    localStorage.setItem(ACTIVE_KEY, activeId);
  }, [activeId, conversations]);

  useEffect(() => {
    if (!conversations.some((conversation) => conversation.id === activeId)) {
      setActiveId(conversations[0]?.id || "");
    }
  }, [activeId, conversations]);

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
    } catch {
      setApiStatus("offline");
      setPolicies([]);
    }
  }, []);

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
    setSidebarOpen(false);
    window.setTimeout(() => textareaRef.current?.focus(), 120);
  }

  useEffect(() => {
    function handleGlobalShortcut(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "n") {
        event.preventDefault();
        startNewConversation();
      }
      if (event.key === "Escape") {
        setSidebarOpen(false);
        setPoliciesOpen(false);
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

  return (
    <div className="app-shell">
      <div className="ambient ambient--one" />
      <div className="ambient ambient--two" />

      <AnimatePresence>
        {sidebarOpen && (
          <motion.button
            aria-label="Cerrar menú"
            className="mobile-backdrop"
            type="button"
            onClick={() => setSidebarOpen(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
        )}
      </AnimatePresence>

      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`}>
        <div className="sidebar__brand">
          <BrandMark compact />
          <div>
            <strong>Alicorp <span>IA</span></strong>
            <small>Asistente normativo</small>
          </div>
          <button
            className="sidebar__close icon-button"
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label="Cerrar menú"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <button className="new-chat" type="button" onClick={startNewConversation}>
          <Plus size={18} />
          Nueva conversación
          <span>⌘ N</span>
        </button>

        <div className="sidebar__section-head">
          <span><History size={14} /> Conversaciones</span>
          <small>{conversations.length}</small>
        </div>

        <nav className="conversation-list" aria-label="Conversaciones">
          {conversations.map((conversation) => (
            <div
              className={`conversation-item ${conversation.id === activeId ? "conversation-item--active" : ""}`}
              key={conversation.id}
            >
              <button
                className="conversation-item__select"
                type="button"
                onClick={() => {
                  setActiveId(conversation.id);
                  setSidebarOpen(false);
                }}
              >
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
                onClick={(event) => deleteConversation(conversation.id, event)}
                disabled={conversation.id === pendingConversationId}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </nav>

        <div className="sidebar__footer">
          <button className="knowledge-card" type="button" onClick={() => setPoliciesOpen(true)}>
            <span><BookOpen size={17} /></span>
            <div>
              <strong>Base de políticas</strong>
              <small>{policies.length ? `${policies.length} documentos activos` : "Consultar cobertura"}</small>
            </div>
            <ChevronDown size={15} className="side-arrow" />
          </button>
          <StatusPill status={apiStatus} />
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar__left">
            <button className="menu-button icon-button" type="button" onClick={() => setSidebarOpen(true)}>
              <Menu size={20} />
            </button>
            <div>
              <span className="eyebrow">Asistente de políticas</span>
              <h2>{activeConversation?.title || "Nueva conversación"}</h2>
            </div>
          </div>
          <div className="topbar__actions">
            <button className="top-action" type="button" onClick={() => setPoliciesOpen(true)}>
              <BookOpen size={16} />
              <span>Políticas</span>
            </button>
            <button
              className="top-action"
              type="button"
              onClick={clearCurrentConversation}
              disabled={pending || !activeConversation?.messages.length}
            >
              <RefreshCw size={16} />
              <span>Reiniciar</span>
            </button>
          </div>
        </header>

        <section className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {!activeConversation?.messages.length ? (
              <Hero onSuggestion={sendMessage} />
            ) : (
              <div className="message-list">
                <AnimatePresence initial={false}>
                  {activeConversation.messages.map((message) => (
                    <Message
                      message={message}
                      key={message.id}
                      onOpenTicket={setTicketDraft}
                    />
                  ))}
                  {pendingConversationId === activeConversation.id && <ThinkingMessage key="thinking" />}
                </AnimatePresence>
              </div>
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
              placeholder="Consulta una política, requisito o procedimiento…"
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
              <Send size={18} />
            </button>
          </div>
          <div className="composer-meta">
            <span><ShieldCheck size={13} /> Respuestas verificadas con documentos internos</span>
            <span>Enter para enviar · Shift + Enter para una línea nueva</span>
          </div>
        </footer>
      </main>

      <PoliciesPanel
        open={policiesOpen}
        onClose={() => setPoliciesOpen(false)}
        policies={policies}
        status={apiStatus}
      />
    </div>
  );
}
