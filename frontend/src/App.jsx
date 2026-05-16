import { Routes, Route } from "react-router-dom";
import Home        from "./pages/Home/Home";
import PdfSplitter from "./pages/PdfSplitter/PdfSplitter";
import Similarity  from "./pages/Similarity/Similarity";
import Suggest     from "./pages/Suggest/Suggest";
import Database from "./pages/database/Database";

export default function App() {
  return (
    <Routes>
      <Route path="/"        element={<Home />}        />
      <Route path="/split"   element={<PdfSplitter />} />
      <Route path="/search"  element={<Similarity />}  />
      <Route path="/suggest" element={<Suggest />}     />
      <Route path="database" element={<Database />} />
    </Routes>
  );
}