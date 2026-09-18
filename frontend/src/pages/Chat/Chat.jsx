import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  dbListPdfs,
  streamChatMessage,
  listConversations,
  getConversation,
  deleteConversation,
} from "../../../services/service";
import UserMenu from "../../UserMenu";
import "./Chat.css";

const ACTIVE_CONVERSATION_KEY = "altayai_chat_active_conversation";

const NAV_LINKS = [
  ["PDF Bölme", "/split"],
  ["PDF Sohbet", "/chat"],
  ["Proje Öneri", "/suggest"],
  ["Kütüphanem", "/database"],
];

const EXAMPLE_PROMPTS = [
  "Bana dronlarda görüntü işleme ile ilgili projeleri getir",
  "Bu belgenin özetini çıkar",
  "Kullanılan yöntemleri karşılaştır",
];

// ── Navbar ─────────────────────────────────────────────────────────
function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <nav className="chat-nav">
      <button className="chat-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
        <span className="chat-logo-hex">A</span>
        <span className="chat-nav__brand">Altay<em>AI</em></span>
      </button>
      <ul className={`chat-nav__links${open ? " open" : ""}`}>
        {NAV_LINKS.map(([label, path]) => (
          <li key={path}>
            <button
              className={`chat-nav__link${path === "/chat" ? " active" : ""}`}
              onClick={() => { navigate(path); setOpen(false); }}
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <UserMenu />
        <button className="chat-nav__burger" onClick={() => setOpen((v) => !v)} aria-label="Menü">
          <span /><span /><span />
        </button>
      </div>
    </nav>
  );
}

// ── PDF seçim ikonu ─────────────────────────────────────────────────
function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" fill="none">
      <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
      <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 14 14" fill="none" width="12" height="12">
      <path
        d="M2.5 3.5h9M5.5 3.5V2h3v1.5M3.5 3.5l.5 8.5h6l.5-8.5"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

// ── Sohbet geçmişi listesi ────────────────────────────────────────
function HistoryPanel({ conversations, loading, activeId, onSelect, onNew, onDelete }) {
  return (
    <div className="chat-history">
      <div className="chat-history__head">
        <div className="chat-sidebar__title">Sohbetlerim</div>
        <button className="chat-history__new" onClick={onNew}>
          <PlusIcon /> Yeni Sohbet
        </button>
      </div>
      <div className="chat-history__list">
        {loading && <div className="chat-sidebar__empty">Yükleniyor…</div>}
        {!loading && conversations.length === 0 && (
          <div className="chat-sidebar__empty">Henüz sohbetin yok.</div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`chat-history-item${c.id === activeId ? " active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="chat-history-item__title">{c.title}</span>
            <button
              className="chat-history-item__del"
              title="Sohbeti sil"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
            >
              <TrashIcon />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sidebar: kullanıcının PDF'lerini seçme ──────────────────────────
function Sidebar({ docs, loading, selected, onToggle, onClear, open, history }) {
  const [q, setQ] = useState("");
  const filtered = docs.filter((d) => {
    const s = q.trim().toLowerCase();
    if (!s) return true;
    return (d.raw_title || "").toLowerCase().includes(s) || d.pdf_name.toLowerCase().includes(s);
  });

  return (
    <aside className={`chat-sidebar${open ? " open" : ""}`}>
      {history}
      <div className="chat-sidebar__head">
        <div className="chat-sidebar__title">Belgelerim</div>
        <div className="chat-sidebar__hint">
          Belge seç, sadece onlar hakkında konuş — seçmezsen tüm belgelerinde arama yapılır.
        </div>
      </div>

      <input
        className="chat-sidebar__search"
        placeholder="Belge ara…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      <div className="chat-sidebar__list">
        {loading && <div className="chat-sidebar__empty">Yükleniyor…</div>}
        {!loading && filtered.length === 0 && (
          <div className="chat-sidebar__empty">
            {docs.length === 0 ? "Henüz PDF yüklemedin." : "Eşleşen belge yok."}
          </div>
        )}
        {filtered.map((d) => {
          const isSel = selected.has(d.pdf_name);
          return (
            <div
              key={d.pdf_name}
              className={`chat-pdf-item${isSel ? " selected" : ""}`}
              onClick={() => onToggle(d.pdf_name)}
            >
              <span className="chat-pdf-item__box">{isSel && <CheckIcon />}</span>
              <span className="chat-pdf-item__text">
                <span className="chat-pdf-item__title">{d.raw_title || d.pdf_name}</span>
                <span className="chat-pdf-item__name">{d.pdf_name}</span>
              </span>
            </div>
          );
        })}
      </div>

      {selected.size > 0 && (
        <div className="chat-sidebar__foot">
          <button className="chat-sidebar__clear" onClick={onClear}>
            Seçimi Temizle ({selected.size})
          </button>
        </div>
      )}
    </aside>
  );
}

// ── Kaynak PDF çipi ──────────────────────────────────────────────────
function SourceChip({ source }) {
  return (
    <span className="chat-source-chip" title={source.raw_title}>
      <svg viewBox="0 0 16 16" fill="none">
        <path d="M9 2H4a1 1 0 00-1 1v10a1 1 0 001 1h8a1 1 0 001-1V6L9 2z" stroke="currentColor" strokeWidth="1.4" />
        <path d="M9 2v4h4" stroke="currentColor" strokeWidth="1.4" />
      </svg>
      <span>{source.raw_title}</span>
    </span>
  );
}

// ── Ana Bileşen ────────────────────────────────────────────────────
export default function Chat() {
  const [docs, setDocs] = useState([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [messages, setMessages] = useState([]); // {role, content, sources?, error?}
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  // ChatGPT'deki gibi: bu sayfadayken tarayıcı sayfasının (<body>) kendisi
  // ASLA kaymasın — tüm kaydırma sadece .chat-messages/.chat-sidebar__list
  // gibi iç panellerin içinde olsun. CSS tarafında (.chat-root, .chat-main,
  // .chat-sidebar) zincirin her yerinde min-height:0/overflow:hidden zaten
  // var, ama bazı tarayıcılarda/durumlarda <body> yine de birkaç pikselik
  // bir taşmayla kayabiliyordu — bu, olası tüm CSS senaryolarına karşı
  // kesin/garanti bir çözüm: sayfa mount olduğunda body'nin kendi
  // scroll'unu devre dışı bırakır, sayfadan çıkınca (başka bir route'a
  // geçince) eski haline geri döndürür.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    const prevHeight   = document.body.style.height;
    const prevMargin   = document.body.style.margin;
    document.body.style.overflow = "hidden";
    document.body.style.height   = "100vh";
    document.body.style.margin   = "0";
    return () => {
      document.body.style.overflow = prevOverflow;
      document.body.style.height   = prevHeight;
      document.body.style.margin   = prevMargin;
    };
  }, []);

  const refreshConversations = useCallback(() => {
    listConversations()
      .then((res) => setConversations(res.conversations || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let ignore = false;
    dbListPdfs(500)
      .then((res) => { if (!ignore) setDocs(res.documents || []); })
      .catch(() => { if (!ignore) setDocs([]); })
      .finally(() => { if (!ignore) setDocsLoading(false); });
    return () => { ignore = true; };
  }, []);

  // Sohbet listesi + (varsa) sayfa yenilenmeden önce aktif olan sohbetin
  // geri yüklenmesi — refresh/remount sonrası sohbetin kaybolmamasının
  // tek kaynağı burasıdır.
  useEffect(() => {
    let ignore = false;

    listConversations()
      .then((res) => { if (!ignore) setConversations(res.conversations || []); })
      .catch(() => {})
      .finally(() => { if (!ignore) setConversationsLoading(false); });

    const storedId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);
    if (storedId) {
      getConversation(storedId)
        .then((conv) => {
          if (ignore) return;
          setActiveConversationId(conv.id);
          setSelected(new Set(conv.pdf_names || []));
          setMessages(
            (conv.messages || []).map((m) => ({
              role: m.role,
              content: m.content,
              sources: m.sources || [],
            })),
          );
        })
        .catch(() => {
          localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
        });
    }

    return () => { ignore = true; };
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Stream sırasında (sending=true) her delta ayrı bir render/efekt tetikliyor —
    // "smooth" kaydırma art arda çok hızlı çağrılınca her seferinde bir önceki
    // animasyonu yarıda kesip yeniden başlatıyor, bu da kullanıcının elle aşağı
    // itmesi gerekiyormuş gibi bir gecikme/duraksama izlenimi veriyordu. Stream
    // sırasında anlık (instant) kaydırma kullanılıyor; mesaj tamamlandığında/
    // yeni bir mesaj eklendiğinde yumuşak kaydırma korunuyor.
    el.scrollTo({ top: el.scrollHeight, behavior: sending ? "instant" : "smooth" });
  }, [messages, sending]);

  const toggleDoc = useCallback((pdfName) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(pdfName) ? next.delete(pdfName) : next.add(pdfName);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelected(new Set()), []);

  const startNewChat = useCallback(() => {
    setMessages([]);
    setSelected(new Set());
    setActiveConversationId(null);
    localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }, []);

  const selectConversation = useCallback((id) => {
    if (id === activeConversationId) return;
    getConversation(id)
      .then((conv) => {
        setActiveConversationId(conv.id);
        setSelected(new Set(conv.pdf_names || []));
        setMessages(
          (conv.messages || []).map((m) => ({
            role: m.role,
            content: m.content,
            sources: m.sources || [],
          })),
        );
        localStorage.setItem(ACTIVE_CONVERSATION_KEY, String(conv.id));
        setSidebarOpen(false);
      })
      .catch(() => {
        refreshConversations();
      });
  }, [activeConversationId, refreshConversations]);

  const removeConversation = useCallback((id) => {
    deleteConversation(id)
      .then(() => {
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (id === activeConversationId) {
          startNewChat();
        }
      })
      .catch(() => {});
  }, [activeConversationId, startNewChat]);

  // Akan yanıtın son mesaja (asistan balonu) yazılması — hep dizideki SON
  // öğeyi hedefler, bu yüzden çağıran taraf balonu ekledikten hemen sonra
  // başka bir setMessages araya girmemelidir (send() bu sırayı korur).
  const appendToLastAssistant = useCallback((patch) => {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant" && last.streaming) {
        next[next.length - 1] = typeof patch === "function" ? patch(last) : { ...last, ...patch };
      }
      return next;
    });
  }, []);

  const send = useCallback(async (text) => {
    const trimmed = (text ?? input).trim();
    if (!trimmed || sending) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "", sources: [], streaming: true },
    ]);
    setInput("");
    setSending(true);

    try {
      await streamChatMessage(trimmed, Array.from(selected), activeConversationId, {
        onChunk: (delta) => {
          appendToLastAssistant((last) => ({ ...last, content: last.content + delta }));
        },
        onDone: (data) => {
          appendToLastAssistant({ streaming: false, sources: data.sources || [] });
          if (data.conversation_id && data.conversation_id !== activeConversationId) {
            setActiveConversationId(data.conversation_id);
            localStorage.setItem(ACTIVE_CONVERSATION_KEY, String(data.conversation_id));
          }
          refreshConversations();
        },
        onError: (msg) => {
          appendToLastAssistant((last) => ({
            ...last,
            streaming: false,
            error: true,
            content: last.content || msg || "Bir hata oluştu.",
          }));
        },
      });
    } catch (err) {
      const msg = err?.message || "Sunucuya bağlanılamadı.";
      appendToLastAssistant((last) => ({ ...last, streaming: false, error: true, content: last.content || msg }));
    } finally {
      setSending(false);
    }
  }, [input, sending, selected, activeConversationId, refreshConversations, appendToLastAssistant]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const autoGrow = (e) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const selectedTitles = docs.filter((d) => selected.has(d.pdf_name));

  return (
    <div className="chat-root">
      <Navbar />

      <div className="chat-layout">
        <Sidebar
          docs={docs}
          loading={docsLoading}
          selected={selected}
          onToggle={toggleDoc}
          onClear={clearSelection}
          open={sidebarOpen}
          history={
            <HistoryPanel
              conversations={conversations}
              loading={conversationsLoading}
              activeId={activeConversationId}
              onSelect={selectConversation}
              onNew={startNewChat}
              onDelete={removeConversation}
            />
          }
        />

        <main className="chat-main">
          <div className="chat-main__head">
            <button className="chat-main__docs-toggle" onClick={() => setSidebarOpen((v) => !v)}>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
              Belgeler
            </button>
            <div className="chat-main__scope">
              {selected.size === 0 ? (
                <span>Kapsam: <strong style={{ color: "var(--text)" }}>Tüm belgelerim</strong></span>
              ) : (
                <>
                  <span>Kapsam:</span>
                  {selectedTitles.slice(0, 3).map((d) => (
                    <span className="chat-main__scope-chip" key={d.pdf_name}>
                      {d.raw_title || d.pdf_name}
                    </span>
                  ))}
                  {selected.size > 3 && <span className="chat-main__scope-chip">+{selected.size - 3}</span>}
                </>
              )}
            </div>
            {messages.length > 0 && (
              <button className="chat-main__new" onClick={startNewChat}>
                <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                  <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
                Yeni Sohbet
              </button>
            )}
          </div>

          <div className="chat-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="chat-empty">
                <svg className="chat-empty__icon" viewBox="0 0 48 48" fill="none">
                  <path d="M8 10h32v22H18l-8 8V10z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
                  <line x1="14" y1="18" x2="34" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <line x1="14" y1="25" x2="26" y2="25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                <div className="chat-empty__title">Belgelerinle sohbet et</div>
                <p className="chat-empty__sub">
                  Soldan bir veya birkaç PDF seç ve sadece onlar hakkında konuş,
                  ya da hiçbir şey seçmeden tüm kütüphanende arama yapan genel bir soru sor.
                </p>
                <div className="chat-empty__examples">
                  {EXAMPLE_PROMPTS.map((p) => (
                    <button key={p} className="chat-empty__example" onClick={() => send(p)}>
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`chat-row chat-row--${m.role}`}>
                {m.streaming && !m.content ? (
                  <div className="chat-typing">
                    <span /><span /><span />
                  </div>
                ) : (
                  <div className={`chat-bubble chat-bubble--${m.role}${m.error ? " chat-bubble--error" : ""}`}>
                    {m.content}
                    {m.streaming && <span className="chat-cursor" aria-hidden="true" />}
                    {m.sources && m.sources.length > 0 && (
                      <div className="chat-sources">
                        {m.sources.map((s) => (
                          <SourceChip key={s.pdf_name} source={s} />
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="chat-inputbar">
            <textarea
              ref={textareaRef}
              className="chat-inputbar__field"
              placeholder="Belgelerin hakkında bir şey sor… (Enter ile gönder, Shift+Enter yeni satır)"
              value={input}
              onChange={autoGrow}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button className="chat-inputbar__send" onClick={() => send()} disabled={!input.trim() || sending}>
              <svg viewBox="0 0 20 20" fill="none" width="18" height="18">
                <path d="M3 10h13M10 4l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}
