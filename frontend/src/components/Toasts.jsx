export function Toasts({ toasts }) {
  if (toasts.length === 0) return null;
  return (
    <div className="toasts" aria-live="assertive">
      {toasts.map((toast) => (
        <div className="toast" data-tone={toast.tone} key={toast.id} role="status">
          {toast.message}
        </div>
      ))}
    </div>
  );
}
