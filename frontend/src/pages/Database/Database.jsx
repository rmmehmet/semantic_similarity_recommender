import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  dbAddPdf,
  dbRemovePdf,
  dbStats,
  dbListPdfs,
  dbGetDetail,
  dbReset,
} from "../../../services/service";
import "./Database.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ══════════════════════════════════════════════════════════════════
// NAVBAR
// ══════════════════════════════════════════════════════════════════
function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const links = [
    ["PDF Bölme", "/split"],
    ["Benzerlik Arama", "/search"],
    ["Proje Öneri", "/suggest"],
    ["Veritabanı", "/database"],
  ];
  return (
    <nav className="db-nav">
      <div className="db-nav__logo" onClick={() => navigate("/")}>
        <span className="db-logo-hex">A</span>
        <span className="db-nav__brand">
          Altay<em>AI</em>
        </span>
      </div>
      <ul className={`db-nav__links${open ? " open" : ""}`}>
        {links.map(([l, p]) => (
          <li key={p}>
            <button
              className={`db-nav__link${p === "/database" ? " active" : ""}`}
              onClick={() => {
                navigate(p);
                setOpen(false);
              }}
            >
              {l}
            </button>
          </li>
        ))}
      </ul>
      <button className="db-nav__burger" onClick={() => setOpen((v) => !v)}>
        <span />
        <span />
        <span />
      </button>
    </nav>
  );
}

// ══════════════════════════════════════════════════════════════════
// STAT KARTI
// ══════════════════════════════════════════════════════════════════
function StatCard({ label, value, sub, color, icon }) {
  return (
    <div className="db-stat-card">
      <div className="db-stat-card__icon" style={{ background: `${color}18`, color }}>
        {icon}
      </div>
      <div className="db-stat-card__body">
        <span className="db-stat-card__val">{value ?? "—"}</span>
        <span className="db-stat-card__label">{label}</span>
        {sub && <span className="db-stat-card__sub">{sub}</span>}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// DROP ZONE
// ══════════════════════════════════════════════════════════════════
function PdfDropZone({ files, onFiles }) {
  const [drag, setDrag] = useState(false);
  const ref = useRef(null);

  const handle = useCallback(
    (fileList) => {
      const pdfs = Array.from(fileList).filter((f) => f.type === "application/pdf");
      if (pdfs.length)
        onFiles((prev) => {
          const names = new Set(prev.map((f) => f.name));
          return [...prev, ...pdfs.filter((f) => !names.has(f.name))];
        });
    },
    [onFiles]
  );

  return (
    <div
      className={`db-drop${drag ? " drag" : ""}${files.length ? " has-files" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        handle(e.dataTransfer.files);
      }}
      onClick={() => !files.length && ref.current?.click()}
    >
      <input
        ref={ref}
        type="file"
        accept=".pdf"
        multiple
        style={{ display: "none" }}
        onChange={(e) => handle(e.target.files)}
      />

      {files.length === 0 ? (
        <div className="db-drop__empty">
          <div className="db-drop__empty-icon">
            <svg viewBox="0 0 56 56" fill="none">
              <rect x="8" y="4" width="32" height="44" rx="3" stroke="currentColor" strokeWidth="1.6" opacity=".35" />
              <path d="M32 4v12h12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity=".35" />
              <circle cx="40" cy="40" r="14" fill="var(--db-bg2)" stroke="#F59E0B" strokeWidth="1.8" />
              <path d="M40 33v7M40 33l-3 3M40 33l3 3" stroke="#F59E0B" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              <line x1="35" y1="43" x2="45" y2="43" stroke="#F59E0B" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </div>
          <p className="db-drop__label">PDF dosyalarını sürükle veya tıkla</p>
          <p className="db-drop__sub">Birden fazla PDF · Otomatik BERT indeksleme</p>
        </div>
      ) : (
        <div className="db-drop__filelist" onClick={(e) => e.stopPropagation()}>
          {files.map((f, i) => (
            <div key={f.name} className="db-drop__file">
              <svg viewBox="0 0 20 20" fill="none" className="db-drop__file-icon">
                <path d="M12 2H5a1 1 0 00-1 1v14a1 1 0 001 1h10a1 1 0 001-1V7l-4-5z" stroke="currentColor" strokeWidth="1.4" />
                <path d="M12 2v5h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
              <span className="db-drop__file-name">{f.name}</span>
              <span className="db-drop__file-size">{(f.size / 1024 / 1024).toFixed(2)} MB</span>
              <button className="db-drop__file-rm" onClick={() => onFiles((prev) => prev.filter((_, j) => j !== i))}>
                <svg viewBox="0 0 12 12" fill="none">
                  <path d="M2 2l8 8M10 2L2 10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          ))}
          <button className="db-drop__add-more" onClick={() => ref.current?.click()}>
            + Daha fazla PDF ekle
          </button>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// UPLOAD SATIRI
// ══════════════════════════════════════════════════════════════════
function UploadRow({ file, status, result, error }) {
  return (
    <div className={`db-upload-row db-upload-row--${status}`}>
      <div className="db-upload-row__icon">
        {status === "done" && <span className="db-icon-ok">✓</span>}
        {status === "error" && <span className="db-icon-err">✕</span>}
        {status === "uploading" && <span className="db-spin-sm" />}
        {status === "pending" && <span className="db-icon-wait">○</span>}
      </div>
      <div className="db-upload-row__info">
        <span className="db-upload-row__name">{file.name}</span>
        {status === "done" && result && (
          <span className="db-upload-row__detail">
            ✓ {result.chunks} chunk · {result.title?.slice(0, 60)}
          </span>
        )}
        {status === "error" && (
          <span className="db-upload-row__detail db-upload-row__detail--err">{error}</span>
        )}
        {status === "uploading" && <span className="db-upload-row__detail">İşleniyor…</span>}
        {status === "pending" && <span className="db-upload-row__detail">Sırada</span>}
      </div>
      <span className="db-upload-row__size">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// PDF LİSTE SATIRI
// ══════════════════════════════════════════════════════════════════
function PdfRow({ doc, index, onDelete, onDetail, onPreview }) {
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (!confirm) { setConfirm(true); return; }
    setDeleting(true);
    await onDelete(doc.pdf_name);
    setDeleting(false);
  };

  return (
    <div className="db-pdf-row">
      <span className="db-pdf-row__num">{String(index).padStart(2, "0")}</span>

      <div className="db-pdf-row__body" onClick={() => onDetail(doc.pdf_name)}>
        <span className="db-pdf-row__title">{doc.raw_title || doc.pdf_name}</span>
        <div className="db-pdf-row__meta">
          <span className="db-pdf-row__name">{doc.pdf_name}</span>
          {doc.book_name && <span className="db-pdf-row__tag">{doc.book_name}</span>}
          {doc.year > 0 && <span className="db-pdf-row__year">{doc.year}</span>}
          {doc.abstract_len > 0 && (
            <span className="db-pdf-row__badge db-pdf-row__badge--abs">
              özet {doc.abstract_len}k
            </span>
          )}
          {doc.fulltext_len > 0 && (
            <span className="db-pdf-row__badge db-pdf-row__badge--ft">
              metin {Math.round(doc.fulltext_len / 1000)}k
            </span>
          )}
        </div>
      </div>

      {/* Önizleme butonu */}
      <button
        className="db-pdf-row__preview"
        onClick={(e) => { e.stopPropagation(); onPreview(doc.pdf_name); }}
        title="PDF önizle"
      >
        <svg viewBox="0 0 16 16" fill="none">
          <path d="M2 8s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5z" stroke="currentColor" strokeWidth="1.4" />
          <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.4" />
        </svg>
      </button>

      {/* Detay butonu */}
      <button
        className="db-pdf-row__detail-btn"
        onClick={() => onDetail(doc.pdf_name)}
        title="İçeriği gör"
      >
        <svg viewBox="0 0 16 16" fill="none">
          <path d="M3 4h10M3 8h7M3 12h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>

      {/* Sil butonu */}
      <button
        className={`db-pdf-row__del${confirm ? " confirm" : ""}`}
        onClick={handleDelete}
        disabled={deleting}
        onBlur={() => setTimeout(() => setConfirm(false), 200)}
        title="Sil"
      >
        {deleting ? (
          <span className="db-spin-sm" />
        ) : confirm ? (
          "Emin misin?"
        ) : (
          <svg viewBox="0 0 16 16" fill="none">
            <path d="M3 4h10M6 4V3h4v1M5 4v9a1 1 0 001 1h4a1 1 0 001-1V4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// PDF ÖNİZLEME MODALI
// ══════════════════════════════════════════════════════════════════
function PdfPreviewModal({ pdfName, onClose }) {
  const previewUrl = `${API}/api/db/preview/${encodeURIComponent(pdfName)}`;

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="db-overlay" onClick={onClose}>
      <div className="db-preview-modal" onClick={(e) => e.stopPropagation()}>
        <div className="db-modal__header">
          <div className="db-modal__title">
            <svg viewBox="0 0 18 18" fill="none">
              <path d="M11 2H4a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V6l-4-4z" stroke="currentColor" strokeWidth="1.5" />
              <path d="M11 2v4h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span>{pdfName}</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <a
              href={previewUrl}
              target="_blank"
              rel="noreferrer"
              className="db-modal__open-btn"
              title="Yeni sekmede aç"
            >
              <svg viewBox="0 0 16 16" fill="none">
                <path d="M7 3H3a1 1 0 00-1 1v9a1 1 0 001 1h9a1 1 0 001-1V9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                <path d="M10 2h4v4M14 2L8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </a>
            <button className="db-modal__close" onClick={onClose}>
              <svg viewBox="0 0 14 14" fill="none">
                <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>

        <div className="db-preview-body">
          <iframe
            src={previewUrl}
            title={pdfName}
            className="db-preview-iframe"
          />
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// DETAY MODALI — Başlık / Özet / Tam Metin / Chunk'lar
// ══════════════════════════════════════════════════════════════════
function DetailPanel({ pdfName, onClose, onPreview }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("title");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!pdfName) return;
    setLoading(true);
    setData(null);
    setTab("title");
    dbGetDetail(pdfName)
      .then((res) => setData(res.detail))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [pdfName]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // ── Sekme içerikleri ──────────────────────────────────────────
  const tabContent = () => {
    if (!data) return "";
    if (tab === "title") return data.raw_title || "(başlık bulunamadı)";
    if (tab === "abstract") return data.abstract || "(özet bulunamadı)";
    if (tab === "fulltext") return data.fulltext || "(tam metin bulunamadı)";
    if (tab === "chunks") return null; // özel render
    return "";
  };

  const fulltextChunks = data?.chunks?.filter((c) => c.chunk_type === "fulltext") || [];
  const charCount = typeof tabContent() === "string" ? tabContent().length : 0;

  const copy = () => {
    const content = tab === "chunks"
      ? fulltextChunks.map((c, i) => `[${i + 1}] ${c.chunk_text}`).join("\n\n")
      : tabContent();
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // Chunk'ın Milvus'ta nasıl tutulduğunu açıklayan renk/etiket
  const storageLabel = {
    title:    { label: "liftup_titles",    color: "#00D4FF" },
    abstract: { label: "liftup_abstracts", color: "#A78BFA" },
    fulltext: { label: "liftup_fulltext",  color: "#34D399" },
    chunks:   { label: "liftup_fulltext",  color: "#34D399" },
  }[tab];

  return (
    <div className="db-overlay" onClick={onClose}>
      <div className="db-modal" onClick={(e) => e.stopPropagation()}>

        {/* Header */}
        <div className="db-modal__header">
          <div className="db-modal__title">
            <svg viewBox="0 0 18 18" fill="none">
              <path d="M11 2H4a1 1 0 00-1 1v12a1 1 0 001 1h10a1 1 0 001-1V6l-4-4z" stroke="currentColor" strokeWidth="1.5" />
              <path d="M11 2v4h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span>{pdfName}</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="db-modal__preview-btn"
              onClick={() => { onClose(); onPreview(pdfName); }}
              title="PDF önizle"
            >
              <svg viewBox="0 0 16 16" fill="none">
                <path d="M2 8s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5z" stroke="currentColor" strokeWidth="1.4" />
                <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.4" />
              </svg>
              PDF Önizle
            </button>
            <button className="db-modal__close" onClick={onClose}>
              <svg viewBox="0 0 14 14" fill="none">
                <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>

        {/* Meta bilgiler */}
        {data && (
          <div className="db-modal__meta">
            {data.year > 0 && (
              <span className="db-modal__badge db-modal__badge--year">{data.year}</span>
            )}
            {data.book_name && (
              <span className="db-modal__badge">{data.book_name}</span>
            )}
            {fulltextChunks.length > 0 && (
              <span className="db-modal__badge db-modal__badge--green">
                {fulltextChunks.length} chunk
              </span>
            )}
            {/* Milvus storage göstergesi */}
            <span
              className="db-modal__badge db-modal__badge--storage"
              style={{ borderColor: storageLabel.color, color: storageLabel.color }}
            >
              <span
                className="db-storage-dot"
                style={{ background: storageLabel.color }}
              />
              {storageLabel.label}
            </span>
          </div>
        )}

        {/* Sekmeler */}
        <div className="db-modal__tabs">
          {[
            ["title",    "Başlık",    "1 kayıt"],
            ["abstract", "Özet",      "1 kayıt"],
            ["fulltext", "Tam Metin", "ham metin"],
            ["chunks",   "Chunk'lar", fulltextChunks.length + " parça"],
          ].map(([k, l, hint]) => (
            <button
              key={k}
              className={`db-modal__tab${tab === k ? " active" : ""}`}
              onClick={() => setTab(k)}
            >
              {l}
              <span className="db-modal__tab-hint">{hint}</span>
            </button>
          ))}
          <div className="db-modal__tabs-right">
            {!loading && data && tab !== "chunks" && (
              <span className="db-modal__charcount">
                {charCount.toLocaleString()} karakter
              </span>
            )}
            <button className="db-modal__copy" onClick={copy} disabled={loading || !data}>
              {copied ? "✓ Kopyalandı" : "Kopyala"}
            </button>
          </div>
        </div>

        {/* İçerik */}
        <div className="db-modal__body">
          {loading ? (
            <div className="db-modal__loading">
              <span className="db-spin-sm" />
              <span>Yükleniyor…</span>
            </div>
          ) : !data ? (
            <div className="db-modal__empty">
              <p>Bu PDF için veri bulunamadı</p>
            </div>
          ) : tab === "chunks" ? (
            /* Chunk'lar özel görünüm */
            <div className="db-chunks-list">
              {fulltextChunks.length === 0 ? (
                <p className="db-chunks-empty">Chunk bulunamadı</p>
              ) : (
                fulltextChunks.map((chunk) => (
                  <div key={chunk.chunk_idx} className="db-chunk-card">
                    <div className="db-chunk-card__header">
                      <span className="db-chunk-card__num">#{chunk.chunk_idx + 1}</span>
                      <span className="db-chunk-card__len">
                        {chunk.chunk_text.length} karakter
                      </span>
                      <span className="db-chunk-card__type">liftup_fulltext</span>
                    </div>
                    <p className="db-chunk-card__text">{chunk.chunk_text}</p>
                  </div>
                ))
              )}
            </div>
          ) : (
            <pre className="db-modal__text">{tabContent()}</pre>
          )}
        </div>

        {/* Alt bilgi — Milvus yapısı açıklaması */}
        {!loading && data && (
          <div className="db-modal__footer">
            <div className="db-storage-explain">
              <div className="db-storage-explain__item">
                <span className="db-storage-dot" style={{ background: "#00D4FF" }} />
                <code>liftup_titles</code>
                <span>— 1 kayıt · başlık vektörü · benzerlik title skorunda kullanılır</span>
              </div>
              <div className="db-storage-explain__item">
                <span className="db-storage-dot" style={{ background: "#A78BFA" }} />
                <code>liftup_abstracts</code>
                <span>— 1 kayıt · özet vektörü · semantik arama için</span>
              </div>
              <div className="db-storage-explain__item">
                <span className="db-storage-dot" style={{ background: "#34D399" }} />
                <code>liftup_fulltext</code>
                <span>— {fulltextChunks.length} chunk · 850 kar/chunk · RAG retrieval için</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// ANA BİLEŞEN
// ══════════════════════════════════════════════════════════════════
export default function Database() {
  const [files, setFiles]             = useState([]);
  const [bookName, setBookName]       = useState("");
  const [year, setYear]               = useState("");
  const [forceUp, setForceUp]         = useState(false);
  const [uploading, setUploading]     = useState(false);
  const [uploadRows, setUploadRows]   = useState([]);

  const [stats, setStats]             = useState(null);
  const [statsErr, setStatsErr]       = useState(null);
  const [docs, setDocs]               = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [search, setSearch]           = useState("");
  const [tab, setTab]                 = useState("upload");

  const [selectedPdf, setSelectedPdf]   = useState(null); // detay modal
  const [previewPdf, setPreviewPdf]     = useState(null); // önizleme modal
  const [resetting, setResetting]       = useState(false);

  useEffect(() => {
    loadStats();
    loadDocs();
  }, []);

  const loadStats = async () => {
    try {
      const res = await dbStats();
      setStats(res.stats);
      setStatsErr(null);
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (!e?.response)
        setStatsErr("Backend'e bağlanılamadı — uvicorn çalışıyor mu? (localhost:8000)");
      else if (status === 503)
        setStatsErr(detail || "Milvus bağlantısı kurulamadı (localhost:19530)");
      else
        setStatsErr(`Hata ${status}: ${detail || e.message}`);
    }
  };

  const loadDocs = async () => {
    setDocsLoading(true);
    try {
      const res = await dbListPdfs(500);
      setDocs(res.documents || []);
    } catch {
      setDocs([]);
    }
    setDocsLoading(false);
  };

  const startUpload = useCallback(async () => {
    if (!files.length || uploading) return;
    setUploading(true);
    const rows = files.map((f) => ({ file: f, status: "pending", result: null, error: null }));
    setUploadRows(rows);
    setTab("upload");

    for (let i = 0; i < files.length; i++) {
      setUploadRows((prev) => prev.map((r, j) => (j === i ? { ...r, status: "uploading" } : r)));
      try {
        const res = await dbAddPdf(files[i], {
          bookName,
          year: year ? parseInt(year) : 0,
          forceUpdate: forceUp,
        });
        setUploadRows((prev) =>
          prev.map((r, j) => (j === i ? { ...r, status: "done", result: res } : r))
        );
      } catch (e) {
        const msg = e?.response?.data?.detail || e.message || "Hata";
        setUploadRows((prev) =>
          prev.map((r, j) => (j === i ? { ...r, status: "error", error: msg } : r))
        );
      }
    }
    setUploading(false);
    setFiles([]);
    loadStats();
    loadDocs();
  }, [files, bookName, year, forceUp, uploading]);

  const handleDelete = async (pdfName) => {
    try {
      await dbRemovePdf(pdfName);
      setDocs((prev) => prev.filter((d) => d.pdf_name !== pdfName));
      if (selectedPdf === pdfName) setSelectedPdf(null);
      if (previewPdf === pdfName) setPreviewPdf(null);
      loadStats();
    } catch (e) {
      alert("Silme hatası: " + (e?.response?.data?.detail || e.message));
    }
  };

  const handleReset = async () => {
    if (!window.confirm("TÜM veriler silinecek! Emin misin?")) return;
    setResetting(true);
    try {
      await dbReset();
      setDocs([]);
      setSelectedPdf(null);
      setPreviewPdf(null);
      loadStats();
    } catch (e) {
      alert("Reset hatası: " + (e?.response?.data?.detail || e.message));
    }
    setResetting(false);
  };

  // İstatistik değerleri
  const totalDocs  = stats?.unique_pdf_count ?? docs.length;
  const titleCount = stats?.liftup_titles?.count    ?? "—";
  const absCount   = stats?.liftup_abstracts?.count ?? "—";
  const ftCount    = stats?.liftup_fulltext?.count  ?? "—";

  const filteredDocs = docs.filter(
    (d) =>
      !search ||
      d.pdf_name?.toLowerCase().includes(search.toLowerCase()) ||
      d.raw_title?.toLowerCase().includes(search.toLowerCase()) ||
      d.book_name?.toLowerCase().includes(search.toLowerCase())
  );

  const uploadedCount = uploadRows.filter((r) => r.status === "done").length;
  const errorCount    = uploadRows.filter((r) => r.status === "error").length;
  const doneAll = uploadRows.length > 0 && uploadRows.every((r) => r.status === "done" || r.status === "error");

  return (
    <div className="db-root">
      <Navbar />

      {/* Header */}
      <div className="db-header">
        <div className="db-header__bg-grid" />
        <div className="db-header__bg-glow" />
        <div className="db-header__inner">
          <div className="db-breadcrumb">
            AltayAI
            <svg viewBox="0 0 10 10" fill="none">
              <path d="M3 2l4 3-4 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <span>Veritabanı</span>
          </div>
          <h1 className="db-header__title">
            Milvus <em>Veritabanı</em>
          </h1>
          <p className="db-header__sub">
            PDF yükle · BERT embedding ile otomatik indeksle · Benzerlik & Öneri için hazırla
          </p>
          <div className="db-header__pills">
            <span className="db-pill db-pill--amber">Milvus</span>
            <span className="db-pill">PostgreSQL</span>
            <span className="db-pill">sentence-BERT</span>
            <span className="db-pill">3 Collection</span>
            <span className="db-pill">850-token chunk</span>
          </div>
        </div>
      </div>

      {/* Bağlantı hatası */}
      {statsErr && (
        <div className="db-conn-err">
          <svg viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.8" />
            <line x1="10" y1="6" x2="10" y2="11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <circle cx="10" cy="14" r=".8" fill="currentColor" />
          </svg>
          {statsErr}
          <button onClick={loadStats}>Tekrar Dene</button>
        </div>
      )}

      {/* İstatistik kartları */}
      <div className="db-stats-bar">
        <StatCard
          label="Toplam PDF" value={totalDocs} color="#F59E0B" sub="unique PDF sayısı"
          icon={<svg viewBox="0 0 20 20" fill="none"><path d="M13 2H5a1 1 0 00-1 1v14a1 1 0 001 1h10a1 1 0 001-1V6l-3-4z" stroke="currentColor" strokeWidth="1.5" /><path d="M13 2v4h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>}
        />
        <StatCard
          label="Başlık Kayıtları" value={titleCount} color="#00D4FF" sub="liftup_titles"
          icon={<svg viewBox="0 0 20 20" fill="none"><line x1="4" y1="6" x2="16" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><line x1="4" y1="10" x2="12" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity=".6" /><line x1="4" y1="14" x2="9" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity=".3" /></svg>}
        />
        <StatCard
          label="Özet Kayıtları" value={absCount} color="#A78BFA" sub="liftup_abstracts"
          icon={<svg viewBox="0 0 20 20" fill="none"><rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" /><line x1="6" y1="7" x2="14" y2="7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><line x1="6" y1="10" x2="14" y2="10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" opacity=".6" /><line x1="6" y1="13" x2="10" y2="13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" opacity=".3" /></svg>}
        />
        <StatCard
          label="Fulltext Chunk" value={ftCount} color="#34D399" sub="liftup_fulltext"
          icon={<svg viewBox="0 0 20 20" fill="none"><ellipse cx="10" cy="6" rx="7" ry="3" stroke="currentColor" strokeWidth="1.5" /><path d="M3 6v4c0 1.657 3.134 3 7 3s7-1.343 7-3V6" stroke="currentColor" strokeWidth="1.5" /><path d="M3 10v4c0 1.657 3.134 3 7 3s7-1.343 7-3v-4" stroke="currentColor" strokeWidth="1.5" /></svg>}
        />
      </div>

      {/* Sekmeler + İçerik */}
      <div className="db-layout">
        <div className="db-tabs">
          <button className={`db-tab${tab === "upload" ? " active" : ""}`} onClick={() => setTab("upload")}>
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M8 2v8M5 5l3-3 3 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 12h12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            PDF Yükle
            {uploadRows.length > 0 && (
              <span className={`db-tab__badge${doneAll ? (errorCount > 0 ? " err" : " ok") : ""}`}>
                {doneAll ? `${uploadedCount}/${uploadRows.length}` : "…"}
              </span>
            )}
          </button>
          <button className={`db-tab${tab === "list" ? " active" : ""}`} onClick={() => setTab("list")}>
            <svg viewBox="0 0 16 16" fill="none">
              <line x1="2" y1="5" x2="14" y2="5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="2" y1="8" x2="14" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="2" y1="11" x2="10" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            PDF Listesi
            <span className="db-tab__badge db-tab__badge--neutral">{totalDocs}</span>
          </button>
        </div>

        {/* ── Yükleme sekmesi ──────────────────────────────────────── */}
        {tab === "upload" && (
          <div className="db-upload-panel">
            <div className="db-upload-form">
              <div className="db-section-label">
                <span className="db-dot db-dot--amber" />PDF Dosyaları
              </div>
              <PdfDropZone files={files} onFiles={setFiles} />

              <div className="db-section-label" style={{ marginTop: 18 }}>
                <span className="db-dot db-dot--cyan" />Meta Bilgiler (opsiyonel)
              </div>
              <div className="db-form-row">
                <div className="db-form-field">
                  <label className="db-form-label">Bildiri Kitabı Adı</label>
                  <input
                    className="db-input"
                    type="text"
                    placeholder="ör: LIFT UP 2024"
                    value={bookName}
                    onChange={(e) => setBookName(e.target.value)}
                  />
                </div>
                <div className="db-form-field db-form-field--sm">
                  <label className="db-form-label">Yıl</label>
                  <input
                    className="db-input"
                    type="number"
                    placeholder="2024"
                    min="2000"
                    max="2030"
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                  />
                </div>
              </div>

              <label className="db-checkbox">
                <input
                  type="checkbox"
                  checked={forceUp}
                  onChange={(e) => setForceUp(e.target.checked)}
                />
                <span className="db-checkbox__box" />
                <span className="db-checkbox__label">
                  Zaten mevcut PDF'leri güncelle
                  <span className="db-checkbox__note"> (varsayılan: atla)</span>
                </span>
              </label>

              <button
                className="db-upload-btn"
                onClick={startUpload}
                disabled={uploading || !files.length}
              >
                {uploading ? (
                  <>
                    <span className="db-spin" />
                    <span>Yükleniyor… ({files.length} PDF)</span>
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 20 20" fill="none">
                      <path d="M10 3v10M7 6l3-3 3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      <path d="M3 14v2a1 1 0 001 1h12a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    <span>Milvus'a Yükle ve İndeksle</span>
                    {files.length > 0 && (
                      <span className="db-upload-btn__count">{files.length} PDF</span>
                    )}
                  </>
                )}
              </button>

              {/* Veri akışı açıklaması */}
              <div className="db-info-box">
                <div className="db-info-box__title">
                  <svg viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
                    <line x1="8" y1="7" x2="8" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    <circle cx="8" cy="5" r=".7" fill="currentColor" />
                  </svg>
                  Her PDF yüklendiğinde neler olur?
                </div>
                <ul className="db-info-box__list">
                  <li>
                    <span className="db-info-dot" style={{ background: "#00D4FF" }} />
                    Başlık <span className="db-info-arrow">→</span>{" "}
                    <code>liftup_titles</code> (1 satır) + PostgreSQL <code>papers.raw_title</code>
                  </li>
                  <li>
                    <span className="db-info-dot" style={{ background: "#A78BFA" }} />
                    Özet <span className="db-info-arrow">→</span>{" "}
                    <code>liftup_abstracts</code> (1 satır) + PostgreSQL <code>papers.abstract</code>
                  </li>
                  <li>
                    <span className="db-info-dot" style={{ background: "#34D399" }} />
                    Tam metin <span className="db-info-arrow">→</span>{" "}
                    <code>liftup_fulltext</code> (~N chunk, 850 karakter/chunk, overlap 100) + PostgreSQL <code>chunks</code>
                  </li>
                </ul>
              </div>
            </div>

            {/* Yükleme durumu */}
            <div className="db-upload-results">
              <div className="db-section-label">
                <span className="db-dot db-dot--green" />Yükleme Durumu
              </div>
              {uploadRows.length === 0 ? (
                <div className="db-results-empty">
                  <svg viewBox="0 0 60 60" fill="none">
                    <ellipse cx="30" cy="18" rx="20" ry="7" stroke="currentColor" strokeWidth="1.4" opacity=".25" />
                    <path d="M10 18v16c0 3.866 8.954 7 20 7s20-3.134 20-7V18" stroke="currentColor" strokeWidth="1.4" opacity=".25" />
                    <path d="M10 26v8c0 3.866 8.954 7 20 7s20-3.134 20-7v-8" stroke="currentColor" strokeWidth="1.4" opacity=".15" />
                  </svg>
                  <p>PDF seçin ve yükleyin</p>
                  <span>Sonuçlar burada görünecek</span>
                </div>
              ) : (
                <>
                  {doneAll && (
                    <div className={`db-results-summary${errorCount > 0 ? " has-err" : ""}`}>
                      <span className="db-results-summary__ok">✓ {uploadedCount} başarılı</span>
                      {errorCount > 0 && (
                        <span className="db-results-summary__err">✕ {errorCount} hata</span>
                      )}
                    </div>
                  )}
                  <div className="db-upload-rows">
                    {uploadRows.map((r, i) => <UploadRow key={i} {...r} />)}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Liste sekmesi ─────────────────────────────────────────── */}
        {tab === "list" && (
          <div className="db-list-panel">
            <div className="db-list-toolbar">
              <div className="db-search-wrap">
                <svg viewBox="0 0 16 16" fill="none" className="db-search-icon">
                  <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.4" />
                  <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
                <input
                  className="db-search"
                  type="text"
                  placeholder="PDF adı, başlık veya kitap ara…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                {search && (
                  <button className="db-search-clear" onClick={() => setSearch("")}>✕</button>
                )}
              </div>
              <button className="db-reset-btn" onClick={handleReset} disabled={resetting}>
                {resetting ? <span className="db-spin-sm" /> : "Sıfırla"}
              </button>
              <button className="db-refresh-btn" onClick={() => { loadDocs(); loadStats(); }}>
                <svg viewBox="0 0 16 16" fill="none">
                  <path d="M13 3A7 7 0 103.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  <path d="M3 13V10H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Yenile
              </button>
            </div>

            {docsLoading ? (
              <div className="db-list-loading">
                <span className="db-spin" />
                <span>Yükleniyor…</span>
              </div>
            ) : filteredDocs.length === 0 ? (
              <div className="db-list-empty">
                {search ? (
                  <>
                    <p>"{search}" için sonuç bulunamadı</p>
                    <span>Arama kriterini değiştirin</span>
                  </>
                ) : (
                  <>
                    <p>Veritabanı boş</p>
                    <span>PDF Yükle sekmesinden dosya ekleyin</span>
                  </>
                )}
              </div>
            ) : (
              <div className="db-pdf-list">
                <div className="db-pdf-list__header">
                  <span className="db-pdf-list__count">{filteredDocs.length} PDF</span>
                  {search && (
                    <span className="db-pdf-list__filter">"{search}" filtresi</span>
                  )}
                  <span className="db-pdf-list__hint">
                    <svg viewBox="0 0 14 14" fill="none" style={{ width: 13, opacity: 0.5 }}>
                      <path d="M2 7s2-4 5-4 5 4 5 4-2 4-5 4-5-4-5-4z" stroke="currentColor" strokeWidth="1.3" />
                      <circle cx="7" cy="7" r="1.5" stroke="currentColor" strokeWidth="1.3" />
                    </svg>
                    Önizle · İçerik · Sil
                  </span>
                </div>
                {filteredDocs.map((doc, i) => (
                  <PdfRow
                    key={doc.pdf_name}
                    doc={doc}
                    index={i + 1}
                    onDelete={handleDelete}
                    onDetail={setSelectedPdf}
                    onPreview={setPreviewPdf}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detay Modal */}
      {selectedPdf && (
        <DetailPanel
          pdfName={selectedPdf}
          onClose={() => setSelectedPdf(null)}
          onPreview={(name) => { setSelectedPdf(null); setPreviewPdf(name); }}
        />
      )}

      {/* PDF Önizleme Modal */}
      {previewPdf && (
        <PdfPreviewModal
          pdfName={previewPdf}
          onClose={() => setPreviewPdf(null)}
        />
      )}
    </div>
  );
}