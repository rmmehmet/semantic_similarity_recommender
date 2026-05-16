import axios from "axios";

const API_BASE = "http://localhost:8000";

const api = axios.create({ baseURL: API_BASE });

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
  const res = await fetch(`${API_BASE}/pdf/download-section`, { method: "POST", body: fd });
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
  const res = await fetch(`${API_BASE}/pdf/preview-section`, { method: "POST", body: fd });
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

// ════════════════════════════════════════════
//  Project Recommendation
// ════════════════════════════════════════════

export const suggestSearch = async ({ searchType, queryText, pdfFile, topK = 12 }) => {
  const fd = new FormData();
  fd.append("search_type", searchType);
  fd.append("query_text",  queryText);
  fd.append("top_k",       topK);
  if (pdfFile) fd.append("pdf_file", pdfFile);
  const res = await api.post("/suggest/search", fd);
  return res.data;
};

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