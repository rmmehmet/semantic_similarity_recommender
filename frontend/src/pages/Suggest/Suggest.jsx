import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { suggestSearch, validatePdfFile } from "../../../services/service.js";
import UserMenu from "../../UserMenu";
import "./Suggest.css";

// ── Sabitler ───────────────────────────────────────────────────────
const BERT_HIGH = 0.80;
const BERT_MID  = 0.50;

const MODES = [
  {
    v: "title",
    l: "Başlık",
    icon: "T",
    hint: "Proje başlığınızı girin",
    desc: "Başlık bazlı semantik arama",
    placeholder: "Projenizin başlığını buraya yazın…\n\nÖrnek: Derin Öğrenme ile Tıbbi Görüntü Analizi",
    minLen: 5,
  },
  {
    v: "abstract",
    l: "Özet",
    icon: "Ö",
    hint: "Proje özetinizi girin",
    desc: "Özet bazlı anlamsal eşleştirme",
    placeholder: "Projenizin özetini buraya yazın…\n\nBu çalışmada amaçlanan…",
    minLen: 30,
  },
  {
    v: "fulltext",
    l: "Tam Metin",
    icon: "TM",
    hint: "Tam metin girin veya PDF yükleyin",
    desc: "Tam metin analizi + PDF yükleme",
    placeholder: "Proje tam metnini buraya yazın\nveya aşağıdan PDF yükleyin…",
    minLen: 50,
  },
];

function levelFor(score) {
  if (score >= BERT_HIGH) return "high";
  if (score >= BERT_MID)  return "mid";
  return "low";
}

// ── Navbar ─────────────────────────────────────────────────────────
function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <nav className="sug-nav">
      <button className="sug-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
        <span className="sug-logo-hex">A</span>
        <span className="sug-nav__brand">Altay<em>AI</em></span>
      </button>
      <ul className={`sug-nav__links${open ? " open" : ""}`}>
        {[["PDF Bölme","/split"],["Benzerlik Arama","/search"],["Proje Öneri","/suggest"],["Veritabanı","/database"]].map(([l,p]) => (
          <li key={p}>
            <button className={`sug-nav__link${p==="/suggest"?" active":""}`}
              onClick={() => { navigate(p); setOpen(false); }}>{l}</button>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <UserMenu />
        <button className="sug-nav__burger" onClick={() => setOpen(v=>!v)}>
          <span/><span/><span/>
        </button>
      </div>
    </nav>
  );
}

// ── PDF Drop Zone ──────────────────────────────────────────────────
function PdfDrop({ file, onFile, onError }) {
  const [drag, setDrag] = useState(false);
  const ref = useRef(null);
  const handle = f => {
    if (!f) return;
    const err = validatePdfFile(f);
    if (err) { onError?.(err); return; }
    onFile(f);
  };
  return (
    <div className={`sug-pdf-drop${drag?" drag":""}${file?" filled":""}`}
      onDragOver={e=>{e.preventDefault();setDrag(true)}}
      onDragLeave={()=>setDrag(false)}
      onDrop={e=>{e.preventDefault();setDrag(false);handle(e.dataTransfer.files[0])}}
      onClick={()=>!file&&ref.current?.click()}>
      <input ref={ref} type="file" accept=".pdf" style={{display:"none"}}
        onChange={e=>handle(e.target.files[0])}/>
      {file ? (
        <div className="sug-pdf-drop__filled">
          <div className="sug-pdf-drop__file-icon">
            <svg viewBox="0 0 28 28" fill="none">
              <path d="M16 2H6a2 2 0 00-2 2v20a2 2 0 002 2h16a2 2 0 002-2V9l-8-7z"
                stroke="currentColor" strokeWidth="1.6"/>
              <path d="M16 2v7h7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
              <line x1="9" y1="15" x2="19" y2="15" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              <line x1="9" y1="19" x2="15" y2="19" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
          </div>
          <div className="sug-pdf-drop__info">
            <span className="sug-pdf-drop__name">{file.name}</span>
            <span className="sug-pdf-drop__size">{(file.size/1024/1024).toFixed(2)} MB · PDF</span>
          </div>
          <button className="sug-pdf-drop__rm"
            onClick={e=>{e.stopPropagation();onFile(null);}}>
            <svg viewBox="0 0 14 14" fill="none">
              <path d="M3 3l8 8M11 3L3 11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      ) : (
        <div className="sug-pdf-drop__empty">
          <div className="sug-pdf-drop__empty-icon">
            <svg viewBox="0 0 40 40" fill="none">
              <path d="M22 4H10a2 2 0 00-2 2v28a2 2 0 002 2h20a2 2 0 002-2V14l-10-10z"
                stroke="currentColor" strokeWidth="1.6" opacity=".45"/>
              <path d="M22 4v10h10" stroke="currentColor" strokeWidth="1.6"
                strokeLinecap="round" opacity=".45"/>
              <path d="M20 22v8M16 26l4 4 4-4"
                stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="sug-pdf-drop__label">PDF sürükle veya tıkla</span>
          <span className="sug-pdf-drop__sub">Tam metin otomatik çıkarılır</span>
        </div>
      )}
    </div>
  );
}

// ── Sonuç Kartı ────────────────────────────────────────────────────
function ResultCard({ result, rank, animDelay }) {
  const level = levelFor(result.score);
  const pct   = Math.round(result.score * 100);
  const LABELS = { high: "Yüksek Benzerlik", mid: "Orta Benzerlik", low: "Düşük Benzerlik" };
  const COLORS = { high: "#EF4444", mid: "#F59E0B", low: "#34D399" };
  const GRADS  = {
    high: "linear-gradient(90deg,#EF4444,#F87171)",
    mid:  "linear-gradient(90deg,#F59E0B,#FCD34D)",
    low:  "linear-gradient(90deg,#34D399,#6EE7B7)",
  };

  return (
    <div className={`sug-rcard sug-rcard--${level}`}
      style={{animationDelay:`${animDelay}ms`}}>
      <div className="sug-rcard__rank">
        <span>{String(rank).padStart(2,"0")}</span>
      </div>
      <div className="sug-rcard__body">
        <div className="sug-rcard__top">
          <div className="sug-rcard__title-wrap">
            <h3 className="sug-rcard__title">{result.raw_title || result.pdf_name}</h3>
            <div className="sug-rcard__meta">
              {result.book_name && (
                <span className="sug-rcard__meta-tag">{result.book_name}</span>
              )}
              {result.year > 0 && (
                <span className="sug-rcard__meta-year">{result.year}</span>
              )}
            </div>
          </div>
          <span className={`sug-badge sug-badge--${level}`}>{LABELS[level]}</span>
        </div>
        <div className="sug-rcard__bar-row">
          <div className="sug-rcard__bar">
            <div className="sug-rcard__bar-fill"
              style={{width:`${pct}%`, background:GRADS[level]}}/>
          </div>
          <span className="sug-rcard__pct" style={{color:COLORS[level]}}>%{pct}</span>
        </div>
        {result.matched_text && (
          <p className="sug-rcard__snippet">"{result.matched_text}"</p>
        )}
      </div>
    </div>
  );
}

// ── Konu Kartı ─────────────────────────────────────────────────────
function TopicCard({ topic, index, delay }) {
  const title     = typeof topic === "string" ? topic : (topic.title||"");
  const rationale = typeof topic === "object" ? (topic.rationale||"") : "";
  const novelty   = typeof topic === "object" ? (topic.novelty_score||null) : null;

  return (
    <div className="sug-topic-card" style={{animationDelay:`${delay}ms`}}>
      <div className="sug-topic-card__num">{String(index+1).padStart(2,"0")}</div>
      <div className="sug-topic-card__content">
        <h4 className="sug-topic-card__title">{title}</h4>
        {rationale && <p className="sug-topic-card__rationale">{rationale}</p>}
      </div>
      {novelty && (
        <div className="sug-topic-card__novelty">
          <svg viewBox="0 0 36 36" fill="none" className="sug-topic-card__ring-svg">
            <circle cx="18" cy="18" r="15" stroke="rgba(52,211,153,0.15)" strokeWidth="3"/>
            <circle cx="18" cy="18" r="15" stroke="#34D399" strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${(novelty/100)*94.2} 94.2`}
              strokeDashoffset="23.5"
              transform="rotate(-90 18 18)"/>
          </svg>
          <div className="sug-topic-card__novelty-inner">
            <span className="sug-topic-card__novelty-val">%{novelty}</span>
            <span className="sug-topic-card__novelty-lbl">özgünlük</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── LLM Öneri Paneli ───────────────────────────────────────────────
// function LLMPanel({ data, highCount }) {
//   const [expanded, setExpanded] = useState(true);
//   if (!data) return null;
//   const hasTopics = (data.topic_suggestions||[]).length > 0;

//   return (
//     <div className="sug-llm-panel">
//       <div className="sug-llm-panel__glow-bar"/>
//       <div className="sug-llm-panel__hdr" onClick={()=>setExpanded(v=>!v)}>
//         <div className="sug-llm-panel__hdr-left">
//           <div className="sug-llm-panel__star-icon">
//             <svg viewBox="0 0 24 24" fill="none">
//               <path d="M12 2l2.4 7H22l-6 4.5 2.3 7L12 17l-6.3 3.5L8 13.5 2 9h7.6z"
//                 stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/>
//             </svg>
//           </div>
//           <div>
//             <div className="sug-llm-panel__title">
//               LLM Konu Önerisi
//               <span className="sug-llm-panel__model-badge">Llama 3.1 Q4</span>
//             </div>
//             <div className="sug-llm-panel__sub">
//               {data.success
//                 ? `${highCount} yüksek benzerlik · Aynı alanda özgün konu önerileri`
//                 : "LLM modeli yüklenemedi"}
//             </div>
//           </div>
//         </div>
//         <div className="sug-llm-panel__hdr-right">
//           {data.field && <span className="sug-llm-panel__field-chip">{data.field}</span>}
//           <button className={`sug-llm-panel__toggle${expanded?" open":""}`}>
//             <svg viewBox="0 0 16 16" fill="none">
//               <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.8"
//                 strokeLinecap="round" strokeLinejoin="round"/>
//             </svg>
//           </button>
//         </div>
//       </div>

//       {expanded && (
//         <div className="sug-llm-panel__body">
//           {!data.success && (
//             <div className="sug-llm-err">
//               <svg viewBox="0 0 24 24" fill="none">
//                 <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
//                 <line x1="12" y1="8" x2="12" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
//                 <circle cx="12" cy="16.5" r="1.2" fill="currentColor"/>
//               </svg>
//               <div>
//                 <p className="sug-llm-err__msg">{data.analysis}</p>
//                 {data.error && <code className="sug-llm-err__code">{data.error}</code>}
//                 <p className="sug-llm-err__hint">
//                   Model indirme:<br/>
//                   <code>huggingface-cli download bartowski/Meta-Llama-3.1-8B-Instruct-GGUF --include "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf" --local-dir ./models/</code>
//                 </p>
//               </div>
//             </div>
//           )}

//           {data.success && data.analysis && (
//             <div className="sug-analysis">
//               <div className="sug-analysis__eyebrow">
//                 <span className="sug-analysis__dot"/>
//                 Benzerlik Analizi
//               </div>
//               <p className="sug-analysis__text">{data.analysis}</p>
//             </div>
//           )}

//           {data.success && hasTopics && (
//             <div className="sug-topics">
//               <div className="sug-topics__header">
//                 <span className="sug-topics__label">Önerilen Özgün Konular</span>
//                 <span className="sug-topics__count">{data.topic_suggestions.length} öneri</span>
//               </div>
//               <div className="sug-topics__list">
//                 {data.topic_suggestions.map((t,i) => (
//                   <TopicCard key={i} topic={t} index={i} delay={i*80}/>
//                 ))}
//               </div>
//             </div>
//           )}

//           {data.success && data.revised_title && (
//             <div className="sug-revised">
//               <div className="sug-revised__label">
//                 <svg viewBox="0 0 16 16" fill="none">
//                   <path d="M8 1l1.8 4 4.2.5-3 3 .7 4.5L8 11l-3.7 2 .7-4.5-3-3 4.2-.5z"
//                     stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
//                 </svg>
//                 Önerilen Özgün Başlık
//               </div>
//               <p className="sug-revised__text">"{data.revised_title}"</p>
//             </div>
//           )}

//           {data.success && !hasTopics && !data.analysis && (
//             <p className="sug-llm-empty">LLM yanıt üretemedi. Model tekrar denenebilir.</p>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }

// ── LLM Öneri Paneli ───────────────────────────────────────────────
function LLMPanel({ data, highCount }) {
  const [expanded, setExpanded] = useState(true);
  if (!data) return null;

  const isRag    = data.mode === "rag";
  const hasTopics = (data.topic_suggestions || []).length > 0;
  const hasOriginal = (data.original_aspects || []).length > 0;
  const hasImprovements = (data.improvement_suggestions || []).length > 0;

  return (
    <div className="sug-llm-panel">
      <div className="sug-llm-panel__glow-bar"/>
      <div className="sug-llm-panel__hdr" onClick={() => setExpanded(v => !v)}>
        <div className="sug-llm-panel__hdr-left">
          <div className="sug-llm-panel__star-icon">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12 2l2.4 7H22l-6 4.5 2.3 7L12 17l-6.3 3.5L8 13.5 2 9h7.6z"
                stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <div className="sug-llm-panel__title">
              {isRag ? "RAG Derin Analiz" : "LLM Konu Önerisi"}
              <span className="sug-llm-panel__model-badge">
                {isRag ? "RAG + Llama 3.1 Q4" : "Llama 3.1 Q4"}
              </span>
            </div>
            <div className="sug-llm-panel__sub">
              {data.success
                ? isRag
                  ? `PDF analizi tamamlandı · ${highCount} benzer proje ile karşılaştırıldı`
                  : `${highCount} yüksek benzerlik · Aynı alanda özgün konu önerileri`
                : "LLM modeli yüklenemedi"}
            </div>
          </div>
        </div>
        <div className="sug-llm-panel__hdr-right">
          {data.field && <span className="sug-llm-panel__field-chip">{data.field}</span>}
          {data.risk_level && (
            <span className="sug-llm-panel__field-chip" style={{
              background: data.risk_level === "düşük"
                ? "rgba(52,211,153,0.1)" : data.risk_level === "orta"
                ? "rgba(245,158,11,0.1)" : "rgba(239,68,68,0.1)",
              color: data.risk_level === "düşük" ? "#34D399"
                : data.risk_level === "orta" ? "#F59E0B" : "#EF4444",
              borderColor: data.risk_level === "düşük"
                ? "rgba(52,211,153,0.25)" : data.risk_level === "orta"
                ? "rgba(245,158,11,0.25)" : "rgba(239,68,68,0.25)",
            }}>
              Risk: {data.risk_level}
            </span>
          )}
          <button className={`sug-llm-panel__toggle${expanded ? " open" : ""}`}>
            <svg viewBox="0 0 16 16" fill="none">
              <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="sug-llm-panel__body">

          {/* Hata durumu */}
          {!data.success && (
            <div className="sug-llm-err">
              <svg viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8"/>
                <line x1="12" y1="8" x2="12" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="12" cy="16.5" r="1.2" fill="currentColor"/>
              </svg>
              <div>
                <p className="sug-llm-err__msg">{data.analysis}</p>
                {data.error && <code className="sug-llm-err__code">{data.error}</code>}
              </div>
            </div>
          )}

          {/* ── TEXT MOD: analysis ── */}
          {data.success && !isRag && data.analysis && (
            <div className="sug-analysis">
              <div className="sug-analysis__eyebrow">
                <span className="sug-analysis__dot"/>
                Benzerlik Analizi
              </div>
              <p className="sug-analysis__text">{data.analysis}</p>
            </div>
          )}

          {/* ── RAG MOD: similarity_analysis ── */}
          {data.success && isRag && data.similarity_analysis && (
            <div className="sug-analysis">
              <div className="sug-analysis__eyebrow">
                <span className="sug-analysis__dot"/>
                Benzerlik Analizi (RAG)
              </div>
              <p className="sug-analysis__text">{data.similarity_analysis}</p>
            </div>
          )}

          {/* ── RAG MOD: original_aspects ── */}
          {data.success && isRag && hasOriginal && (
            <div className="sug-rag-section">
              <div className="sug-rag-section__header">
                <svg viewBox="0 0 16 16" fill="none" style={{width:13,height:13}}>
                  <circle cx="8" cy="8" r="6.5" stroke="#34D399" strokeWidth="1.4"/>
                  <path d="M5 8l2 2 4-4" stroke="#34D399" strokeWidth="1.4"
                    strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Özgün Yönler
              </div>
              <ul className="sug-rag-list sug-rag-list--green">
                {data.original_aspects.map((item, i) => (
                  <li key={i} className="sug-rag-list__item">
                    <span className="sug-rag-list__bullet sug-rag-list__bullet--green"/>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* ── RAG MOD: improvement_suggestions ── */}
          {data.success && isRag && hasImprovements && (
            <div className="sug-rag-section">
              <div className="sug-rag-section__header">
                <svg viewBox="0 0 16 16" fill="none" style={{width:13,height:13}}>
                  <path d="M8 2v8M5 7l3 3 3-3" stroke="#A78BFA" strokeWidth="1.5"
                    strokeLinecap="round" strokeLinejoin="round"/>
                  <line x1="3" y1="13" x2="13" y2="13" stroke="#A78BFA"
                    strokeWidth="1.4" strokeLinecap="round"/>
                </svg>
                Geliştirme Önerileri
              </div>
              <ul className="sug-rag-list sug-rag-list--violet">
                {data.improvement_suggestions.map((item, i) => (
                  <li key={i} className="sug-rag-list__item">
                    <span className="sug-rag-list__bullet sug-rag-list__bullet--violet"/>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Konu önerileri (her iki modda da) */}
          {data.success && hasTopics && (
            <div className="sug-topics">
              <div className="sug-topics__header">
                <span className="sug-topics__label">
                  {isRag ? "Alternatif Konu Önerileri" : "Önerilen Özgün Konular"}
                </span>
                <span className="sug-topics__count">{data.topic_suggestions.length} öneri</span>
              </div>
              <div className="sug-topics__list">
                {data.topic_suggestions.map((t, i) => (
                  <TopicCard key={i} topic={t} index={i} delay={i * 80}/>
                ))}
              </div>
            </div>
          )}

          {/* Önerilen başlık (her iki modda da) */}
          {data.success && data.revised_title && (
            <div className="sug-revised">
              <div className="sug-revised__label">
                <svg viewBox="0 0 16 16" fill="none">
                  <path d="M8 1l1.8 4 4.2.5-3 3 .7 4.5L8 11l-3.7 2 .7-4.5-3-3 4.2-.5z"
                    stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
                </svg>
                Önerilen Özgün Başlık
              </div>
              <p className="sug-revised__text">"{data.revised_title}"</p>
            </div>
          )}

          {data.success && !hasTopics && !data.analysis && !data.similarity_analysis && (
            <p className="sug-llm-empty">LLM yanıt üretemedi. Model tekrar denenebilir.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Pipeline Adım Göstergesi ───────────────────────────────────────
function PipelineProgress({ step }) {
  const STEPS = [
    { n: 1, label: "BERT embedding hesaplanıyor"   },
    { n: 2, label: "Milvus vektör tabanı aranıyor" },
    { n: 3, label: "Llama 3.1 Q4 öneri üretiyor"   },
  ];
  return (
    <div className="sug-loading">
      <div className="sug-ring"><div/><div/><div/><div/></div>
      <p className="sug-loading__title">Analiz yapılıyor…</p>
      <div className="sug-loading__pipeline">
        {STEPS.map(s => (
          <div key={s.n}
            className={`sug-loading__step${step>=s.n?" active":""}${step>s.n?" done":""}`}>
            <span className="sug-loading__step-icon">
              {step>s.n ? "✓" : step===s.n ? "●" : "○"}
            </span>
            {s.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Boş Durum ─────────────────────────────────────────────────────
function EmptyState({ mode }) {
  const MODE = MODES.find(m=>m.v===mode)||MODES[0];
  return (
    <div className="sug-empty">
      <div className="sug-empty__illustration">
        <svg viewBox="0 0 240 150" fill="none">
          {/* DB */}
          <ellipse cx="58" cy="30" rx="38" ry="12" stroke="currentColor" strokeWidth="1.5" opacity=".18"/>
          <rect x="20" y="30" width="76" height="70" stroke="currentColor" strokeWidth="1.5" opacity=".18"/>
          <ellipse cx="58" cy="100" rx="38" ry="12" stroke="currentColor" strokeWidth="1.5" opacity=".18"/>
          <ellipse cx="58" cy="65" rx="38" ry="12" stroke="currentColor" strokeWidth="1.2" opacity=".08" strokeDasharray="5 3"/>
          {[45,55,65,75,85].map((y,i) => (
            <line key={y} x1="30" y1={y} x2={i%2===0?80:68} y2={y}
              stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".14"/>
          ))}
          {/* Arrow */}
          <path d="M102 65 L140 65" stroke="#34D399" strokeWidth="1.8"
            strokeDasharray="5 3" opacity=".5" strokeLinecap="round"/>
          <path d="M136 61l7 4-7 4" stroke="#34D399" strokeWidth="1.8"
            strokeLinecap="round" strokeLinejoin="round" opacity=".6"/>
          {/* LLM box */}
          <rect x="150" y="35" width="76" height="62" rx="10"
            stroke="currentColor" strokeWidth="1.5" opacity=".18"/>
          <path d="M188 48l3 7.5 7.5.5L193 60l2.5 7.5L188 64l-7.5 3.5 2.5-7.5L177.5 56l7.5-.5z"
            stroke="#34D399" strokeWidth="1.4" strokeLinejoin="round" opacity=".7"/>
          {[72,81,90].map((y,i) => (
            <line key={y} x1="160" y1={y} x2={i===0?216:206} y2={y}
              stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".16"/>
          ))}
          {/* Mode indicator */}
          {mode==="fulltext" && (
            <>
              <rect x="22" y="108" width="24" height="32" rx="2"
                stroke="#34D399" strokeWidth="1.2" opacity=".3"/>
              <line x1="26" y1="115" x2="42" y2="115" stroke="#34D399" strokeWidth="1" opacity=".25"/>
              <line x1="26" y1="120" x2="40" y2="120" stroke="#34D399" strokeWidth="1" opacity=".2"/>
            </>
          )}
        </svg>
      </div>
      <h2 className="sug-empty__title">{MODE.desc}</h2>
      <p className="sug-empty__desc">
        {mode==="title"
          ? "Proje başlığınızı girerek benzer başlıkları bulun ve özgünlük analizi yapın."
          : mode==="abstract"
          ? "Özet metnini girerek anlamsal olarak benzer projeleri keşfedin."
          : "Tam metni veya PDF'i yükleyerek kapsamlı benzerlik analizi yapın."}
      </p>
      <div className="sug-empty__pipeline">
        {["Metin Al","BERT Embed","Milvus Ara","LLM Öner"].map((s,i) => (
          <div key={s} className="sug-empty__step">
            <div className="sug-empty__step-num">{i+1}</div>
            <span>{s}</span>
            {i<3 && <div className="sug-empty__step-arrow">→</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// Ana Bileşen
// ══════════════════════════════════════════════════════════════════
export default function Suggest() {
  const [mode,      setMode]      = useState("abstract");
  const [queryText, setQueryText] = useState("");
  const [pdfFile,   setPdfFile]   = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [results,   setResults]   = useState(null);
  const [error,     setError]     = useState(null);
  const [loadStep,  setLoadStep]  = useState(0);

  // Yükleme animasyon adımları
  useEffect(() => {
    if (!loading) { setLoadStep(0); return; }
    const t1 = setTimeout(()=>setLoadStep(1), 300);
    const t2 = setTimeout(()=>setLoadStep(2), 1800);
    const t3 = setTimeout(()=>setLoadStep(3), 4500);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [loading]);

  const currentMode = MODES.find(m=>m.v===mode) || MODES[0];

  const canRun = mode==="fulltext"
    ? (pdfFile!==null || queryText.trim().length > currentMode.minLen)
    : queryText.trim().length > currentMode.minLen;

  const runSearch = useCallback(async () => {
    if (!canRun||loading) return;
    setLoading(true); setError(null); setResults(null);
    try {
      const data = await suggestSearch({
        searchType: mode,
        queryText:  queryText.trim(),
        pdfFile:    mode==="fulltext" ? pdfFile : null,
        topK:       12,
      });
      if (!data.success) throw new Error(data.error||"Arama başarısız");
      setResults(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }, [mode, queryText, pdfFile, canRun, loading]);

  const highCount = (results?.results||[]).filter(r=>r.score>=BERT_HIGH).length;

  const switchMode = v => {
    setMode(v);
    setQueryText("");
    setPdfFile(null);
    setResults(null);
    setError(null);
  };

  return (
    <div className="sug-root">
      <Navbar/>

      {/* ── Page Header ────────────────────────────────────────── */}
      <div className="sug-header">
        <div className="sug-header__bg-grid"/>
        <div className="sug-header__bg-glow"/>
        <div className="sug-header__inner">
          <div className="sug-breadcrumb">
            AltayAI
            <svg viewBox="0 0 10 10" fill="none">
              <path d="M3 2l4 3-4 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            </svg>
            <span>Proje Öneri</span>
          </div>
          <h1 className="sug-header__title">Proje <em>Öneri</em> Sistemi</h1>
          <p className="sug-header__sub">
            BERT semantik arama · Milvus vektör DB · Llama 3.1 Q4 lokal konu önerisi
          </p>
          <div className="sug-header__pills">
            <span className="sug-pill sug-pill--green">sentence-BERT</span>
            <span className="sug-pill">Milvus</span>
            <span className="sug-pill">Llama 3.1 Q4</span>
            <span className="sug-pill">%80+ eşiği</span>
          </div>
        </div>
      </div>

      {/* ── Main Layout ────────────────────────────────────────── */}
      <div className="sug-layout">

        {/* ════ Sidebar ════════════════════════════════════════════ */}
        <aside className="sug-sidebar">

          {/* Mod Seçimi */}
          <div className="sug-panel">
            <div className="sug-panel__label">
              <span className="sug-dot sug-dot--green"/>
              Arama Modu
            </div>
            <div className="sug-mode-grid">
              {MODES.map(m => (
                <button key={m.v}
                  className={`sug-mode-btn${mode===m.v?" active":""}`}
                  onClick={()=>switchMode(m.v)}>
                  <span className="sug-mode-btn__icon-label">{m.icon}</span>
                  <div className="sug-mode-btn__text">
                    <span className="sug-mode-btn__label">{m.l}</span>
                    <span className="sug-mode-btn__desc">{m.desc}</span>
                  </div>
                  {mode===m.v && <span className="sug-mode-btn__pip"/>}
                </button>
              ))}
            </div>
          </div>

          {/* Giriş Alanı */}
          <div className="sug-panel sug-panel--input">
            <div className="sug-panel__label">
              <span className="sug-dot sug-dot--violet"/>
              {currentMode.hint}
            </div>
            <div className="sug-textarea-wrap">
              <textarea
                className="sug-textarea"
                placeholder={currentMode.placeholder}
                value={queryText}
                onChange={e=>setQueryText(e.target.value)}
                onKeyDown={e=>e.key==="Enter"&&e.ctrlKey&&runSearch()}
                rows={mode==="title" ? 4 : 8}
              />
              <div className="sug-textarea-footer">
                <span className="sug-char-count">
                  {queryText.length} / {mode==="fulltext"?"—":mode==="abstract"?"2000":"200"} kar.
                </span>
                {queryText.length>0 && (
                  <button className="sug-clear-btn" onClick={()=>setQueryText("")}>
                    Temizle
                  </button>
                )}
              </div>
            </div>

            {/* PDF yükleme — sadece fulltext */}
            {mode==="fulltext" && (
              <>
                <div className="sug-or-divider"><span>veya</span></div>
                <PdfDrop file={pdfFile} onFile={setPdfFile} onError={setError}/>
              </>
            )}
          </div>

          {/* Çalıştır */}
          <button className="sug-run-btn" onClick={runSearch} disabled={loading||!canRun}>
            {loading ? (
              <><span className="sug-spin"/><span>Analiz ediliyor…</span></>
            ) : (
              <>
                <svg viewBox="0 0 20 20" fill="none">
                  <circle cx="9" cy="9" r="6.5" stroke="currentColor" strokeWidth="1.8"/>
                  <path d="M9 6v3l2 1.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
                  <line x1="14" y1="14" x2="18.5" y2="18.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
                </svg>
                <span>Analiz Et ve Öneri Al</span>
              </>
            )}
          </button>
          <div className="sug-run-hint">Ctrl + Enter ile çalıştırabilirsiniz</div>

          {/* İstatistik */}
          {results && (
            <div className="sug-panel sug-panel--stats">
              <div className="sug-panel__label">Analiz Sonuçları</div>
              <div className="sug-stat-rows">
                {[
                  {l:"Toplam Eşleşme",  v:results.total, cls:""},
                  {l:"Yüksek Benzerlik",v:highCount,      cls: highCount>0?" red":" green"},
                  {l:"LLM Öneri",        v:results.llm_suggestion
                                            ? (results.llm_suggestion.success?"✓ Aktif":"✗ Hata")
                                            : "—",
                                          cls: results.llm_suggestion?.success?" green":""},
                  {l:"Arama Modu",       v:currentMode.l, cls:""},
                ].map(s=>(
                  <div className="sug-stat-row" key={s.l}>
                    <span>{s.l}</span>
                    <span className={`sug-stat-val${s.cls}`}>{s.v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* BERT eşik bilgisi */}
          <div className="sug-panel sug-panel--info">
            <div className="sug-panel__label">BERT Eşik Değerleri</div>
            <div className="sug-threshold-list">
              {[
                {l:"Yüksek", v:"≥ %80", color:"#EF4444", note:"LLM öneri devreye girer"},
                {l:"Orta",   v:"≥ %50", color:"#F59E0B", note:"Dikkat edilmeli"},
                {l:"Düşük",  v:"< %50", color:"#34D399", note:"Özgün sayılabilir"},
              ].map(t=>(
                <div className="sug-thr-item" key={t.l}>
                  <span className="sug-thr-dot" style={{background:t.color}}/>
                  <div className="sug-thr-body">
                    <span className="sug-thr-label">{t.l}</span>
                    <span className="sug-thr-note">{t.note}</span>
                  </div>
                  <span className="sug-thr-val" style={{color:t.color}}>{t.v}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* ════ Ana Panel ══════════════════════════════════════════ */}
        <main className="sug-main">

          {/* Hata */}
          {error && (
            <div className="sug-err">
              <svg viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.8"/>
                <line x1="10" y1="6" x2="10" y2="11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                <circle cx="10" cy="14" r=".8" fill="currentColor"/>
              </svg>
              <span>{error}</span>
              <button onClick={()=>setError(null)}>✕</button>
            </div>
          )}

          {/* Boş durum */}
          {!results&&!loading&&!error && <EmptyState mode={mode}/>}

          {/* Yükleniyor */}
          {loading && <PipelineProgress step={loadStep}/>}

          {/* Sonuçlar */}
          {results&&!loading && (
            <>
              {/* LLM Paneli — en üstte */}
              {results.llm_suggestion && (
                <LLMPanel data={results.llm_suggestion} highCount={highCount}/>
              )}

              {/* Sonuç listesi başlık */}
              <div className="sug-results-hdr">
                <div className="sug-results-hdr__left">
                  <span className="sug-results-title">Benzer Projeler</span>
                  {highCount>0 ? (
                    <span className="sug-warn-badge">
                      <svg viewBox="0 0 14 14" fill="none">
                        <path d="M7 1L13 12H1L7 1z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
                        <line x1="7" y1="5" x2="7" y2="8.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                        <circle cx="7" cy="10.5" r=".7" fill="currentColor"/>
                      </svg>
                      {highCount} yüksek benzerlik
                    </span>
                  ) : (
                    <span className="sug-ok-badge">
                      <svg viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.4"/>
                        <path d="M4 7l2 2 4-4" stroke="currentColor" strokeWidth="1.4"
                          strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      Yüksek benzerlik yok
                    </span>
                  )}
                </div>
                <span className="sug-results-count">{results.total} sonuç</span>
              </div>

              {/* Kartlar */}
              <div className="sug-results">
                {(results.results||[]).map((r,i)=>(
                  <ResultCard key={r.pdf_name+i} result={r} rank={i+1} animDelay={i*35}/>
                ))}
                {results.total===0 && (
                  <div className="sug-no-results">
                    <p>Milvus'ta kayıtlı benzer proje bulunamadı.</p>
                    <span>Veritabanı boş olabilir veya eşik çok yüksek.</span>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
