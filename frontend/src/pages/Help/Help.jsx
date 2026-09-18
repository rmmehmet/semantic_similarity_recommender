import { useState } from "react";
import { useNavigate } from "react-router-dom";
import UserMenu from "../../UserMenu";
import "./Help.css";

const NAV_LINKS = [
  ["PDF Bölme", "/split"],
  ["PDF Sohbet", "/chat"],
  ["Proje Öneri", "/suggest"],
  ["Kütüphanem", "/database"],
];

function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  return (
    <nav className="hlp-nav">
      <button className="hlp-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
        <span className="hlp-logo-hex">A</span>
        <span className="hlp-nav__brand">Altay<em>AI</em></span>
      </button>
      <ul className={`hlp-nav__links${open ? " open" : ""}`}>
        {NAV_LINKS.map(([l, p]) => (
          <li key={p}>
            <button className="hlp-nav__link" onClick={() => { navigate(p); setOpen(false); }}>{l}</button>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <UserMenu />
        <button className="hlp-nav__burger" onClick={() => setOpen((v) => !v)}>
          <span /><span /><span />
        </button>
      </div>
    </nav>
  );
}

const FAQ = [
  {
    q: "Kütüphanem ne işe yarar?",
    a: "Yüklediğiniz tüm PDF'lerin listelendiği, önizlenebildiği ve içeriğinin (başlık, özet, tam metin) görüntülenebildiği kişisel belge kütüphanenizdir. Yüklediğiniz her belge otomatik olarak işlenir ve diğer özelliklerde (Proje Öneri, PDF Sohbet) kullanılabilir hale gelir.",
  },
  {
    q: "Proje Öneri ne yapar?",
    a: "Bir başlık, özet ya da PDF verdiğinizde, kütüphanenizdeki benzer çalışmaları bulur ve projenizin ne kadar özgün olduğuna dair bir analiz sunar. Yüksek benzerlik tespit edilirse, alternatif ve daha özgün konu önerileri de üretir.",
  },
  {
    q: "PDF Sohbet nasıl çalışır?",
    a: "Kütüphanenizdeki bir veya birden fazla belgeyi (ya da tüm kütüphanenizi) seçip, o belgeler hakkında doğal dilde sorular sorabilirsiniz. Yanıtlar yalnızca seçtiğiniz belgelerin içeriğine dayanır ve hangi belgeden/bölümden alındığı kaynak olarak gösterilir.",
  },
  {
    q: "PDF Bölme ne için kullanılır?",
    a: "Birden fazla makale/bildiri içeren tek bir PDF dosyasını (örn. bir konferans kitapçığı), font boyutu eşiğine göre ayrı ayrı belgelere böler. Bölme sonrası her bir bölümü ayrı ayrı indirebilir ya da önizleyebilirsiniz.",
  },
  {
    q: "Yüklediğim bir belgeyi nasıl silerim?",
    a: "Kütüphanem sayfasında, \"PDF Listesi\" sekmesinde ilgili belgenin yanındaki silme (çöp kutusu) simgesine tıklayın. Silme işlemi geri alınamaz.",
  },
  {
    q: "Aynı belgeyi tekrar yüklersem ne olur?",
    a: "Sistem içerik bazında tekilleştirme yapar — aynı içerik zaten yüklüyse işlem atlanır. Farklı bir isimle ama aynı içerikle tekrar yüklerseniz bu durum size bildirilir. Var olan bir belgeyi güncellemek isterseniz \"Zaten mevcut PDF'leri güncelle\" seçeneğini işaretleyerek tekrar yükleyebilirsiniz.",
  },
];

export default function Help() {
  const [openIdx, setOpenIdx] = useState(0);

  return (
    <div className="hlp-root">
      <Navbar />

      <div className="hlp-header">
        <div className="hlp-breadcrumb">
          AltayAI
          <svg viewBox="0 0 10 10" fill="none">
            <path d="M3 2l4 3-4 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <span>Yardım</span>
        </div>
        <h1 className="hlp-header__title">Yardım <em>&amp; SSS</em></h1>
        <p className="hlp-header__sub">Özellikler hakkında sık sorulan sorular</p>
      </div>

      <div className="hlp-layout">
        {FAQ.map((item, i) => (
          <div key={i} className={`hlp-item${openIdx === i ? " open" : ""}`}>
            <button className="hlp-item__q" onClick={() => setOpenIdx(openIdx === i ? -1 : i)}>
              <span>{item.q}</span>
              <svg viewBox="0 0 16 16" fill="none" className="hlp-item__chevron">
                <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {openIdx === i && <p className="hlp-item__a">{item.a}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
