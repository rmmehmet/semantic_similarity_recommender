import { useEffect, useState } from "react";

// Kaydırmayla değil, kendi kendine sürekli döngüde oynayan bir vitrin —
// her sahne SCENE_DURATION kadar aktif kalır, kendi iç animasyonunu
// (yazma efekti / kart ayrışması / graf çizimi / sohbet balonları)
// baştan sona oynatır, sonra bir sonraki sahneye geçilir. Sona gelince
// başa döner. Instagram Stories'teki gibi noktalara tıklayıp da
// istenen sahneye atlanabilir.
const SCENE_DURATION = 5200;
const SAMPLE_TITLE = "Derin öğrenme tabanlı görüntü sınıflandırma üzerine bir çalışma";

const SCENES = [
  { title: "Bir fikirle başlanır", desc: "Başlığınızı yazın ya da PDF'inizi sürükleyin — gerisini AltayAI halleder." },
  { title: "Bir belge, katmanlarına ayrılır", desc: "Başlık, özet ve içerik ayrı ayrı okunur — artık tek bir dosya değil, aranabilir bir bilgi kaynağıdır." },
  { title: "Kütüphanenizle karşılaştırılır", desc: "Yeni belge, geçmiş çalışmalarınızla eşleştirilir — özgünlüğünüz somut bir skora dönüşür." },
  { title: "Ve onunla konuşursunuz", desc: "Yanıtlar yalnızca sizin belgelerinize dayanır, hangi sayfadan geldiği kaynak olarak gösterilir." },
];

function useReducedMotion() {
  const [reduced] = useState(
    () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
  return reduced;
}

// Bir sahne aktif olduğu sürece 0'dan 1'e ilerleyen "yerel zaman" —
// sahnenin kendi iç animasyonunun tek kaynağı budur, kaydırmayla hiçbir
// ilgisi yok. Sahne pasif olunca sıfırlanır, tekrar aktif olduğunda
// baştan oynar.
function useLocalProgress(active, reducedMotion) {
  const [p, setP] = useState(reducedMotion ? 1 : 0);
  useEffect(() => {
    // reducedMotion: başlangıç değeri zaten 1, yeniden ayarlamaya gerek
    // yok. !active: sahne zaten görünmez (opacity:0), bayat bir p değeri
    // görsel bir etki yaratmaz — tekrar aktif olunca rAF döngüsü baştan
    // başlar ve p'yi (izin verilen, callback içi bir setState ile) günceller.
    if (reducedMotion || !active) return undefined;
    let raf;
    const start = performance.now();
    const tick = (now) => {
      const elapsed = now - start;
      const next = Math.min(1, elapsed / SCENE_DURATION);
      setP(next);
      if (next < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, reducedMotion]);
  return p;
}

function Caption({ index, title, desc }) {
  return (
    <div className="jr-caption">
      <span className="jr-caption__index">{String(index + 1).padStart(2, "0")}</span>
      <h3 className="jr-caption__title">{title}</h3>
      <p className="jr-caption__desc">{desc}</p>
    </div>
  );
}

function SceneWrap({ active, children }) {
  return <div className={`jr-scene${active ? " active" : ""}`}>{children}</div>;
}

// ── Sahne 1: bir fikirle başlanır (yazma/gönderme anı) ─────────────
function SceneInput({ active, reducedMotion }) {
  const p = useLocalProgress(active, reducedMotion);
  const typeP = Math.min(1, p / 0.7);
  const visibleChars = Math.round(typeP * SAMPLE_TITLE.length);
  const typedText = SAMPLE_TITLE.slice(0, visibleChars);
  const stillTyping = visibleChars < SAMPLE_TITLE.length;
  const buttonActive = p > 0.75;

  return (
    <SceneWrap active={active}>
      <div className="jr-visual jr-visual--input">
        <div className="jr-input-card">
          <span className="jr-input-card__label">Proje başlığı ya da özeti</span>
          <div className="jr-input-card__field">
            {typedText}
            {stillTyping && <span className="jr-input-cursor" />}
          </div>
          <div className="jr-input-card__row">
            <span className="jr-input-card__hint">ya da bir PDF sürükleyin</span>
            <button className={`jr-input-card__btn${buttonActive ? " active" : ""}`} tabIndex={-1}>
              Analiz Et
            </button>
          </div>
        </div>
      </div>
      <Caption index={0} {...SCENES[0]} />
    </SceneWrap>
  );
}

// ── Sahne 2: bir belge, üç katmana ayrılır ─────────────────────────
function SceneLayers({ active, reducedMotion }) {
  const p = useLocalProgress(active, reducedMotion);
  return (
    <SceneWrap active={active}>
      <div className="jr-visual jr-visual--layers">
        <div
          className="jr-doc-card jr-doc-card--title"
          style={{ transform: `translate3d(${p * -46}px, ${p * -58}px, ${p * 70}px) rotate(${p * -3.5}deg)` }}
        >
          <span className="jr-doc-card__label">Başlık</span>
          <div className="jr-doc-card__line jr-doc-card__line--wide" />
        </div>
        <div
          className="jr-doc-card jr-doc-card--abstract"
          style={{ transform: `scale(${1 - p * 0.03})`, opacity: 1 - p * 0.15 }}
        >
          <span className="jr-doc-card__label">Özet</span>
          <div className="jr-doc-card__line" />
          <div className="jr-doc-card__line" />
          <div className="jr-doc-card__line jr-doc-card__line--short" />
        </div>
        <div
          className="jr-doc-card jr-doc-card--content"
          style={{ transform: `translate3d(${p * 46}px, ${p * 58}px, ${p * -70}px) rotate(${p * 3.5}deg)` }}
        >
          <span className="jr-doc-card__label">İçerik</span>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="jr-doc-card__chunk" style={{ opacity: p > 0.35 + i * 0.12 ? 1 : 0.15 }} />
          ))}
        </div>
      </div>
      <Caption index={1} {...SCENES[1]} />
    </SceneWrap>
  );
}

// ── Sahne 3: kütüphanenizle karşılaştırılır ────────────────────────
function SceneCompare({ active, reducedMotion }) {
  const p = useLocalProgress(active, reducedMotion);
  const nodes = [
    { x: 78, y: 60, r: 1 },
    { x: 235, y: 40, r: 0.7 },
    { x: 250, y: 165, r: 0.85 },
    { x: 60, y: 190, r: 0.6 },
    { x: 165, y: 15, r: 0.55 },
  ];
  const cx = 160, cy = 110;
  const matchReveal = Math.max(0, (p - 0.55) / 0.35);

  return (
    <SceneWrap active={active}>
      <div className="jr-visual jr-visual--compare">
        <svg viewBox="0 0 320 220" className="jr-graph">
          {nodes.map((n, i) => {
            const len = Math.hypot(n.x - cx, n.y - cy) * 1.4;
            const reveal = Math.min(1, Math.max(0, p * 1.6 - i * 0.12));
            return (
              <line
                key={i}
                x1={cx} y1={cy} x2={n.x} y2={n.y}
                className="jr-graph__line"
                strokeDasharray={len}
                strokeDashoffset={len * (1 - reveal)}
              />
            );
          })}
          {nodes.map((n, i) => (
            <circle
              key={i}
              cx={n.x} cy={n.y} r={5 * n.r}
              className={`jr-graph__node${i === 2 ? " jr-graph__node--match" : ""}`}
              style={{ opacity: Math.min(1, Math.max(0, p * 1.6 - i * 0.12)) }}
            />
          ))}
          <circle cx={cx} cy={cy} r="8" className="jr-graph__node jr-graph__node--self" />
        </svg>
        <div className="jr-match-chip" style={{ opacity: matchReveal, transform: `translateY(${(1 - matchReveal) * 8}px)` }}>
          <span className="jr-match-chip__dot" />
          %87 benzerlik
        </div>
      </div>
      <Caption index={2} {...SCENES[2]} />
    </SceneWrap>
  );
}

// ── Sahne 4: ve onunla konuşursunuz ────────────────────────────────
function SceneChat({ active, reducedMotion }) {
  const p = useLocalProgress(active, reducedMotion);
  const showUser   = p > 0.12;
  const showTyping = p > 0.32 && p < 0.62;
  const showReply  = p > 0.55;
  const showCite   = p > 0.82;

  return (
    <SceneWrap active={active}>
      <div className="jr-visual jr-visual--chat">
        <div className="jr-chat">
          <div className={`jr-bubble jr-bubble--user${showUser ? " in" : ""}`}>
            Bu makalenin sonuçları neydi?
          </div>
          {showTyping && (
            <div className="jr-bubble jr-bubble--typing in">
              <span /><span /><span />
            </div>
          )}
          {showReply && (
            <div className="jr-bubble jr-bubble--reply in">
              Model, test setinde %94.2 doğruluk elde etmiş.
              {showCite && <span className="jr-bubble__cite">kaynak: makale.pdf, s.4</span>}
            </div>
          )}
        </div>
      </div>
      <Caption index={3} {...SCENES[3]} />
    </SceneWrap>
  );
}

export default function Journey() {
  const reducedMotion = useReducedMotion();
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (reducedMotion) return undefined;
    const t = setInterval(() => setActive((a) => (a + 1) % SCENES.length), SCENE_DURATION);
    return () => clearInterval(t);
  }, [reducedMotion]);

  return (
    <section className="jr-root" aria-label="AltayAI bir belgeyi nasıl işler">
      <div className="jr-stage">
        <SceneInput   active={active === 0} reducedMotion={reducedMotion} />
        <SceneLayers  active={active === 1} reducedMotion={reducedMotion} />
        <SceneCompare active={active === 2} reducedMotion={reducedMotion} />
        <SceneChat    active={active === 3} reducedMotion={reducedMotion} />
      </div>
      <div className="jr-dots" role="tablist" aria-label="Sahne seç">
        {SCENES.map((s, i) => (
          <button
            key={i}
            role="tab"
            aria-selected={active === i}
            aria-label={s.title}
            className={`jr-dot${active === i ? " active" : ""}`}
            onClick={() => setActive(i)}
          />
        ))}
      </div>
    </section>
  );
}
