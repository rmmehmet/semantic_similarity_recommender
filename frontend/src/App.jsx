import { Routes, Route } from "react-router-dom";
import Home        from "./pages/Home/Home";
import PdfSplitter from "./pages/PdfSplitter/PdfSplitter";
import Similarity  from "./pages/Similarity/Similarity";

export default function App() {
  return (
    <Routes>
      <Route path="/"        element={<Home />}        />
      <Route path="/split"   element={<PdfSplitter />} />
      <Route path="/search"  element={<Similarity />}  />
      <Route path="/suggest" element={<div style={{color:"#fff",padding:"120px 48px"}}>Proje Öneri — yakında</div>} />
    </Routes>
  );
}