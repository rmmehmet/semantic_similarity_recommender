import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import UserMenu from "../../UserMenu";
import HeroCinema from "./HeroCinema";
import "./Home.css";

const NAV_LINKS = [
  { label: "PDF Bölme",  path: "/split",    icon: "⬡" },
  { label: "PDF Sohbet", path: "/chat",     icon: "⬡" },
  { label: "Proje Öneri", path: "/suggest",  icon: "⬡" },
  { label: "Kütüphanem",  path: "/database", icon: "⬡" },
];

const FEATURES = [
  {
    path: "/split",
    icon: (
      <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="6" width="22" height="30" rx="2" stroke="currentColor" strokeWidth="2"/>
        <rect x="18" y="12" width="22" height="30" rx="2" stroke="currentColor" strokeWidth="2" strokeDasharray="4 2"/>
        <line x1="8" y1="20" x2="30" y2="20" stroke="currentColor" strokeWidth="2"/>
        <line x1="8" y1="28" x2="30" y2="28" stroke="currentColor" strokeWidth="2"/>
      </svg>
    ),
    tag: "01",
    title: "PDF Bölme",
    subtitle: "Bildiri kitaplarını otomatik olarak ayrıştır",
    desc: "Font büyüklüğü analizi ile PDF'leri bölümlere ayır, her bildiriyi bağımsız dosya olarak çıkart.",
    accent: "#00D4FF",
  },
  {
    path: "/chat",
    icon: (
      <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 10h32v22H18l-8 8V10z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
        <line x1="14" y1="18" x2="34" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <line x1="14" y1="25" x2="26" y2="25" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    tag: "02",
    title: "PDF Sohbet",
    subtitle: "Belgelerinle doğal dilde konuş",
    desc: "İstediğin PDF'leri seç ve sadece onlar hakkında soru sor, ya da hiçbir şey seçmeden tüm kütüphanende arama yap.",
    accent: "#A78BFA",
  },
  {
    path: "/suggest",
    icon: (
      <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M24 6 L28 18 L40 18 L30 26 L34 38 L24 30 L14 38 L18 26 L8 18 L20 18 Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      </svg>
    ),
    tag: "03",
    title: "Proje Öneri",
    subtitle: "Yapay zeka destekli özgünleştirme önerileri",
    desc: "Yüksek benzerlik tespit edildiğinde, projenizi özgünleştirmenize yardımcı olacak alternatif konu önerileri üretir.",
    accent: "#34D399",
  },
  {
    path: "/database",
    icon: (
      <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <ellipse cx="24" cy="12" rx="16" ry="6" stroke="currentColor" strokeWidth="2"/>
        <path d="M8 12v12c0 3.314 7.163 6 16 6s16-2.686 16-6V12" stroke="currentColor" strokeWidth="2"/>
        <path d="M8 24v12c0 3.314 7.163 6 16 6s16-2.686 16-6V24" stroke="currentColor" strokeWidth="2"/>
      </svg>
    ),
    tag: "04",
    title: "Kütüphanem",
    subtitle: "Belge kütüphanesi yönetimi",
    desc: "Yüklediğiniz her PDF otomatik olarak işlenir ve dizinlenir — ekleyin, önizleyin, silin, arayın.",
    accent: "#F59E0B",
  },
];

// Animated counter
function Counter({ target, suffix = "" }) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        let start = 0;
        const step = Math.ceil(target / 60);
        const t = setInterval(() => {
          start += step;
          if (start >= target) { setVal(target); clearInterval(t); }
          else setVal(start);
        }, 20);
        obs.disconnect();
      }
    }, { threshold: 0.5 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target]);
  return <span ref={ref}>{val}{suffix}</span>;
}

// Particle canvas
function ParticleField() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let W = (canvas.width  = window.innerWidth);
    let H = (canvas.height = window.innerHeight);
    const pts = Array.from({ length: 90 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35,
      r: Math.random() * 1.6 + .4,
    }));
    let raf;
    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      pts.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
        if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0,212,255,0.45)";
        ctx.fill();
      });
      for (let i = 0; i < pts.length; i++)
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 120) {
            ctx.beginPath();
            ctx.moveTo(pts[i].x, pts[i].y);
            ctx.lineTo(pts[j].x, pts[j].y);
            ctx.strokeStyle = `rgba(0,212,255,${0.12 * (1 - d / 120)})`;
            ctx.lineWidth = .6;
            ctx.stroke();
          }
        }
      raf = requestAnimationFrame(draw);
    };
    draw();
    const onResize = () => {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", onResize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); };
  }, []);
  return <canvas ref={canvasRef} className="hm-canvas" />;
}

export default function Home() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled]   = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <div className="hm-root">
      {/* ── Navbar ── */}
      <nav className={`hm-nav${scrolled ? " hm-nav--scrolled" : ""}`}>
        <button className="hm-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
          <span className="hm-nav__logo-mark">A</span>
          <span className="hm-nav__logo-text">Altay<em>AI</em></span>
        </button>
        <ul className={`hm-nav__links${menuOpen ? " open" : ""}`}>
          {NAV_LINKS.map(l => (
            <li key={l.path}>
              <button className="hm-nav__link" onClick={() => { navigate(l.path); setMenuOpen(false); }}>
                <span className="hm-nav__link-icon">{l.icon}</span>
                {l.label}
              </button>
            </li>
          ))}
        </ul>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <UserMenu />
          <button className="hm-nav__burger" onClick={() => setMenuOpen(p => !p)} aria-label="Menü">
            <span /><span /><span />
          </button>
        </div>
      </nav>

      {/* ── Hero: tek, sürekli oynayan sinematik açılış ── */}
      <section className="hm-hero">
        <ParticleField />
        <div className="hm-hero__grid-overlay" />

        <div className="hm-hero__badge">
          <span className="hm-hero__badge-dot" />
          Akademik Belge Zekası
        </div>

        <HeroCinema />
      </section>

      {/* ── Stats: tek bir cümleye gömülü rakamlar ── */}
      <section className="hm-stats">
        <p className="hm-stats__line">
          Kütüphanenizi <span className="hm-stats__num" style={{ color: "#00D4FF" }}><Counter target={4} /></span> temel
          özellikle işler, aramayı <span className="hm-stats__num" style={{ color: "#A78BFA" }}><Counter target={3} /></span> farklı
          modda çalıştırır, <span className="hm-stats__num" style={{ color: "#34D399" }}><Counter target={80} suffix="%" /></span> üzerindeki
          benzerlikte sizi uyarır ve verdiği her yanıtı kaynağıyla gösterir.
        </p>
      </section>

      {/* ── Modüller: bir belgenin dört yöne dağılışı ── */}
      <section className="hm-features">
        <div className="hm-features__header">
          <span className="hm-section-tag">Modüller</span>
          <h2 className="hm-section-title">Bir Belge, Dört Yön</h2>
          <p className="hm-features__lede">Yüklediğiniz her belge, aynı anda dört farklı işleve akar.</p>
        </div>

        <svg className="hm-hub" viewBox="0 0 400 190" aria-hidden="true">
          <line x1="200" y1="95" x2="66" y2="34" className="hm-hub__spoke" stroke={FEATURES[0].accent} />
          <line x1="200" y1="95" x2="334" y2="34" className="hm-hub__spoke" stroke={FEATURES[1].accent} />
          <line x1="200" y1="95" x2="66" y2="156" className="hm-hub__spoke" stroke={FEATURES[2].accent} />
          <line x1="200" y1="95" x2="334" y2="156" className="hm-hub__spoke" stroke={FEATURES[3].accent} />
          <circle cx="200" cy="95" r="9" className="hm-hub__core" />
          <circle cx="66" cy="34" r="4.5" fill={FEATURES[0].accent} />
          <circle cx="334" cy="34" r="4.5" fill={FEATURES[1].accent} />
          <circle cx="66" cy="156" r="4.5" fill={FEATURES[2].accent} />
          <circle cx="334" cy="156" r="4.5" fill={FEATURES[3].accent} />
        </svg>

        <div className="hm-module-list">
          {FEATURES.map((f) => (
            <button
              key={f.path}
              className="hm-module"
              style={{ "--accent": f.accent }}
              onClick={() => navigate(f.path)}
            >
              <span className="hm-module__index">{f.tag}</span>
              <span className="hm-module__icon">{f.icon}</span>
              <span className="hm-module__text">
                <span className="hm-module__title">{f.title}</span>
                <span className="hm-module__subtitle">{f.subtitle}</span>
                <span className="hm-module__desc">{f.desc}</span>
              </span>
              <span className="hm-module__arrow">
                <svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12M10 4l6 6-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="hm-cta">
        <div className="hm-cta__glow" />
        <div className="hm-cta__inner">
          <h2 className="hm-cta__title">Projenizi Şimdi Analiz Edin</h2>
          <p className="hm-cta__sub">Özgün bir proje fikri geliştirmenin ilk adımı belgelerinizle konuşmaktan geçer.</p>
          <div className="hm-cta__btns">
            <button className="hm-btn hm-btn--primary hm-btn--lg" onClick={() => navigate("/chat")}>
              <span>PDF Sohbet</span>
              <svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12M10 4l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
            <button className="hm-btn hm-btn--ghost hm-btn--lg" onClick={() => navigate("/suggest")}>
              Proje Öneri
            </button>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="hm-footer">
        <div className="hm-footer__row">
          <div className="hm-footer__logo">
            <span className="hm-nav__logo-mark">A</span>
            <span className="hm-nav__logo-text">Altay<em>AI</em></span>
          </div>
          <p className="hm-footer__copy">AltayAI · Akademik Belge Zekası</p>
          <div className="hm-footer__links">
            {NAV_LINKS.map(l => (
              <button key={l.path} className="hm-footer__link" onClick={() => navigate(l.path)}>
                {l.label}
              </button>
            ))}
          </div>
        </div>
        <div className="hm-footer__credit">
          <span>Geliştirici: Mehmet Uzun</span>
          <span className="hm-footer__credit-sep">·</span>
          <a href="https://rmmehmet.github.io/" target="_blank" rel="noopener noreferrer">Site</a>
          <a href="https://github.com/rmmehmet" target="_blank" rel="noopener noreferrer">GitHub</a>
          <a href="https://www.linkedin.com/in/ramazan-mehmet-uzun/" target="_blank" rel="noopener noreferrer">LinkedIn</a>
        </div>
      </footer>
    </div>
  );
}
