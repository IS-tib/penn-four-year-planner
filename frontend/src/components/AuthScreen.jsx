import { useState } from "react";
import { useAuth } from "../auth.jsx";

export function AuthScreen() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const registering = mode === "signup";

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (registering) await signUp(email, displayName, password);
      else await signIn(email, password);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }

  function switchTo(next) {
    setMode(next);
    setError(null);
  }

  return (
    <div className="auth">
      <section className="auth-pitch">
        <h1>
          Four years of Penn CS,
          <br />
          laid out on one page.
        </h1>
        <p>
          Drag courses into semesters and see straight away whether the order actually works.
        </p>
        <ul className="auth-points">
          <li>Real CIS, MATH and PHYS prerequisites from the Penn catalog</li>
          <li>Prerequisite order and course load checked as you build</li>
          <li>Progress toward every requirement bucket in the BSE</li>
          <li>One press lays out a complete, valid four year schedule</li>
        </ul>
      </section>

      <div className="auth-form-wrap">
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={!registering}
              onClick={() => switchTo("signin")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={registering}
              onClick={() => switchTo("signup")}
            >
              Create account
            </button>
          </div>

          <h2>{registering ? "Start a plan" : "Welcome back"}</h2>

          {error ? (
            <p className="auth-error" role="alert">
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

          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Working..." : registering ? "Create account" : "Sign in"}
          </button>

          <p className="auth-note">
            {registering
              ? "At least 8 characters. Passwords are hashed with bcrypt and never stored as text."
              : "Your plans are private to your account."}
          </p>
        </form>
      </div>
    </div>
  );
}
