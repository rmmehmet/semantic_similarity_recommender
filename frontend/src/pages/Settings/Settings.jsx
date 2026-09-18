import { useState } from "react";
import { useNavigate } from "react-router-dom";
import UserMenu from "../../UserMenu";
import { useAuth } from "../../useAuth";
import { updateProfile, changePassword } from "../../../services/service";
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

function ProfileForm({ user, onSaved }) {
  const [firstName, setFirstName] = useState(user?.first_name || "");
  const [lastName, setLastName]   = useState(user?.last_name || "");
  const [email, setEmail]         = useState(user?.email || "");
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState(null);
  const [saved, setSaved]         = useState(false);

  const dirty =
    firstName.trim() !== (user?.first_name || "") ||
    lastName.trim() !== (user?.last_name || "") ||
    email.trim() !== (user?.email || "");

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateProfile({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim(),
      });
      onSaved(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <form className="set-card" onSubmit={submit}>
      <div className="set-card__title">Profil Bilgileri</div>

      <div className="set-form-row">
        <div className="set-field">
          <label className="set-field__label">Ad</label>
          <input className="set-input" value={firstName} onChange={(e) => setFirstName(e.target.value)} required minLength={2} />
        </div>
        <div className="set-field">
          <label className="set-field__label">Soyad</label>
          <input className="set-input" value={lastName} onChange={(e) => setLastName(e.target.value)} required minLength={2} />
        </div>
      </div>

      <div className="set-field">
        <label className="set-field__label">E-posta</label>
        <input className="set-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>

      {error && <div className="set-msg set-msg--error">{error}</div>}
      {saved && <div className="set-msg set-msg--ok">✓ Profil güncellendi</div>}

      <button className="set-save-btn" type="submit" disabled={!dirty || saving}>
        {saving ? "Kaydediliyor…" : "Değişiklikleri Kaydet"}
      </button>
    </form>
  );
}

function PasswordForm() {
  const [current, setCurrent]   = useState("");
  const [next, setNext]         = useState("");
  const [confirm, setConfirm]   = useState("");
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState(null);
  const [saved, setSaved]       = useState(false);

  const canSubmit = current && next.length >= 8 && next === confirm;

  const submit = async (e) => {
    e.preventDefault();
    if (next !== confirm) {
      setError("Yeni şifreler eşleşmiyor.");
      return;
    }
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await changePassword({
        currentPassword: current,
        newPassword: next,
        newPasswordConfirm: confirm,
      });
      setCurrent("");
      setNext("");
      setConfirm("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <form className="set-card" onSubmit={submit}>
      <div className="set-card__title">Şifre Değiştir</div>

      <div className="set-field">
        <label className="set-field__label">Mevcut Şifre</label>
        <input className="set-input" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
      </div>
      <div className="set-form-row">
        <div className="set-field">
          <label className="set-field__label">Yeni Şifre</label>
          <input className="set-input" type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} />
        </div>
        <div className="set-field">
          <label className="set-field__label">Yeni Şifre (Tekrar)</label>
          <input className="set-input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
        </div>
      </div>
      <p className="set-field__hint">En az 8 karakter, en az 1 harf ve 1 rakam içermeli.</p>

      {error && <div className="set-msg set-msg--error">{error}</div>}
      {saved && <div className="set-msg set-msg--ok">✓ Şifre değiştirildi</div>}

      <button className="set-save-btn" type="submit" disabled={!canSubmit || saving}>
        {saving ? "Kaydediliyor…" : "Şifreyi Değiştir"}
      </button>
    </form>
  );
}

export default function Settings() {
  const { user, isAdmin, logout, setCurrentUser } = useAuth();
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
        <p className="set-header__sub">Profil bilgilerinizi ve şifrenizi yönetin</p>
      </div>

      <div className="set-layout">
        <div className="set-profile-summary">
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

        <ProfileForm user={user} onSaved={setCurrentUser} />
        <PasswordForm />

        <button className="set-logout-btn" onClick={handleLogout}>
          Çıkış Yap
        </button>
      </div>
    </div>
  );
}
