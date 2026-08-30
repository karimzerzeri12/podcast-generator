import { Navigate, Route, HashRouter, Routes } from "react-router-dom";
import { getToken } from "./api/client";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import LoginPage from "./pages/LoginPage";
import TopicsPage from "./pages/TopicsPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  return getToken() ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route
          path="/topics"
          element={
            <RequireAuth>
              <TopicsPage />
            </RequireAuth>
          }
        />
        <Route path="/admin" element={<AdminDashboardPage />} />
      </Routes>
    </HashRouter>
  );
}
