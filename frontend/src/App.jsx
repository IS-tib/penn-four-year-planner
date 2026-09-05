import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "./auth.jsx";
import { useTheme } from "./theme.js";
import { Audit } from "./pages/Audit.jsx";
import { AuthPage } from "./pages/Auth.jsx";
import { Compare } from "./pages/Compare.jsx";
import { Dashboard, NewPlan } from "./pages/Dashboard.jsx";
import { Landing } from "./pages/Landing.jsx";
import { Planner } from "./pages/Planner.jsx";
import { ProgramDetail, Programs } from "./pages/Programs.jsx";
import { Shared } from "./pages/Shared.jsx";

/** Sends anyone without a session to sign in, remembering where they wanted. */
function RequireAuth({ children }) {
  const { user, checking } = useAuth();
  const location = useLocation();

  if (checking) {
    return (
      <div className="busy">
        <div>
          <div className="spinner" />
          Checking your session
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/signin" replace state={{ from: location }} />;
  return children;
}

function Redirected({ to, children }) {
  const { user, checking } = useAuth();
  if (checking) return null;
  if (user) return <Navigate to={to} replace />;
  return children;
}

export default function App() {
  useTheme();

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/signin"
          element={
            <Redirected to="/plans">
              <AuthPage mode="signin" />
            </Redirected>
          }
        />
        <Route
          path="/signup"
          element={
            <Redirected to="/plans">
              <AuthPage mode="signup" />
            </Redirected>
          }
        />

        <Route path="/programs" element={<Programs />} />
        <Route path="/programs/:code" element={<ProgramDetail />} />
        <Route path="/shared/:token" element={<Shared />} />

        <Route
          path="/plans"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/plans/new"
          element={
            <RequireAuth>
              <NewPlan />
            </RequireAuth>
          }
        />
        <Route
          path="/plans/:planId"
          element={
            <RequireAuth>
              <Planner />
            </RequireAuth>
          }
        />
        <Route
          path="/plans/:planId/audit"
          element={
            <RequireAuth>
              <Audit />
            </RequireAuth>
          }
        />
        <Route
          path="/plans/:planId/compare"
          element={
            <RequireAuth>
              <Compare />
            </RequireAuth>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
