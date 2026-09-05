import { useEffect, useRef, useState } from "react";

const reduceMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Mark a section as revealed the first time it scrolls into view.
 *
 * The alternative, animating everything on load, means the sections below the
 * fold have finished animating before anyone sees them, which is the same as
 * having no animation at all except slower.
 *
 * Once revealed it stays revealed. Re-animating on the way back up is the kind
 * of effect that is charming once and irritating every time after.
 */
export function useReveal(options = {}) {
  const ref = useRef(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (reduceMotion() || typeof IntersectionObserver === "undefined") {
      setShown(true);
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: options.rootMargin ?? "0px 0px -12% 0px", threshold: 0.08 },
    );
    observer.observe(node);

    // A safety net, because the failure mode of this pattern is a section that
    // stays invisible forever. Anything that captures a long page without
    // scrolling it, print to PDF and full-page screenshot tools among them,
    // never fires the observer. Ten seconds is long enough that a reader who
    // scrolls still sees the animation, and short enough that nothing is
    // permanently hidden from a reader who does not.
    const failsafe = window.setTimeout(() => setShown(true), 10000);

    return () => {
      observer.disconnect();
      window.clearTimeout(failsafe);
    };
  }, [options.rootMargin]);

  return [ref, shown];
}

/**
 * Count a number up once, when it first matters.
 *
 * Eased rather than linear, because a linear counter reads as a machine
 * finishing a task and an eased one reads as a number settling.
 */
export function useCountUp(target, active, duration = 900) {
  const [value, setValue] = useState(active ? target : 0);

  useEffect(() => {
    if (!active) return undefined;
    if (reduceMotion()) {
      setValue(target);
      return undefined;
    }
    let frame = 0;
    const started = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active, duration]);

  return value;
}
