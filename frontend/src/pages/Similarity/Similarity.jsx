import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { compareDocuments, compareHighlight, validatePdfFile } from "../../../services/service";
import UserMenu from "../../UserMenu";
import "./Similarity.css";

// ── Algoritma tanımları + eşikler ─────────────────────────────────
const ALGO = {
  bert:        { label: "BERT",        color: "#F472B6", high: 0.80, mid: 0.50 },
  cosine:      { label: "Cosine",      color: "#00D4FF", high: 0.70, mid: 0.40 },
  tfidf:       { label: "TF-IDF",      color: "#34D399", high: 0.70, mid: 0.40 },
  jaccard:     { label: "Jaccard",     color: "#A78BFA", high: 0.30, mid: 0.15 },
  levenshtein: { label: "Levenshtein", color: "#FB923C", high: 0.30, mid: 0.15 },
};

function levelFor(key, score) {
  const t = ALGO[key]; if (!t) return "low";
  return score >= t.high ? "high" : score >= t.mid ? "mid" : "low";
}
function hex2rgba(hex, a) {
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

// ── Navbar ─────────────────────────────────────────────────────────
function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <nav className="sim-nav">
      <button className="sim-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
        <span className="sim-logo-hex">A</span>
        <span className="sim-nav__brand">Altay<em>AI</em></span>
      </button>
      <ul className={`sim-nav__links${open ? " open" : ""}`}>
        {[["PDF Bölme","/split"],["Benzerlik Arama","/search"],["Proje Öneri","/suggest"], ["Veritabanı","/database"]].map(([l,p]) => (
          <li key={p}><button className={`sim-nav__link${p==="/search"?" active":""}`}
            onClick={() => { navigate(p); setOpen(false); }}>{l}</button></li>
        ))}
      </ul>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <UserMenu />
        <button className="sim-nav__burger" onClick={() => setOpen(v=>!v)}><span/><span/><span/></button>
      </div>
    </nav>
  );
}

function PdfIcon() {
  return (
    <svg style={{width:14,height:14,flexShrink:0}} viewBox="0 0 16 16" fill="none">
      <path d="M9 2H4a1 1 0 00-1 1v10a1 1 0 001 1h8a1 1 0 001-1V6L9 2z" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M9 2v4h4" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  );
}
function b64url(b64) {
  const chars = atob(b64); const bytes = new Uint8Array(chars.length);
  for (let i = 0; i < chars.length; i++) bytes[i] = chars.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type:"application/pdf" }));
}

// ── CompareModal ───────────────────────────────────────────────────
function CompareModal({ targetFile, compareFile, compareName, searchType, onClose }) {
  const [phase, setPhase] = useState("loading");
  const [data,  setData]  = useState(null);
  const [error, setError] = useState(null);
  const tRef = useRef(null), cRef = useRef(null);

  useEffect(() => {
    setPhase("loading"); setData(null); setError(null);
    compareHighlight(targetFile, compareFile, searchType)
      .then(res => {
        tRef.current = b64url(res.target_pdf);
        cRef.current = b64url(res.compare_pdf);
        setData({ ...res, tUrl: tRef.current, cUrl: cRef.current });
        setPhase("done");
      })
      .catch(e => { setError(e.message); setPhase("error"); });
    return () => {
      tRef.current && URL.revokeObjectURL(tRef.current);
      cRef.current && URL.revokeObjectURL(cRef.current);
    };
  }, []);

  return (
    <div className="sim-modal-overlay" onClick={onClose}>
      <div className="sim-modal" onClick={e => e.stopPropagation()}>

        {/* ── Header ── */}
        <div className="sim-modal__hdr">
          <div className="sim-modal__hdr-left">
            <span className="sim-modal__eyebrow">
              <span className="sim-modal__eyebrow-dot"/>
              Semantik Benzerlik Görselleştirme
            </span>
            <div className="sim-modal__files">
              <div className="sim-modal__file sim-modal__file--a">
                <PdfIcon/>
                <span className="sim-modal__file-tag">Hedef</span>
                <span className="sim-modal__file-name">{targetFile?.name}</span>
              </div>
              <div className="sim-modal__arrow">
                <svg viewBox="0 0 36 12" fill="none">
                  <line x1="0" y1="6" x2="30" y2="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 2"/>
                  <path d="M26 2l6 4-6 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="sim-modal__file sim-modal__file--b">
                <PdfIcon/>
                <span className="sim-modal__file-tag">Karşılaştırılan</span>
                <span className="sim-modal__file-name">{compareName}</span>
              </div>
            </div>
          </div>

          {phase === "done" && data && (
            <div className="sim-modal__infobadges">
              <div className="sim-modal__infobadge">
                <span className="sim-modal__infobadge-dot"/>
                <span>İşaretlenen cümle</span>
                <strong>{(data.target_sentences||0) + (data.compare_sentences||0)}</strong>
              </div>
              <div className="sim-modal__legend">
                <span className="sim-modal__legend-swatch" style={{background:"#FF7300"}}/>
                <span>Özdeş (%95+)</span>
              </div>
              <div className="sim-modal__legend">
                <span className="sim-modal__legend-swatch" style={{background:"#FFD200"}}/>
                <span>Semantik benzer (%80+)</span>
              </div>
            </div>
          )}

          <button className="sim-modal__close" onClick={onClose}>
            <svg viewBox="0 0 20 20" fill="none">
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="sim-modal__body">
          {phase === "loading" && (
            <div className="sim-modal__center">
              <div className="sim-ring"><div/><div/><div/><div/></div>
              <p>Semantik analiz yapılıyor…</p>
              <span>BERT ile cümle bazlı benzerlik · %80+ eşiği uygulanıyor</span>
            </div>
          )}
          {phase === "error" && (
            <div className="sim-modal__center sim-modal__center--err">
              <svg viewBox="0 0 48 48" fill="none">
                <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="2"/>
                <line x1="24" y1="13" x2="24" y2="27" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
                <circle cx="24" cy="34" r="2.2" fill="currentColor"/>
              </svg>
              <p>{error}</p>
              <button className="sim-btn sim-btn--ghost" onClick={onClose}>Kapat</button>
            </div>
          )}
          {phase === "done" && data && (
            <div className="sim-modal__pdfs">
              <div className="sim-modal__pane">
                <div className="sim-modal__pane-label sim-modal__pane-label--a">
                  <span className="sim-modal__pane-dot sim-modal__pane-dot--a"/>
                  Hedef PDF
                  <span className="sim-modal__pane-fname">{targetFile?.name}</span>
                </div>
                <iframe src={data.tUrl} className="sim-modal__iframe" title="Hedef"/>
              </div>
              <div className="sim-modal__vdivider">
                <div className="sim-modal__vdivider-line"/>
                <div className="sim-modal__vdivider-badge">VS</div>
                <div className="sim-modal__vdivider-line"/>
              </div>
              <div className="sim-modal__pane">
                <div className="sim-modal__pane-label sim-modal__pane-label--b">
                  <span className="sim-modal__pane-dot sim-modal__pane-dot--b"/>
                  Karşılaştırılan PDF
                  <span className="sim-modal__pane-fname">{compareName}</span>
                </div>
                <iframe src={data.cUrl} className="sim-modal__iframe" title="Karşılaştırılan"/>
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="sim-modal__ftr">
          {phase === "done" && data?.sample_pairs?.length > 0 && (
            <div className="sim-modal__pairs">
              <span className="sim-modal__pairs-label">Örnek semantik benzer cümleler:</span>
              {data.sample_pairs.slice(0,3).map(([t,c,score],i) => (
                <div className="sim-modal__pair" key={i}>
                  <div className="sim-modal__pair-sent sim-modal__pair-sent--a"><span>{t}</span></div>
                  <div className={`sim-modal__pair-score${score>=0.95?" sim-modal__pair-score--identical":""}`}>
                    %{Math.round(score*100)}
                  </div>
                  <div className="sim-modal__pair-sent sim-modal__pair-sent--b"><span>{c}</span></div>
                </div>
              ))}
            </div>
          )}
          <button className="sim-btn sim-btn--ghost" onClick={onClose}>Kapat</button>
        </div>
      </div>
    </div>
  );
}

// ── Algoritma Tab ──────────────────────────────────────────────────
function AlgoTab({ algoKey, meta, bestScore, bestName, isActive, onClick }) {
  const pct   = Math.round((bestScore||0)*100);
  const level = levelFor(algoKey, bestScore||0);

  const activeStyle = isActive ? {
    background: hex2rgba(meta.color, 0.1),
    borderColor: hex2rgba(meta.color, 0.6),
    boxShadow: `0 0 20px ${hex2rgba(meta.color, 0.18)}`,
  } : {};

  return (
    <button
      className={`sim-algo-tab${isActive?" sim-algo-tab--active":""}`}
      style={{ borderTopColor: meta.color, ...activeStyle }}
      onClick={onClick}
    >
      <div className="sim-algo-tab__top">
        <span className="sim-algo-tab__name" style={{ color: isActive ? meta.color : undefined }}>
          {meta.label}
        </span>
        {isActive && (
          <span className="sim-algo-tab__pip" style={{ background: meta.color, boxShadow: `0 0 6px ${meta.color}` }}/>
        )}
      </div>
      <span className="sim-algo-tab__score" style={{ color: meta.color }}>%{pct}</span>
      <span className="sim-algo-tab__doc">{(bestName||"").replace(/\.pdf$/i,"").slice(0,18)||"—"}</span>
      <div className="sim-algo-tab__footer">
        <span className={`sim-algo-tab__level sim-algo-tab__level--${level}`}>
          {level==="high"?"⚠ Yüksek":level==="mid"?"Orta":"Düşük"}
        </span>
        <span className="sim-algo-tab__threshold">%{Math.round(meta.high*100)}+</span>
      </div>
    </button>
  );
}

// ── Sonuç Kartı ────────────────────────────────────────────────────
function ResultCard({ result, rank, activeAlgo, onCompare, animDelay }) {
  const meta  = ALGO[activeAlgo];
  const score = result.algo_scores?.[activeAlgo] || 0;
  const pct   = Math.round(score * 100);
  const level = levelFor(activeAlgo, score);
  const LABELS = { high:"Yüksek Benzerlik", mid:"Orta Benzerlik", low:"Düşük Benzerlik" };

  const borderColor = level==="high" ? "#EF4444" : level==="mid" ? "#F59E0B" : "transparent";

  return (
    <div className="sim-rcard" style={{ borderLeftColor: borderColor, animationDelay:`${animDelay}ms` }}>
      <div className="sim-rcard__rank"><span>{String(rank).padStart(2,"0")}</span></div>

      <div className="sim-rcard__body">
        <div className="sim-rcard__top">
          <h3 className="sim-rcard__name" title={result.name}>{result.name}</h3>
          <span className={`sim-badge sim-badge--${level}`}>{LABELS[level]}</span>
        </div>

        {/* Ana bar — aktif algoritmaya göre */}
        <div className="sim-rcard__mainbar-row">
          <div className="sim-rcard__mainbar">
            <div className="sim-rcard__mainbar-fill" style={{
              width: `${pct}%`,
              background: level==="high"
                ? `linear-gradient(90deg,${meta.color},${meta.color}99)`
                : level==="mid"
                ? "linear-gradient(90deg,#F59E0B,#FCD34D)"
                : "linear-gradient(90deg,#22C55E,#4ADE80)",
            }}/>
          </div>
          <span className="sim-rcard__mainpct" style={{ color: meta.color }}>%{pct}</span>
        </div>

        {/* 5 algo mini satır */}
        <div className="sim-rcard__algos">
          {Object.entries(ALGO).map(([key,m]) => {
            const s  = result.algo_scores?.[key]||0;
            const p  = Math.round(s*100);
            const lv = levelFor(key,s);
            const isAct = key===activeAlgo;
            return (
              <div className={`sim-algo-row${isAct?" sim-algo-row--active":""}`} key={key}>
                <span className="sim-algo-row__name" style={{ color: m.color }}>{m.label}</span>
                <div className="sim-algo-row__track">
                  <div className="sim-algo-row__fill" style={{
                    width:`${p}%`,
                    background: lv==="high"?m.color:lv==="mid"?"#F59E0B":"#22C55E",
                    opacity: isAct?1:0.45,
                  }}/>
                </div>
                <span className={`sim-algo-row__pct${lv==="high"?" sim-algo-row__pct--hl":""}`}>%{p}</span>
                {lv==="high"&&<span className="sim-algo-row__warn">⚠</span>}
              </div>
            );
          })}
        </div>
      </div>

      <button className="sim-rcard__cta" onClick={() => onCompare(result.name)}>
        <div className="sim-rcard__cta-icon">
          <svg viewBox="0 0 28 28" fill="none">
            <rect x="2"  y="3" width="11" height="22" rx="2" stroke="currentColor" strokeWidth="1.8"/>
            <rect x="15" y="3" width="11" height="22" rx="2" stroke="currentColor" strokeWidth="1.8"/>
            <line x1="5"  y1="9"  x2="10" y2="9"  stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <line x1="18" y1="9"  x2="23" y2="9"  stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <line x1="5"  y1="13" x2="10" y2="13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <line x1="18" y1="13" x2="23" y2="13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <line x1="5"  y1="17" x2="8"  y2="17" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
            <line x1="18" y1="17" x2="21" y2="17" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </div>
        <span>Karşılaştır</span>
        <span className="sim-rcard__cta-hint">Yan yana gör</span>
      </button>
    </div>
  );
}

// ── Drop bileşenleri ───────────────────────────────────────────────
function SingleDrop({ label, file, onFile, accent, onError }) {
  const [drag, setDrag] = useState(false);
  const ref = useRef(null);
  const handle = f => {
    if (!f) return;
    const err = validatePdfFile(f);
    if (err) { onError?.(err); return; }
    onFile(f);
  };
  return (
    <div className={`sim-drop${drag?" drag":""}${file?" filled":""}`} style={{"--da":accent}}
      onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)}
      onDrop={e=>{e.preventDefault();setDrag(false);handle(e.dataTransfer.files[0])}}
      onClick={()=>ref.current?.click()}>
      <input ref={ref} type="file" accept=".pdf" style={{display:"none"}} onChange={e=>handle(e.target.files[0])}/>
      {file ? (
        <div className="sim-drop__filled">
          <svg className="sim-drop__ficon" viewBox="0 0 28 28" fill="none">
            <path d="M16 2H6a2 2 0 00-2 2v20a2 2 0 002 2h16a2 2 0 002-2V9l-8-7z" stroke="currentColor" strokeWidth="1.6"/>
            <path d="M16 2v7h7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
          </svg>
          <div>
            <div className="sim-drop__fname">{file.name}</div>
            <div className="sim-drop__fsize">{(file.size/1024/1024).toFixed(2)} MB</div>
          </div>
          <button className="sim-drop__rm" onClick={e=>{e.stopPropagation();onFile(null)}}>
            <svg viewBox="0 0 14 14" fill="none"><path d="M3 3l8 8M11 3L3 11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
          </button>
        </div>
      ) : (
        <div className="sim-drop__empty">
          <svg viewBox="0 0 36 36" fill="none">
            <path d="M18 2H8a2 2 0 00-2 2v28a2 2 0 002 2h20a2 2 0 002-2V12l-8-10z" stroke="currentColor" strokeWidth="1.6" opacity=".5"/>
            <path d="M18 2v10h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity=".5"/>
            <path d="M18 20v8M14 24l4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>{label}</span><em>PDF sürükle veya tıkla</em>
        </div>
      )}
    </div>
  );
}

function MultiDrop({ files, onFiles, onError }) {
  const ref = useRef(null);
  const add = list => {
    const all = Array.from(list);
    const pdfs = [];
    for (const f of all) {
      const err = validatePdfFile(f);
      if (err) onError?.(`${f.name}: ${err}`);
      else pdfs.push(f);
    }
    onFiles(prev => { const names=new Set(prev.map(f=>f.name)); return [...prev,...pdfs.filter(f=>!names.has(f.name))]; });
  };
  const rm = name => onFiles(prev => prev.filter(f=>f.name!==name));
  return (
    <div className="sim-multidrop">
      <div className="sim-multidrop__zone"
        onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();add(e.dataTransfer.files)}}
        onClick={()=>ref.current?.click()}>
        <input ref={ref} type="file" accept=".pdf" multiple style={{display:"none"}} onChange={e=>add(e.target.files)}/>
        <svg viewBox="0 0 20 20" fill="none">
          <path d="M10 4v8M6 8l4-4 4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="4" y1="17" x2="16" y2="17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
        <span>PDF'leri yükle</span>
        {files.length>0 && <em>{files.length} dosya</em>}
      </div>
      {files.length>0 && (
        <div className="sim-multidrop__list">
          {files.map((f,i) => (
            <div key={f.name} className="sim-multidrop__item">
              <span className="sim-multidrop__num">{String(i+1).padStart(2,"0")}</span>
              <svg viewBox="0 0 14 14" fill="none" className="sim-multidrop__icon">
                <path d="M8 1H3a1 1 0 00-1 1v10a1 1 0 001 1h8a1 1 0 001-1V5L8 1z" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M8 1v4h4" stroke="currentColor" strokeWidth="1.2"/>
              </svg>
              <span className="sim-multidrop__fname">{f.name}</span>
              <span className="sim-multidrop__fsize">{(f.size/1024/1024).toFixed(1)}M</span>
              <button className="sim-multidrop__rm" onClick={()=>rm(f.name)}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Ana bileşen ────────────────────────────────────────────────────
export default function Similarity() {
  const [targetFile,   setTargetFile]   = useState(null);
  const [compareFiles, setCompareFiles] = useState([]);
  const [searchType,   setSearchType]   = useState("fulltext");
  const [loading,      setLoading]      = useState(false);
  const [results,      setResults]      = useState(null);
  const [error,        setError]        = useState(null);
  const [activeAlgo,   setActiveAlgo]   = useState("bert");
  const [modal,        setModal]        = useState(null);

  const fileMap = Object.fromEntries(compareFiles.map(f=>[f.name,f]));

  const runAnalysis = useCallback(async () => {
    if (!targetFile||compareFiles.length===0) { setError("Hedef PDF ve en az bir karşılaştırma PDF'i seçin."); return; }
    setLoading(true); setError(null); setResults(null);
    try {
      const data = await compareDocuments(targetFile, compareFiles, searchType);
      if (!data.success) throw new Error(data.error||"Karşılaştırma başarısız");
      setResults(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }, [targetFile,compareFiles,searchType]);

  const openCompare = name => {
    const cf = fileMap[name];
    if (!cf) { setError("Karşılaştırma dosyası bulunamadı."); return; }
    setModal({ name, file: cf });
  };

  const sorted = results
    ? [...(results.combined||[])].sort((a,b)=>(b.algo_scores?.[activeAlgo]||0)-(a.algo_scores?.[activeAlgo]||0))
    : [];

  const TYPES = [["fulltext","Tam Metin"],["abstract","Özet"],["title","Başlık"]];

  return (
    <div className="sim-root">
      <Navbar/>

      <div className="sim-header">
        <div className="sim-header__inner">
          <div className="sim-breadcrumb">
            AltayAI
            <svg viewBox="0 0 10 10" fill="none"><path d="M3 2l4 3-4 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></svg>
            <span>Benzerlik Analizi</span>
          </div>
          <h1 className="sim-header__title">Anlamsal <em>Benzerlik</em> Analizi</h1>
          <p className="sim-header__sub">5 algoritma · PDF bazlı karşılaştırma · BERT semantik cümle highlight</p>
        </div>
        <div className="sim-header__grid"/>
      </div>

      <div className="sim-layout">
        {/* Sidebar */}
        <aside className="sim-sidebar">
          <section className="sim-panel">
            <div className="sim-panel__label"><span className="sim-dot sim-dot--cyan"/>Hedef PDF</div>
            <SingleDrop label="Hedef PDF'i seç" file={targetFile} onFile={setTargetFile} accent="#00D4FF" onError={setError}/>
          </section>

          <section className="sim-panel">
            <div className="sim-panel__label"><span className="sim-dot sim-dot--violet"/>Karşılaştırma PDF'leri</div>
            <MultiDrop files={compareFiles} onFiles={setCompareFiles} onError={setError}/>
          </section>

          <section className="sim-panel">
            <div className="sim-panel__label">Karşılaştırma Modu</div>
            <div className="sim-type-btns">
              {TYPES.map(([v,l]) => (
                <button key={v} className={`sim-type-btn${searchType===v?" active":""}`}
                  onClick={()=>setSearchType(v)}>{l}</button>
              ))}
            </div>
          </section>

          <button className="sim-run-btn" onClick={runAnalysis}
            disabled={loading||!targetFile||compareFiles.length===0}>
            {loading ? (
              <><span className="sim-spin"/><span>Analiz ediliyor…</span></>
            ) : (
              <><svg viewBox="0 0 20 20" fill="none">
                <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.8"/>
                <line x1="13.5" y1="13.5" x2="18" y2="18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
              </svg><span>Benzerlik Analizi Başlat</span></>
            )}
          </button>

          {/* Eşik paneli — tıklayarak algoritma değiştir */}
          <section className="sim-panel">
            <div className="sim-panel__label">Algoritma Seç · Eşikler</div>
            <div className="sim-thresholds">
              {Object.entries(ALGO).map(([k,m]) => {
                const isAct = activeAlgo===k;
                return (
                  <button key={k}
                    className={`sim-thr-row${isAct?" sim-thr-row--active":""}`}
                    style={isAct
                      ? { background: hex2rgba(m.color,0.1), borderColor: hex2rgba(m.color,0.4), color: m.color }
                      : {}}
                    onClick={()=>setActiveAlgo(k)}>
                    <div className="sim-thr-row__left">
                      <span className="sim-thr-row__dot" style={{ background: m.color }}/>
                      <span className="sim-thr-row__name" style={{ color: isAct ? m.color : undefined }}>{m.label}</span>
                    </div>
                    <span className="sim-thr-row__val">%{Math.round(m.high*100)}+</span>
                  </button>
                );
              })}
            </div>
          </section>

          {results && (
            <section className="sim-panel sim-panel--stats">
              {[
                {l:"Karşılaştırılan", v:compareFiles.length},
                {l:"Algoritma",       v:5},
                {l:"BERT En Yüksek",  v:`%${Math.round((results.results?.bert?.[0]?.score||0)*100)}`, accent:true},
              ].map(s=>(
                <div className="sim-srow" key={s.l}>
                  <span>{s.l}</span>
                  <span className={`sim-srow__val${s.accent?" accent":""}`}>{s.v}</span>
                </div>
              ))}
            </section>
          )}
        </aside>

        {/* Ana panel */}
        <main className="sim-main">
          {error && (
            <div className="sim-err">
              <svg viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.8"/>
                <line x1="10" y1="6" x2="10" y2="11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                <circle cx="10" cy="14" r=".8" fill="currentColor"/>
              </svg>
              <span>{error}</span><button onClick={()=>setError(null)}>✕</button>
            </div>
          )}

          {!results&&!loading && (
            <div className="sim-empty">
              <div className="sim-empty__art">
                <svg viewBox="0 0 160 100" fill="none">
                  <rect x="8"  y="12" width="60" height="78" rx="4" stroke="currentColor" strokeWidth="1.5" opacity=".2"/>
                  <rect x="92" y="12" width="60" height="78" rx="4" stroke="currentColor" strokeWidth="1.5" opacity=".2"/>
                  {[24,33,42,51,60,69].map((y,i)=>(
                    <line key={"l"+i} x1="18" y1={y} x2={i%2===0?55:45} y2={y} stroke="currentColor"
                      strokeWidth="1.2" strokeLinecap="round" opacity={i<2?".18":".3"} strokeDasharray={i>=2?"5 2":"0"}/>
                  ))}
                  {[24,33,42,51,60,69].map((y,i)=>(
                    <line key={"r"+i} x1="102" y1={y} x2={i%2===0?145:135} y2={y} stroke="currentColor"
                      strokeWidth="1.2" strokeLinecap="round" opacity={i<2?".18":".3"} strokeDasharray={i>=2?"5 2":"0"}/>
                  ))}
                  <path d="M72 50 Q80 42 88 50" stroke="#A78BFA" strokeWidth="1.8" strokeDasharray="4 2" opacity=".6"/>
                  <circle cx="80" cy="50" r="6" stroke="#A78BFA" strokeWidth="1.5" opacity=".5"/>
                </svg>
              </div>
              <p>PDF'leri yükleyip analiz başlatın</p>
              <span>5 algoritma · BERT %80+ semantik cümle highlight</span>
            </div>
          )}

          {loading && (
            <div className="sim-loading">
              <div className="sim-ring"><div/><div/><div/><div/></div>
              <p>Benzerlik analizi yapılıyor…</p>
              <div className="sim-loading__algos">
                {Object.values(ALGO).map(a=><span key={a.label} style={{color:a.color}}>{a.label}</span>)}
              </div>
            </div>
          )}

          {results&&!loading && (
            <>
              {/* Algoritma tab'ları */}
              <div className="sim-algo-tabs">
                {Object.entries(ALGO).map(([key,meta]) => {
                  const best = (results.results?.[key]||[])[0];
                  return (
                    <AlgoTab key={key} algoKey={key} meta={meta}
                      bestScore={best?.score||0} bestName={best?.name||""}
                      isActive={activeAlgo===key} onClick={()=>setActiveAlgo(key)}/>
                  );
                })}
              </div>

              {/* Aktif algo başlık */}
              <div className="sim-results-hdr">
                <div className="sim-results-hdr__left">
                  <span className="sim-results-hdr__dot"
                    style={{ background: ALGO[activeAlgo]?.color, boxShadow:`0 0 6px ${ALGO[activeAlgo]?.color}` }}/>
                  <span className="sim-results-title">{ALGO[activeAlgo]?.label} Sonuçları</span>
                  <span className="sim-results-threshold">
                    yüksek ≥ %{Math.round((ALGO[activeAlgo]?.high||0)*100)}
                  </span>
                </div>
                <span className="sim-results-count">{sorted.length} sonuç</span>
              </div>

              {/* Kart listesi */}
              <div className="sim-results">
                {sorted.map((r,i)=>(
                  <ResultCard key={r.name} result={r} rank={i+1}
                    activeAlgo={activeAlgo} onCompare={openCompare} animDelay={i*40}/>
                ))}
              </div>
            </>
          )}
        </main>
      </div>

      {modal && (
        <CompareModal targetFile={targetFile} compareFile={modal.file}
          compareName={modal.name} searchType={searchType} onClose={()=>setModal(null)}/>
      )}
    </div>
  );
}