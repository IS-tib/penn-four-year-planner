import { useEffect, useRef } from "react";

/**
 * A modal shell.
 *
 * Three things make a dialog usable that are easy to leave out: escape closes
 * it, focus moves into it when it opens and returns to where it came from when
 * it closes, and a click on the backdrop does not count as a click inside.
 */
export function Dialog({ title, subtitle, onClose, children, footer, wide = false }) {
  const panelRef = useRef(null);
  const returnFocusTo = useRef(null);

  useEffect(() => {
    returnFocusTo.current = document.activeElement;
    panelRef.current?.focus();

    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (returnFocusTo.current instanceof HTMLElement) returnFocusTo.current.focus();
    };
  }, [onClose]);

  return (
    <div
      className="backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="dialog"
        data-wide={wide}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={panelRef}
      >
        <header className="dialog-head">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          <button type="button" className="btn btn-quiet" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </header>
        <div className="dialog-body">{children}</div>
        {footer ? <footer className="dialog-foot">{footer}</footer> : null}
      </div>
    </div>
  );
}
