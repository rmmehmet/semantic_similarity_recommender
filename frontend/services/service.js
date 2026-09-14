import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// PDF/embedding/BERT işlemleri uzun sürebilir — sonsuz beklemeyi önlemek için
// makul ama cömert bir timeout (2 dk). Backend takılırsa kullanıcı net bir hata görür.
// withCredentials: true — oturum httpOnly çerezde taşınır (bkz. AuthContext),
// bu olmadan tarayıcı cross-origin (frontend:5173 ↔ backend:8000) isteklerde
// çerezi ne gönderir ne de kaydeder.
const api = axios.create({ baseURL: API_BASE, timeout: 120_000, withCredentials: true });

// Backend'de ADMIN_API_KEY ayarlıysa (bkz. backend/.env.example), yıkıcı/idari
// uçlar (add/remove/reset/reconcile) bu header'ı da kabul eder — asıl admin
// yetkisi artık ADMIN_EMAILS ile kayıt olan gerçek kullanıcı oturumundandır,
// bu header sadece tarayıcı dışı/otomasyon senaryoları için opsiyonel bir yoldur.
const adminApiKey = import.meta.env.VITE_ADMIN_API_KEY;
if (adminApiKey) {
  api.defaults.headers.common["X-API-Key"] = adminApiKey;
}

// ════════════════════════════════════════════
//  PDF Split & Download
// ════════════════════════════════════════════

export const splitPDF = async (file, fontThreshold = 22) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("font_threshold", fontThreshold);
  const res = await api.post("/pdf/split", fd);
  return res.data;
};

export const downloadSectionPDF = async (file, section) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("start_page", section.start_page);
  fd.append("end_page", section.end_page);
  fd.append("title", section.clean_title || section.title || "bolum");
  const res = await fetch(`${API_BASE}/pdf/download-section`, { method: "POST", body: fd, credentials: "include" });
  if (!res.ok) throw new Error("PDF download is failed");
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement("a"), {
    href: url,
    download: `${sanitize(section.clean_title || section.title || "bolum")}.pdf`,
  });
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const downloadSectionsPDF = async (file, sections) => {
  for (const s of sections) { await downloadSectionPDF(file, s); await delay(300); }
};

export const previewSectionPDF = async (file, section) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("start_page", section.start_page);
  fd.append("end_page",   section.end_page);
  const res = await fetch(`${API_BASE}/pdf/preview-section`, { method: "POST", body: fd, credentials: "include" });
  if (!res.ok) throw new Error("PDF preview failed");
  return URL.createObjectURL(await res.blob());
};

// ════════════════════════════════════════════
//  Similarity Comparison
// ════════════════════════════════════════════

export const compareDocuments = async (targetFile, compareFiles, searchType = "fulltext") => {
  const fd = new FormData();
  fd.append("target_file", targetFile);
  compareFiles.forEach(f => fd.append("compare_files", f));
  fd.append("search_type", searchType);
  const res = await api.post("/similarity/compare", fd);
  return res.data;
};

export const compareHighlight = async (targetFile, compareFile, searchType = "fulltext", topWords = 60) => {
  const fd = new FormData();
  fd.append("target_file",  targetFile);
  fd.append("compare_file", compareFile);
  fd.append("search_type",  searchType);
  fd.append("top_words",    topWords);
  const res = await api.post("/similarity/compare-highlight", fd);
  return res.data;
};
// ─────────────────────────────────────────────────────────────────
// frontend/services/service.js
// ─────────────────────────────────────────────────────────────────
// Mevcut servis fonksiyonlarına (splitPdf, searchSimilarity, vb.)
// suggestSearch eklendi.
//
// Endpoint: POST /suggest/search   (multipart/form-data)
//
// Parametreler:
//   searchType : "title" | "abstract" | "fulltext"
//   queryText  : kullanıcının girdiği metin
//   pdfFile    : File nesnesi (fulltext modunda, opsiyonel)
//   topK       : kaç sonuç isteniyor (varsayılan 12)
//
// Döner:
//   {
//     success       : boolean,
//     total         : number,
//     results       : Array<ResultItem>,
//     llm_suggestion: LLMSuggestion,
//     duration_ms   : number,
//     error?        : string
//   }
//
// ResultItem:
//   { score, pdf_name, raw_title, book_name, year, matched_text }
//
// LLMSuggestion (text modu):
//   { mode:"text", success, field, analysis, risk_level,
//     topic_suggestions, revised_title }
//
// LLMSuggestion (rag modu):
//   { mode:"rag", success, field, risk_level,
//     similarity_analysis, original_aspects,
//     improvement_suggestions, topic_suggestions, revised_title }
// ─────────────────────────────────────────────────────────────────


// ── Yardımcı: timeout eklenmiş fetch ────────────────────────────
async function fetchWithTimeout(url, options = {}, timeoutMs = 180_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, credentials: "include", signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timer);
  }
}

// ════════════════════════════════════════════════════════════════
// suggestSearch
// ════════════════════════════════════════════════════════════════

/**
 * Proje Öneri Sistemi ana servis fonksiyonu.
 *
 * @param {Object} params
 * @param {"title"|"abstract"|"fulltext"} params.searchType
 * @param {string}  params.queryText   - Kullanıcının girdiği metin
 * @param {File|null} params.pdfFile   - fulltext modunda yüklenen PDF (opsiyonel)
 * @param {number}  [params.topK=12]   - Kaç sonuç isteniyor
 * @returns {Promise<Object>}          - Backend'den dönen JSON
 */
export async function suggestSearch({
  searchType,
  queryText  = "",
  pdfFile    = null,
  topK       = 12,
}) {
  // multipart/form-data — fetch otomatik boundary ayarlar, Content-Type elle set edilmez
  const body = new FormData();
  body.append("search_type", searchType);
  body.append("query_text",  queryText.trim());
  body.append("top_k",       String(topK));

  // PDF sadece fulltext modunda eklenir
  if (searchType === "fulltext" && pdfFile instanceof File) {
    body.append("file", pdfFile, pdfFile.name);
  }

  let res;
  try {
    res = await fetchWithTimeout(
      `${API_BASE}/suggest/search`,
      { method: "POST", body },
      300_000,   // Llama 3.1 Q4 RAG modu için 5 dakika timeout
    );
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("İstek zaman aşımına uğradı (5 dk). Ollama çalışıyor mu? GPU modu açık mı?");
    }
    throw new Error(`Sunucuya bağlanılamadı: ${err.message}`);
  }

  if (!res.ok) {
    let detail = `Sunucu hatası: ${res.status}`;
    try {
      const errBody = await res.json();
      detail = errBody.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }

  const data = await res.json();

  // Backend başarısız döndüyse normalize et
  if (data.success === false) {
    throw new Error(data.error || "Arama başarısız");
  }

  return data;
}

// ════════════════════════════════════════════════════════════════
// suggestHealth  — opsiyonel, servis kontrolü için
// ════════════════════════════════════════════════════════════════

/**
 * Suggest servisinin model + Ollama sağlığını kontrol eder.
 * @returns {Promise<{status, model_ok, ollama_ok}>}
 */
export async function suggestHealth() {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/suggest/health`, {}, 5_000);
    return await res.json();
  } catch (_) {
    return { status: "unreachable", model_ok: false, ollama_ok: false };
  }
}

// ════════════════════════════════════════════════════════════════
// NOT: Mevcut diğer fonksiyonlar (splitPdf, searchSimilarity, vb.)
// bu dosyanın geri kalanında aynı şekilde kalmalıdır.
// Sadece bu iki export yeni eklenenlerdir.
// ════════════════════════════════════════════════════════════════════════════════════════════

// ════════════════════════════════════════════
//  Database — PDF Yönetimi
// ════════════════════════════════════════════

export async function dbAddPdf(file, { bookName = "", year = 0, forceUpdate = false } = {}) {
  const form = new FormData();
  form.append("file", file);
  form.append("book_name", bookName);
  form.append("year", String(year));
  form.append("force_update", String(forceUpdate));
  const res = await api.post("/db/add", form);
  return res.data;
}

export async function dbRemovePdf(pdfName) {
  const res = await api.delete(`/db/remove/${encodeURIComponent(pdfName)}`);
  return res.data;
}

export async function dbListPdfs(limit = 500) {
  const res = await api.get("/db/list", { params: { limit } });
  return res.data;
}

export async function dbGetDetail(pdfName) {
  const res = await api.get(`/db/detail/${encodeURIComponent(pdfName)}`);
  return res.data;
}

export async function dbStats() {
  const res = await api.get("/db/stats");
  return res.data;
}

export async function dbReset() {
  const res = await api.post("/db/reset");
  return res.data;
}

export function dbPreviewUrl(pdfName) {
  return `${API_BASE}/db/preview/${encodeURIComponent(pdfName)}`;
}

// ════════════════════════════════════════════
//  Yardımcılar
// ════════════════════════════════════════════

const delay    = ms => new Promise(r => setTimeout(r, ms));
const sanitize = n  => n.replace(/[\\/*?:"<>|]/g, "").replace(/\s+/g, "-").slice(0, 80) || "bolum";

// ════════════════════════════════════════════
//  Yükleme doğrulama (backend limitiyle uyumlu)
// ════════════════════════════════════════════

export const MAX_UPLOAD_MB = 30;

export function validatePdfFile(file) {
  if (!file) return "Dosya seçilmedi.";
  if (file.type !== "application/pdf") return "Sadece PDF dosyaları desteklenir.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `Dosya çok büyük (maksimum ${MAX_UPLOAD_MB} MB).`;
  }
  return null;
}

// ════════════════════════════════════════════
//  Auth
// ════════════════════════════════════════════

function _extractErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (!detail) return err?.message || fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI/pydantic doğrulama hatası formatı: [{loc, msg}, ...]
    return detail.map((d) => d.msg || JSON.stringify(d)).join(" ");
  }
  return fallback;
}

export async function registerUser({ email, firstName, lastName, phone, password, passwordConfirm }) {
  try {
    const res = await api.post("/auth/register", {
      email,
      first_name: firstName,
      last_name: lastName,
      phone,
      password,
      password_confirm: passwordConfirm,
    });
    return res.data.user;
  } catch (err) {
    throw new Error(_extractErrorMessage(err, "Kayıt başarısız."));
  }
}

export async function loginUser({ email, password }) {
  try {
    const res = await api.post("/auth/login", { email, password });
    return res.data.user;
  } catch (err) {
    throw new Error(_extractErrorMessage(err, "Giriş başarısız."));
  }
}

export async function logoutUser() {
  try {
    await api.post("/auth/logout");
  } catch (_) {
    // Çıkış her koşulda client tarafında da sonuçlanmalı.
  }
}

export async function fetchCurrentUser() {
  try {
    const res = await api.get("/auth/me");
    return res.data.user;
  } catch (_) {
    return null;
  }
}