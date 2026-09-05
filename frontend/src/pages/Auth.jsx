import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth.jsx";
import { useTheme } from "../theme.js";

export function AuthPage({ mode }) {
  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useTheme();

  const registering = mode === "signup";

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (registering) await signUp(email, displayName, password);
      else await signIn(email, password);
      navigate("/plans");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <section className="hero" style={{ display: "grid", alignContent: "center" }}>
        <div className="hero-inner">
          <span className="eyebrow" style={{ color: "#9db2dc" }}>
            Course Map
          </span>
          <h1 style={{ fontSize: "clamp(1.8rem, 3.4vw, 2.7rem)" }}>
            Four years, laid out, and checked against the real rules.
          </h1>
          <p>
            Ten Penn degrees, real prerequisites from the catalog, and a plan that
            tells you the moment the order stops working.
          </p>
        </div>
      </section>

      <div className="auth-wrap">
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={!registering}
              onClick={() => navigate("/signin")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={registering}
              onClick={() => navigate("/signup")}
            >
              Create account
            </button>
          </div>

          <h2>{registering ? "Start a plan" : "Welcome back"}</h2>

          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}

          {registering ? (
            <div className="field">
              <label htmlFor="displayName">Name</label>
              <input
                id="displayName"
                type="text"
                autoComplete="name"
                required
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </div>
          ) : null}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete={registering ? "new-password" : "current-password"}
              required
              minLength={registering ? 8 : 1}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>

          <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>
            {busy ? "Working..." : registering ? "Create account" : "Sign in"}
          </button>

          <p className="small muted">
            {registering
              ? "At least 8 characters. Passwords are hashed with bcrypt and never stored as text."
              : "Your plans are private to your account."}
          </p>
          <p className="small muted">
            <Link to="/">Back to the front page</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
