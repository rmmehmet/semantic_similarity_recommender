import axios from "axios";

const API = axios.create({ baseURL: "http://localhost:8000" });

// ════════════════════════════════════════════
//  PDF Split & Download
// ════════════════════════════════════════════
export const splitPDF = async (file, fontThreshold = 22) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("font_threshold", fontThreshold);
  const res = await API.post("/pdf/split", fd);
  return res.data;
};

export const downloadSectionPDF = async (file, section) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("start_page", section.start_page);
  fd.append("end_page", section.end_page);
  fd.append("title", section.clean_title || section.title || "bolum");
  const res  = await fetch("http://localhost:8000/pdf/download-section", { method: "POST", body: fd });
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
  const res  = await fetch("http://localhost:8000/pdf/preview-section", { method: "POST", body: fd });
  if (!res.ok) throw new Error("PDF preview failed");
  return URL.createObjectURL(await res.blob());
};

// ════════════════════════════════════════════
//  Similarity Comparison
// ════════════════════════════════════════════

/**
 * Hedef PDF'yi karşılaştırma PDF'leriyle karşılaştır.
 * İleride Milvus entegrasyonu için compare_files parametresi opsiyonel olacak.
 */
export const compareDocuments = async (targetFile, compareFiles, searchType = "fulltext") => {
  const fd = new FormData();
  fd.append("target_file", targetFile);
  compareFiles.forEach(f => fd.append("compare_files", f));
  fd.append("search_type", searchType);
  const res = await API.post("/similarity/compare", fd);
  return res.data;
};

/**
 * Compare the target PDF to a single comparison PDF and highlight similar sections.
 * İleride Milvus entegrasyonu için compare_file parametresi opsiyonel olacak.
 */
export const compareHighlight = async (targetFile, compareFile, searchType = "fulltext", topWords = 60) => {
  const fd = new FormData();
  fd.append("target_file",  targetFile);
  fd.append("compare_file", compareFile);
  fd.append("search_type",  searchType);
  fd.append("top_words",    topWords);
  const res = await API.post("/similarity/compare-highlight", fd);
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
  const res = await API.post("/suggest/search", fd);
  return res.data;
};

// ════════════════════════════════════════════
//  YARDIMCILAR
// ════════════════════════════════════════════
const delay = ms => new Promise(r => setTimeout(r, ms));
const sanitize = n => n.replace(/[\\/*?:"<>|]/g, "").replace(/\s+/g, "-").slice(0, 80) || "bolum";