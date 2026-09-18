import { useState } from "react";
import { useNavigate } from "react-router-dom";
import UserMenu from "../../UserMenu";
import { useAuth } from "../../useAuth";
import "./Settings.css";

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
    <nav className="set-nav">
      <button className="set-nav__logo" onClick={() => navigate("/")} aria-label="Ana sayfaya git">
        <span className="set-logo-hex">A</span>
        <span className="set-nav__brand">Altay<em>AI</em></span>
      </button>
      <ul className={`set-nav__links${open ? " open" : ""}`}>
        {NAV_LINKS.map(([l, p]) => (
          <li key={p}>
            <button className="set-nav__link" onClick={() => { navigate(p); setOpen(false); }}>{l}</button>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <UserMenu />
        <button className="set-nav__burger" onClick={() => setOpen((v) => !v)}>
          <span /><span /><span />
        </button>
      </div>
    </nav>
  );
}

export default function Settings() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="set-root">
      <Navbar />

      <div className="set-header">
        <div className="set-breadcrumb">
          AltayAI
          <svg viewBox="0 0 10 10" fill="none">
            <path d="M3 2l4 3-4 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <span>Ayarlar</span>
        </div>
        <h1 className="set-header__title">Hesap <em>Ayarları</em></h1>
        <p className="set-header__sub">Hesap bilgilerinizi görüntüleyin</p>
      </div>

      <div className="set-layout">
        <div className="set-card">
          <div className="set-profile">
            <span className="set-avatar">
              {user?.first_name?.[0]?.toUpperCase() || "?"}
            </span>
            <div>
              <div className="set-profile__name">
                {user?.first_name} {user?.last_name}
              </div>
              <span className={`set-role-badge${isAdmin ? " admin" : ""}`}>
                {isAdmin ? "Yönetici" : "Kullanıcı"}
              </span>
            </div>
          </div>

          <div className="set-field">
            <span className="set-field__label">E-posta</span>
            <span className="set-field__value">{user?.email}</span>
          </div>

          <div className="set-divider" />

          <button className="set-logout-btn" onClick={handleLogout}>
            Çıkış Yap
          </button>
        </div>

        <div className="set-hint">
          Profil bilgisi değişikliği (ad, e-posta, şifre) şu anda desteklenmiyor.
          İhtiyacınız varsa yöneticinizle iletişime geçin.
        </div>
      </div>
    </div>
  );
}
