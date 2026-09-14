import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../useAuth";
import "./Auth.css";

function validateClientSide({ firstName, lastName, email, phone, password, passwordConfirm }) {
  if (firstName.trim().length < 2) return "Ad en az 2 karakter olmalı.";
  if (lastName.trim().length < 2) return "Soyad en az 2 karakter olmalı.";
  if (!/^\S+@\S+\.\S+$/.test(email)) return "Geçerli bir e-posta adresi girin.";
  // Basit format kontrolü — kesin doğrulama (phonenumbers) backend'de yapılır.
  if (!/^[+\d][\d\s()-]{6,}$/.test(phone.trim())) return "Geçerli bir telefon numarası girin.";
  if (password.length < 8) return "Şifre en az 8 karakter olmalı.";
  if (!/[0-9]/.test(password) || !/[a-zA-Z]/.test(password)) {
    return "Şifre en az 1 harf ve 1 rakam içermeli.";
  }
  if (password !== passwordConfirm) return "Şifreler eşleşmiyor.";
  return null;
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    password: "",
    passwordConfirm: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const clientError = validateClientSide(form);
    if (clientError) {
      setError(clientError);
      return;
    }

    setLoading(true);
    try {
      await register(form);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-root">
      <div className="auth-card">
        <Link to="/" className="auth-logo">
          <span className="auth-logo-mark">A</span>
          <span className="auth-logo-text">Altay<em>AI</em></span>
        </Link>

        <h1 className="auth-title">Hesap Oluştur</h1>
        <p className="auth-sub">AltayAI'yi kullanmak için kayıt ol</p>

        {error && <div className="auth-error" style={{ marginBottom: 16 }}>{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-row">
            <div className="auth-field">
              <label htmlFor="firstName">Ad</label>
              <input
                id="firstName"
                type="text"
                autoComplete="given-name"
                placeholder="Ad"
                value={form.firstName}
                onChange={set("firstName")}
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="lastName">Soyad</label>
              <input
                id="lastName"
                type="text"
                autoComplete="family-name"
                placeholder="Soyad"
                value={form.lastName}
                onChange={set("lastName")}
                required
              />
            </div>
          </div>

          <div className="auth-field">
            <label htmlFor="email">E-posta</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="ornek@eposta.com"
              value={form.email}
              onChange={set("email")}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="phone">Telefon</label>
            <input
              id="phone"
              type="tel"
              autoComplete="tel"
              placeholder="+90 5xx xxx xx xx"
              value={form.phone}
              onChange={set("phone")}
              required
            />
            <span className="auth-field-hint">Ülke kodu belirtmezsen Türkiye (+90) varsayılır.</span>
          </div>

          <div className="auth-row">
            <div className="auth-field">
              <label htmlFor="password">Şifre</label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                placeholder="En az 8 karakter"
                value={form.password}
                onChange={set("password")}
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="passwordConfirm">Şifre (tekrar)</label>
              <input
                id="passwordConfirm"
                type="password"
                autoComplete="new-password"
                placeholder="Şifreyi tekrar gir"
                value={form.passwordConfirm}
                onChange={set("passwordConfirm")}
                required
              />
            </div>
          </div>
          <span className="auth-field-hint">Şifre en az 1 harf ve 1 rakam içermeli.</span>

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading && <span className="auth-spinner" />}
            {loading ? "Kayıt olunuyor…" : "Kayıt Ol"}
          </button>
        </form>

        <p className="auth-footer">
          Zaten hesabın var mı? <Link to="/login">Giriş Yap</Link>
        </p>
      </div>
    </div>
  );
}
