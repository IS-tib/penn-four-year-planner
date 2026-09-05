import { useCallback, useEffect, useState } from "react";

const KEY = "penn-planner.theme";

function read() {
  try {
    return window.localStorage.getItem(KEY) ?? "light";
  } catch {
    // Private browsing and blocked site data both throw here. Defaulting is
    // the correct fallback, not a crash.
    return "light";
  }
}

/** Theme, persisted per browser and applied to the root element. */
export function useTheme() {
  const [theme, setTheme] = useState(read);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(KEY, theme);
    } catch {
      /* the choice simply will not survive a reload */
    }
  }, [theme]);

  return [theme, useCallback((next) => setTheme(next), [])];
}
