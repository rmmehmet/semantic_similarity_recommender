import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import gsap from "gsap";

// Tek, sürekli döngüde oynayan sinematik açılış: başlık canlı yazılır,
// yazılan cümle bir belgeye dönüşür, belge katmanlarına ayrılır,
// kütüphaneyle karşılaştırılır, bir sohbete dönüşür ve son olarak gerçek
// ürün arayüzüne kristalleşir. Görmek için kaydırmaya gerek yok — hero
// yüklendiği an kendi kendine oynar. Her animasyon gerçek bir ürün
// davranışını temsil eder (bkz. AltayAI: başlık yaz → belge işlensin →
// kütüphaneyle kıyasla → belgeyle konuş).
const HEADLINE = "Projeniz ne kadar özgün?";

function useReducedMotion() {
  const [reduced] = useState(
    () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
  return reduced;
}

export default function HeroCinema() {
  const navigate = useNavigate();
  const rootRef = useRef(null);
  const typedRef = useRef(null);
  const reducedMotion = useReducedMotion();
  const [ctaVisible, setCtaVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setCtaVisible(true), reducedMotion ? 0 : 1400);
    return () => clearTimeout(t);
  }, [reducedMotion]);

  useEffect(() => {
    if (reducedMotion || !rootRef.current) return undefined;

    const ctx = gsap.context(() => {
      const typed = { n: 0 };
      const tl = gsap.timeline({ repeat: -1, defaults: { ease: "power2.out" } });

      // Perde 1 — başlık canlı yazılır (hızlı)
      tl.to(typed, {
        n: HEADLINE.length,
        duration: 1.1,
        ease: "none",
        onUpdate: () => {
          if (typedRef.current) typedRef.current.textContent = HEADLINE.slice(0, Math.round(typed.n));
        },
      }, 0);
      tl.to(".cc-cursor", { opacity: 0, repeat: 3, yoyo: true, duration: 0.18 }, 0.15);

      // Perde 2 — cümle bir belgeye dönüşür
      tl.to(".cc-headline", { opacity: 0, scale: 0.9, duration: 0.4, ease: "power3.inOut" }, 1.4);
      tl.fromTo(".cc-doc-single", { opacity: 0, scale: 0.85 }, { opacity: 1, scale: 1, duration: 0.5 }, 1.65);
      tl.to(".cc-doc-single", { opacity: 0, scale: 0.9, duration: 0.3 }, 2.45);

      // Perde 3 — belge katmanlarına ayrılır
      tl.fromTo(".cc-doc--title", { opacity: 0, x: 0, y: 0, rotate: 0 },
        { opacity: 1, x: -64, y: -54, rotate: -4, duration: 0.85 }, 2.45);
      tl.fromTo(".cc-doc--abstract", { opacity: 0, scale: 1.06 },
        { opacity: 1, scale: 1, duration: 0.85 }, 2.45);
      tl.fromTo(".cc-doc--content", { opacity: 0, x: 0, y: 0, rotate: 0 },
        { opacity: 1, x: 64, y: 54, rotate: 4, duration: 0.85 }, 2.45);
      tl.fromTo(".cc-doc__chunk", { opacity: 0.12 }, { opacity: 1, stagger: 0.1, duration: 0.2 }, 3.05);
      tl.to(".cc-doc--title, .cc-doc--abstract, .cc-doc--content", { opacity: 0, scale: 0.55, duration: 0.45, ease: "power2.in" }, 4.65);

      // Perde 4 — kütüphaneyle karşılaştırılır
      tl.set(".cc-graph-group", { opacity: 1 }, 5.05);
      tl.fromTo(".cc-graph__line",
        { strokeDashoffset: (_, el) => el.getTotalLength() },
        { strokeDashoffset: 0, stagger: 0.1, duration: 0.45 }, 5.05);
      tl.fromTo(".cc-graph__node", { opacity: 0, scale: 0 }, { opacity: 1, scale: 1, stagger: 0.1, duration: 0.3, transformOrigin: "center" }, 5.05);
      tl.fromTo(".cc-match-chip", { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.35 }, 7.05);
      tl.to(".cc-graph-group", { opacity: 0, duration: 0.35 }, 7.85);

      // Perde 5 — belgeyle konuşulur
      tl.set(".cc-chat-group", { opacity: 1 }, 8.2);
      tl.fromTo(".cc-bubble--user", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.35 }, 8.2);
      tl.fromTo(".cc-bubble--typing", { opacity: 0 }, { opacity: 1, duration: 0.25 }, 8.75);
      tl.to(".cc-bubble--typing", { opacity: 0, duration: 0.2 }, 9.65);
      tl.fromTo(".cc-bubble--reply", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.35 }, 9.65);
      tl.fromTo(".cc-bubble__cite", { opacity: 0 }, { opacity: 1, duration: 0.3 }, 10.3);
      tl.to(".cc-chat-group", { opacity: 0, scale: 0.94, duration: 0.4 }, 11.1);

      // Perde 6 — gerçek ürün arayüzüne kristalleşir
      tl.fromTo(".cc-product", { opacity: 0, scale: 0.93, y: 14 },
        { opacity: 1, scale: 1, y: 0, duration: 0.75, ease: "power3.out" }, 11.4);
      tl.to(".cc-product", { opacity: 0, duration: 0.5 }, 14.6);

      // sıfırla, baştan başla
      tl.set(typed, { n: 0 }, 15.25);
      tl.call(() => { if (typedRef.current) typedRef.current.textContent = ""; }, null, 15.25);
      tl.set(".cc-headline", { opacity: 1, scale: 1 }, 15.25);
      tl.set(".cc-graph__line", { strokeDashoffset: (_, el) => el.getTotalLength() }, 15.25);
      tl.set(".cc-graph__node", { opacity: 0, scale: 0 }, 15.25);
      tl.set(".cc-match-chip", { opacity: 0, y: 8 }, 15.25);
      tl.set(".cc-bubble--user, .cc-bubble--typing, .cc-bubble--reply", { opacity: 0, y: 10 }, 15.25);
      tl.set(".cc-bubble__cite", { opacity: 0 }, 15.25);
    }, rootRef);

    return () => ctx.revert();
  }, [reducedMotion]);

  return (
    <div className={`cc-root${reducedMotion ? " reduced" : ""}`} ref={rootRef}>
      <div className="cc-stage" aria-hidden={reducedMotion ? undefined : "true"}>
        <div className="cc-headline">
          <span ref={typedRef}>{reducedMotion ? HEADLINE : ""}</span>
          {!reducedMotion && <span className="cc-cursor">_</span>}
        </div>

        <div className="cc-doc-single">
          <span className="cc-doc-single__label">Yeni belge</span>
          <div className="cc-doc-single__line cc-doc-single__line--wide" />
          <div className="cc-doc-single__line" />
          <div className="cc-doc-single__line cc-doc-single__line--short" />
        </div>

        <div className="cc-doc-group">
          <div className="cc-layer cc-doc cc-doc--title">
            <span className="cc-doc__label">Başlık</span>
            <div className="cc-doc__line cc-doc__line--wide" />
          </div>
          <div className="cc-layer cc-doc cc-doc--abstract">
            <span className="cc-doc__label">Özet</span>
            <div className="cc-doc__line" />
            <div className="cc-doc__line" />
            <div className="cc-doc__line cc-doc__line--short" />
          </div>
          <div className="cc-layer cc-doc cc-doc--content">
            <span className="cc-doc__label">İçerik</span>
            {[0, 1, 2, 3].map((i) => <div key={i} className="cc-doc__chunk" />)}
          </div>
        </div>

        <div className="cc-graph-group">
          <svg viewBox="0 0 320 220" className="cc-graph">
            {[
              { x: 78, y: 60 }, { x: 235, y: 40 }, { x: 250, y: 165 }, { x: 60, y: 190 }, { x: 165, y: 15 },
            ].map((n, i) => (
              <line key={i} x1="160" y1="110" x2={n.x} y2={n.y} className="cc-graph__line" />
            ))}
            {[
              { x: 78, y: 60, r: 5 }, { x: 235, y: 40, r: 3.8 }, { x: 250, y: 165, r: 4.6, match: true },
              { x: 60, y: 190, r: 3.4 }, { x: 165, y: 15, r: 3.2 },
            ].map((n, i) => (
              <circle key={i} cx={n.x} cy={n.y} r={n.r} className={`cc-graph__node${n.match ? " cc-graph__node--match" : ""}`} />
            ))}
            <circle cx="160" cy="110" r="8" className="cc-graph__node cc-graph__node--self" />
          </svg>
          <div className="cc-match-chip"><span className="cc-match-chip__dot" />%87 benzerlik</div>
        </div>

        <div className="cc-chat-group">
          <div className="cc-bubble cc-bubble--user">Bu makalenin sonuçları neydi?</div>
          <div className="cc-bubble cc-bubble--typing"><span /><span /><span /></div>
          <div className="cc-bubble cc-bubble--reply">
            Model, test setinde %94.2 doğruluk elde etmiş.
            <span className="cc-bubble__cite">kaynak: makale.pdf, s.4</span>
          </div>
        </div>

        <div className="cc-product">
          <div className="cc-product__bar">
            <span /><span /><span />
            <em>AltayAI · PDF Sohbet</em>
          </div>
          <div className="cc-product__body">
            <div className="cc-product__rail">
              <div className="cc-product__doc" /><div className="cc-product__doc" /><div className="cc-product__doc cc-product__doc--active" />
            </div>
            <div className="cc-product__main">
              <div className="cc-product__msg cc-product__msg--user">Bu makalenin sonuçları neydi?</div>
              <div className="cc-product__msg cc-product__msg--reply">
                Model, test setinde %94.2 doğruluk elde etmiş.
                <span>kaynak: makale.pdf, s.4</span>
              </div>
              <div className="cc-product__input">Bir soru sorun…</div>
            </div>
          </div>
        </div>
      </div>

      <p className="cc-sub" style={{ opacity: ctaVisible ? 1 : 0 }}>
        Kütüphanenizdeki belgeleri tarayın, onlarla sohbet edin
        <br />ve yapay zeka destekli önerilerle fikrinizi özgünleştirin.
      </p>
      <div className="cc-actions" style={{ opacity: ctaVisible ? 1 : 0, transform: ctaVisible ? "translateY(0)" : "translateY(8px)" }}>
        <button className="hm-btn hm-btn--primary" onClick={() => navigate("/chat")}>
          <span>Sohbete Başla</span>
          <svg viewBox="0 0 20 20" fill="none"><path d="M4 10h12M10 4l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
        <button className="hm-btn hm-btn--ghost" onClick={() => navigate("/split")}>
          PDF Yükle
        </button>
      </div>
    </div>
  );
}
