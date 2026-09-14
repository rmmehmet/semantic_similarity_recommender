import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  splitPDF,
  downloadSectionPDF,
  downloadSectionsPDF,
  previewSectionPDF,
  validatePdfFile,
} from "../../../services/service";
import "./PdfSplitter.css";

// ── Navbar ─────────────────────────────────────────────────────────
function Navbar() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const NAV_LINKS = [
    { label: "PDF Bölme", path: "/split" },
    { label: "Benzerlik Arama", path: "/search" },
    { label: "Proje Öneri", path: "/suggest" },
    { label: "Veritabanı",      path: "/database", icon: "⬡" },
  ];
  return (
    <nav className="ps-nav">
      <button className="ps-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
        <span className="ps-nav__logo-mark">A</span>
        <span className="ps-nav__logo-text">Altay<em>AI</em></span>
      </button>
      <ul className={`ps-nav__links${menuOpen ? " open" : ""}`}>
        {NAV_LINKS.map(l => (
          <li key={l.path}>
            <button
              className={`ps-nav__link${l.path === "/split" ? " active" : ""}`}
              onClick={() => { navigate(l.path); setMenuOpen(false); }}
            >
              {l.label}
            </button>
          </li>
        ))}
      </ul>
      <button className="ps-nav__burger" onClick={() => setMenuOpen(p => !p)}>
        <span /><span /><span />
      </button>
    </nav>
  );
}

// ── PDF Önizleme Modal ─────────────────────────────────────────────
function PreviewModal({ section, file, onClose, onDownload }) {
  const [pdfUrl, setPdfUrl]     = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const urlRef = useRef(null);

  useEffect(() => {
    if (!section || !file) return;
    setLoading(true);
    setError(null);
    setPdfUrl(null);

    previewSectionPDF(file, section)
      .then(url => {
        urlRef.current = url;
        setPdfUrl(url);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));

    return () => {
      if (urlRef.current) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    };
  }, [section, file]);

  if (!section) return null;

  return (
    <div className="ps-modal-overlay" onClick={onClose}>
      <div className="ps-modal" onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="ps-modal__header">
          <div className="ps-modal__header-left">
            <span className="ps-modal__tag">PDF Önizleme</span>
            <h2 className="ps-modal__title">{section.title}</h2>
          </div>
          <button className="ps-modal__close" onClick={onClose}>
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Meta */}
        <div className="ps-modal__meta">
          {[
            { label: "Sayfa Aralığı", val: `${section.start_page} – ${section.end_page}` },
            { label: "Toplam Sayfa",  val: section.pages?.length || 0 },
            { label: "Font Eşiği",    val: `${section.font_size}pt` },
            { label: "Bölüm No",      val: `#${section.id?.replace("section_", "") || "—"}` },
          ].map(m => (
            <div className="ps-modal__meta-item" key={m.label}>
              <span className="ps-modal__meta-label">{m.label}</span>
              <span className="ps-modal__meta-val">{m.val}</span>
            </div>
          ))}
        </div>

        {/* PDF Viewer */}
        <div className="ps-modal__viewer">
          {loading && (
            <div className="ps-modal__viewer-state">
              <div className="ps-drop__spinner" />
              <span>PDF yükleniyor…</span>
            </div>
          )}
          {error && (
            <div className="ps-modal__viewer-state ps-modal__viewer-state--error">
              <svg viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8"/>
                <line x1="12" y1="7" x2="12" y2="13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                <circle cx="12" cy="16.5" r="1" fill="currentColor"/>
              </svg>
              <span>{error}</span>
            </div>
          )}
          {pdfUrl && !loading && (
            <iframe
              src={pdfUrl}
              className="ps-modal__iframe"
              title={section.title}
            />
          )}
        </div>

        {/* Footer */}
        <div className="ps-modal__footer">
          <button className="ps-btn ps-btn--ghost" onClick={onClose}>Kapat</button>
          <button
            className="ps-btn ps-btn--primary"
            onClick={() => onDownload(section)}
          >
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M10 3v10M5 13l5 4 5-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <line x1="3" y1="18" x2="17" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            PDF İndir
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Section Card ───────────────────────────────────────────────────
function SectionCard({ section, index, selected, onToggle, onPreview, onDownload }) {
  return (
    <div className={`ps-card${selected ? " ps-card--selected" : ""}`}>
      {/* Checkbox */}
      <div className="ps-card__check" onClick={() => onToggle(section.id)}>
        <div className={`ps-card__checkbox${selected ? " checked" : ""}`}>
          {selected && (
            <svg viewBox="0 0 12 12" fill="none">
              <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="ps-card__body">
        <div className="ps-card__top">
          <span className="ps-card__index">{String(index + 1).padStart(2, "0")}</span>
          <h3 className="ps-card__title">{section.title || "Başlıksız Bölüm"}</h3>
        </div>
        <div className="ps-card__meta">
          <span className="ps-card__meta-chip">
            <svg viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
              <line x1="4" y1="5" x2="10" y2="5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
              <line x1="4" y1="7.5" x2="10" y2="7.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
              <line x1="4" y1="10" x2="7" y2="10" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
            </svg>
            {section.pages?.length || 0} sayfa
          </span>
          <span className="ps-card__meta-chip">
            s.{section.start_page} – {section.end_page}
          </span>
          <span className="ps-card__meta-chip ps-card__meta-chip--accent">
            {section.font_size}pt
          </span>
        </div>
        <p className="ps-card__preview">
          {section.content?.slice(0, 140).trim()}{section.content?.length > 140 ? "…" : ""}
        </p>
      </div>

      {/* Actions */}
      <div className="ps-card__actions">
        <button className="ps-card__action-btn" onClick={() => onPreview(section)}>
          <svg viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.8"/>
            <path d="M2 10C4 5.5 7 3 10 3s6 2.5 8 7c-2 4.5-5 7-8 7s-6-2.5-8-7z" stroke="currentColor" strokeWidth="1.8"/>
          </svg>
          İncele
        </button>
        <button className="ps-card__action-btn ps-card__action-btn--dl" onClick={() => onDownload(section)}>
          <svg viewBox="0 0 20 20" fill="none">
            <path d="M10 3v10M5 13l5 4 5-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            <line x1="3" y1="18" x2="17" y2="18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
          PDF İndir
        </button>
      </div>
    </div>
  );
}

// ── Drop Zone ──────────────────────────────────────────────────────
function DropZone({ onFile, loading, onError }) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);
  const handle = useCallback(f => {
    if (!f) return;
    const err = validatePdfFile(f);
    if (err) { onError?.(err); return; }
    onFile(f);
  }, [onFile, onError]);

  return (
    <div
      className={`ps-drop${drag ? " ps-drop--drag" : ""}${loading ? " ps-drop--loading" : ""}`}
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
      onClick={() => !loading && inputRef.current?.click()}
    >
      <input ref={inputRef} type="file" accept=".pdf" style={{ display: "none" }}
        onChange={e => handle(e.target.files[0])} />

      {loading ? (
        <div className="ps-drop__loading">
          <div className="ps-drop__spinner" />
          <span>PDF analiz ediliyor…</span>
        </div>
      ) : (
        <>
          <div className="ps-drop__icon">
            <svg viewBox="0 0 64 64" fill="none">
              <rect x="10" y="6" width="34" height="46" rx="3" stroke="currentColor" strokeWidth="2.5"/>
              <rect x="20" y="14" width="34" height="46" rx="3" stroke="currentColor" strokeWidth="2" strokeDasharray="5 3" opacity=".5"/>
              <line x1="18" y1="22" x2="36" y2="22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <line x1="18" y1="30" x2="36" y2="30" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <line x1="18" y1="38" x2="28" y2="38" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M42 38v14M36 45l6 7 6-7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div className="ps-drop__text">
            <span className="ps-drop__main">PDF dosyanızı buraya sürükleyin</span>
            <span className="ps-drop__sub">veya tıklayarak seçin</span>
          </div>
          <div className="ps-drop__hint">Yalnızca .pdf formatı desteklenir</div>
        </>
      )}
    </div>
  );
}

// ── Ana Bileşen ────────────────────────────────────────────────────
export default function PdfSplitter() {
  const [file, setFile]           = useState(null);
  const [sections, setSections]   = useState([]);
  const [selected, setSelected]   = useState(new Set());
  const [preview, setPreview]     = useState(null);
  const [loading, setLoading]     = useState(false);
  const [dlLoading, setDlLoading] = useState(false);
  const [error, setError]         = useState(null);
  const [threshold, setThreshold] = useState(22);

  const handleFile = useCallback(async f => {
    setFile(f);
    setSections([]);
    setSelected(new Set());
    setError(null);
    setLoading(true);
    try {
      const data = await splitPDF(f, threshold);
      if (!data.success) throw new Error(data.error || "PDF bölme başarısız");
      setSections(data.sections || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [threshold]);

  const toggleSelect = id =>
    setSelected(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const toggleAll = () =>
    setSelected(selected.size === sections.length ? new Set() : new Set(sections.map(s => s.id)));

  // Seçili bölümleri PDF olarak sırayla indir
  const handleDownloadSelected = async () => {
    if (!file || selected.size === 0) return;
    setDlLoading(true);
    try {
      const sel = sections.filter(s => selected.has(s.id));
      await downloadSectionsPDF(file, sel);
    } catch (e) {
      setError(e.message);
    } finally {
      setDlLoading(false);
    }
  };

  // Tek bölüm indir
  const handleDownloadOne = async section => {
    if (!file) return;
    try {
      await downloadSectionPDF(file, section);
    } catch (e) {
      setError(e.message);
    }
  };

  const reset = () => { setFile(null); setSections([]); setSelected(new Set()); setError(null); };

  const selectedSections = sections.filter(s => selected.has(s.id));

  return (
    <div className="ps-root">
      <Navbar />

      {/* Page Header */}
      <div className="ps-header">
        <div className="ps-header__inner">
          <div className="ps-header__breadcrumb">
            <span>AltayAI</span>
            <svg viewBox="0 0 12 12" fill="none">
              <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span className="active">PDF Bölme</span>
          </div>
          <h1 className="ps-header__title">PDF <span>Bölme</span> Aracı</h1>
          <p className="ps-header__sub">
            Bildiri kitaplarını font büyüklüğü analizine göre otomatik bölümlere ayırın
          </p>
        </div>
      </div>

      <div className="ps-layout">
        {/* ── Sidebar ── */}
        <aside className="ps-sidebar">
          <div className="ps-sidebar__card">
            <div className="ps-sidebar__section-label">Dosya Yükle</div>
            <DropZone onFile={handleFile} loading={loading} onError={setError} />
            {file && !loading && (
              <div className="ps-sidebar__file-info">
                <div className="ps-sidebar__file-icon">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.8"/>
                    <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                  </svg>
                </div>
                <div className="ps-sidebar__file-meta">
                  <span className="ps-sidebar__file-name">{file.name}</span>
                  <span className="ps-sidebar__file-size">{(file.size/1024/1024).toFixed(2)} MB</span>
                </div>
                <button className="ps-sidebar__file-remove" onClick={reset}>
                  <svg viewBox="0 0 16 16" fill="none">
                    <path d="M4 4l8 8M12 4L4 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            )}
          </div>

          <div className="ps-sidebar__card">
            <div className="ps-sidebar__section-label">Font Eşiği</div>
            <div className="ps-sidebar__threshold">
              <input type="range" min="8" max="48" step="1" value={threshold}
                onChange={e => setThreshold(Number(e.target.value))} className="ps-slider" />
              <div className="ps-sidebar__threshold-val">
                <span className="ps-sidebar__threshold-num">{threshold}</span>
                <span className="ps-sidebar__threshold-unit">pt</span>
              </div>
            </div>
            <p className="ps-sidebar__hint">Bu değerin üzerindeki font boyutları başlık olarak algılanır.</p>
            {file && !loading && (
              <button className="ps-btn ps-btn--secondary ps-btn--full" onClick={() => handleFile(file)}>
                <svg viewBox="0 0 20 20" fill="none">
                  <path d="M17 10A7 7 0 113 10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                  <path d="M17 4v6h-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Yeniden Analiz Et
              </button>
            )}
          </div>

          {sections.length > 0 && (
            <div className="ps-sidebar__card ps-sidebar__stats">
              <div className="ps-stat-row">
                <span className="ps-stat-label">Toplam Bölüm</span>
                <span className="ps-stat-val">{sections.length}</span>
              </div>
              <div className="ps-stat-row">
                <span className="ps-stat-label">Seçili</span>
                <span className="ps-stat-val ps-stat-val--cyan">{selected.size}</span>
              </div>
              <div className="ps-stat-row">
                <span className="ps-stat-label">Toplam Sayfa</span>
                <span className="ps-stat-val">{sections.reduce((a, s) => a + (s.pages?.length || 0), 0)}</span>
              </div>
            </div>
          )}
        </aside>

        {/* ── Main ── */}
        <main className="ps-main">
          {error && (
            <div className="ps-error">
              <svg viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.8"/>
                <line x1="10" y1="6" x2="10" y2="11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                <circle cx="10" cy="14" r=".8" fill="currentColor"/>
              </svg>
              {error}
              <button className="ps-error__close" onClick={() => setError(null)}>✕</button>
            </div>
          )}

          {sections.length === 0 && !loading && (
            <div className="ps-empty">
              <div className="ps-empty__icon">
                <svg viewBox="0 0 80 80" fill="none">
                  <rect x="12" y="8" width="42" height="56" rx="4" stroke="currentColor" strokeWidth="2" opacity=".3"/>
                  <rect x="24" y="18" width="42" height="56" rx="4" stroke="currentColor" strokeWidth="2" strokeDasharray="6 3" opacity=".15"/>
                  <path d="M26 28h20M26 36h20M26 44h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity=".25"/>
                </svg>
              </div>
              <p className="ps-empty__text">PDF yükleyerek bölümleri görüntüleyin</p>
              <p className="ps-empty__sub">Font büyüklüğüne göre otomatik bölümlendirme yapılacak</p>
            </div>
          )}

          {sections.length > 0 && (
            <>
              {/* Toolbar */}
              <div className="ps-toolbar">
                <div className="ps-toolbar__left">
                  <button className="ps-toolbar__select-all" onClick={toggleAll}>
                    <div className={`ps-card__checkbox${selected.size === sections.length ? " checked" : ""}`}>
                      {selected.size === sections.length && (
                        <svg viewBox="0 0 12 12" fill="none">
                          <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </div>
                    Tümünü Seç
                  </button>
                  <span className="ps-toolbar__count">{sections.length} bölüm</span>
                </div>

                {/* Seçili bölümleri ayrı ayrı göster + toplu indir */}
                {selected.size > 0 && (
                  <div className="ps-toolbar__right">
                    <div className="ps-toolbar__selected-pills">
                      {selectedSections.map(s => (
                        <span key={s.id} className="ps-pill">
                          <svg viewBox="0 0 12 12" fill="none">
                            <rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
                          </svg>
                          {String(sections.indexOf(s) + 1).padStart(2, "0")}
                        </span>
                      ))}
                    </div>
                    <button
                      className="ps-btn ps-btn--primary"
                      onClick={handleDownloadSelected}
                      disabled={dlLoading}
                    >
                      {dlLoading ? (
                        <span className="ps-btn-spinner" />
                      ) : (
                        <svg viewBox="0 0 20 20" fill="none">
                          <path d="M10 3v10M5 13l5 4 5-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          <line x1="3" y1="18" x2="17" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      )}
                      {selected.size} PDF İndir
                    </button>
                  </div>
                )}
              </div>

              {/* Section Cards */}
              <div className="ps-cards">
                {sections.map((s, i) => (
                  <SectionCard
                    key={s.id}
                    section={s}
                    index={i}
                    selected={selected.has(s.id)}
                    onToggle={toggleSelect}
                    onPreview={setPreview}
                    onDownload={handleDownloadOne}
                  />
                ))}
              </div>
            </>
          )}
        </main>
      </div>

      {/* Preview Modal */}
      <PreviewModal
        section={preview}
        file={file}
        onClose={() => setPreview(null)}
        onDownload={handleDownloadOne}
      />
    </div>
  );
}