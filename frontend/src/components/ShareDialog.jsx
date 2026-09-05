import { useState } from "react";

import { Dialog } from "./Dialog.jsx";

export function ShareDialog({ shareToken, busy, onCreate, onRevoke, onClose }) {
  const [copied, setCopied] = useState(false);
  const url = shareToken
    ? `${window.location.origin}/shared/${shareToken}`
    : null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access is blocked in some contexts. Selecting the text is a
      // fine fallback and does not need permission.
      const input = document.getElementById("share-url");
      input?.select();
    }
  }

  return (
    <Dialog
      title="Share this plan"
      subtitle="Anyone with the link can read the plan. Nobody can change it."
      onClose={onClose}
    >
      {url ? (
        <div className="share-body">
          <div className="share-url">
            <input id="share-url" type="text" readOnly value={url} onFocus={(e) => e.target.select()} />
            <button type="button" className="btn btn-primary" onClick={copy}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="detail-empty">
            The link carries no account access. It shows the plan, its checks and its progress,
            and nothing else about you.
          </p>
          <button type="button" className="btn" onClick={onRevoke} disabled={busy}>
            Turn the link off
          </button>
          <p className="detail-empty">
            Turning it off breaks the existing link immediately. Sharing again makes a new one.
          </p>
        </div>
      ) : (
        <div className="share-body">
          <p className="detail-empty">
            This plan is private. Creating a link lets you send it to an advisor without
            them needing an account.
          </p>
          <button type="button" className="btn btn-primary" onClick={onCreate} disabled={busy}>
            Create a read-only link
          </button>
        </div>
      )}
    </Dialog>
  );
}
