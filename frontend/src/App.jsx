import { Routes, Route } from "react-router-dom";
import Home        from "./pages/Home/Home";
import PdfSplitter from "./pages/PdfSplitter/PdfSplitter";
import Chat        from "./pages/Chat/Chat";
import Suggest     from "./pages/Suggest/Suggest";
import Database from "./pages/Database/Database";
import Login    from "./pages/Auth/Login";
import Register from "./pages/Auth/Register";
import ProtectedRoute from "./ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login"    element={<Login />}    />
      <Route path="/register" element={<Register />} />

      <Route path="/"         element={<ProtectedRoute><Home /></ProtectedRoute>}        />
      <Route path="/split"    element={<ProtectedRoute><PdfSplitter /></ProtectedRoute>} />
      <Route path="/chat"     element={<ProtectedRoute><Chat /></ProtectedRoute>}        />
      <Route path="/suggest"  element={<ProtectedRoute><Suggest /></ProtectedRoute>}     />
      <Route path="/database" element={<ProtectedRoute><Database /></ProtectedRoute>}    />
    </Routes>
  );
}
