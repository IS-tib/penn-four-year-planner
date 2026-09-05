import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const STORAGE_KEY = "penn-planner.session";

const AuthContext = createContext(null);

function readStoredSession() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    // Private browsing and blocked site data both throw here. Starting signed
    // out is the correct fallback, not a crash.
    return null;
  }
}

function writeStoredSession(session) {
  try {
    if (session) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* the session simply will not survive a reload */
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => readStoredSession());
  const [checking, setChecking] = useState(() => Boolean(readStoredSession()));

  // A stored token can be expired or signed with a key the server has since
  // rotated. Verify it once on load so the app never renders a signed-in shell
  // that then fails every request.
  useEffect(() => {
    let cancelled = false;
    if (!session?.token) {
      setChecking(false);
      return undefined;
    }
    api
      .me(session.token)
      .then((user) => {
        if (!cancelled) setSession((current) => (current ? { ...current, user } : current));
      })
      .catch((error) => {
        if (!cancelled && error.status === 401) {
          setSession(null);
          writeStoredSession(null);
        }
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
    // Runs once on mount; later token changes come from sign in and sign out.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const adopt = useCallback((payload) => {
    const next = { token: payload.access_token, user: payload.user };
    setSession(next);
    writeStoredSession(next);
    return next;
  }, []);

  const signIn = useCallback(
    async (email, password) => adopt(await api.login({ email, password })),
    [adopt],
  );

  const signUp = useCallback(
    async (email, displayName, password) =>
      adopt(await api.register({ email, display_name: displayName, password })),
    [adopt],
  );

  const signOut = useCallback(() => {
    setSession(null);
    writeStoredSession(null);
  }, []);

  const value = useMemo(
    () => ({
      token: session?.token ?? null,
      user: session?.user ?? null,
      checking,
      signIn,
      signUp,
      signOut,
    }),
    [session, checking, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside an AuthProvider");
  return value;
}
