"use client";

import { useEffect, useRef, useState } from "react";

import { api, type Account, type AccountType, type UploadResult, type UploadTarget } from "@/lib/api";
import { plural } from "@/lib/format";
import { Check, Dash, IconClose, IconUpload, Warn } from "./icons";

const TYPES: { value: AccountType; label: string }[] = [
  { value: "current", label: "Current account" },
  { value: "savings", label: "Savings" },
  { value: "credit_card", label: "Credit card" },
  { value: "other", label: "Other" },
];

export function UploadResults({ results }: { results: UploadResult[] }) {
  return (
    <ul className="results">
      {results.map((r, i) => (
        <li key={i}>
          {!r.ok ? <Warn /> : r.reconciled === "ok" ? <Check /> : r.reconciled === "mismatch" ? <Warn /> : <Dash />}
          <span>
            <b>{r.filename}</b>
            {r.ok && r.account ? <> → {r.account}</> : null}:{" "}
            {r.ok ? (
              <>
                {plural(r.rows_added ?? 0, "new transaction")}
                {r.duplicates_skipped ? `, ${r.duplicates_skipped} already imported` : ""}
                {r.transfers_matched ? `, ${plural(r.transfers_matched, "transfer")} matched between your accounts` : ""}.{" "}
                <span className="muted">{r.reconciliation_note}</span>
              </>
            ) : (
              r.error
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

function DropZone({ onFiles, busy }: { onFiles: (f: File[]) => void; busy: boolean }) {
  const [over, setOver] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div
      className={`drop${over ? " over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles(Array.from(e.dataTransfer.files)); }}
    >
      <IconUpload size={22} />
      <strong>Drop CSV exports or PDF statements</strong>
      <span className="quiet small">Lloyds, Halifax and Bank of Scotland are read natively. Most other UK banks&apos; CSVs work too.</span>
      <input ref={ref} type="file" accept=".csv,.pdf,text/csv,application/pdf" multiple hidden
             onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
      <button type="button" className="btn" disabled={busy} onClick={() => ref.current?.click()}>
        {busy ? "Reading…" : "Choose files"}
      </button>
    </div>
  );
}

export function DemoNotice() {
  return (
    <p className="demo-notice" role="note">
      <b>This is a public demo.</b> Try it with the sample data. Please don&apos;t upload real bank statements here:
      to use MoneyMap with your own money, run it on your computer (see the README on GitHub).
    </p>
  );
}

export function UploadDialog({ open, onClose, accounts, onImported, demo = false }: {
  open: boolean; onClose: () => void; accounts: Account[]; onImported: () => void; demo?: boolean;
}) {
  const [choice, setChoice] = useState("detect");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<AccountType>("current");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function send(files: File[]) {
    if (!files.length) return;
    let target: UploadTarget = { kind: "detect" };
    if (choice === "new") {
      if (!newName.trim()) { setError("Give the new account a name first."); return; }
      target = { kind: "new", name: newName.trim(), type: newType };
    } else if (choice !== "detect") {
      target = { kind: "existing", accountId: Number(choice) };
    }
    setBusy(true);
    setError(null);
    try {
      const r = await api.upload(files, target);
      setResults(r.results);
      onImported();
      if (choice === "new") { setChoice("detect"); setNewName(""); }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="up-h">
        <div className="dialog-head">
          <h2 id="up-h">Add statements</h2>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close"><IconClose /></button>
        </div>
        {demo && <DemoNotice />}
        <DropZone onFiles={send} busy={busy} />
        <div className="field">
          <label htmlFor="up-account">Which account are these from?</label>
          <select id="up-account" className="select" value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="detect">Work it out from the file</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            <option value="new">A new account…</option>
          </select>
          {choice === "detect" && (
            <span className="muted small">
              Uses the account number in the file, or matches it to payments you&apos;ve already imported. Otherwise it becomes a new account you can rename.
            </span>
          )}
        </div>
        {choice === "new" && (
          <div className="field field-row">
            <input className="input" placeholder="Name, e.g. Monzo" value={newName} onChange={(e) => setNewName(e.target.value)} aria-label="New account name" />
            <select className="select" value={newType} onChange={(e) => setNewType(e.target.value as AccountType)} aria-label="Account type">
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
        )}
        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
        {results && <UploadResults results={results} />}
        <div className="dialog-foot">
          <button className="btn" onClick={onClose}>{results ? "Done" : "Cancel"}</button>
        </div>
      </div>
    </>
  );
}

export function Welcome({ onImported, demo = false }: { onImported: () => void; demo?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run(job: () => Promise<{ results: UploadResult[] }>) {
    setBusy(true);
    setError(null);
    try { setResults((await job()).results); onImported(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return (
    <div className="welcome">
      <h2>See where your money went, without linking your bank.</h2>
      <p className="lede">
        Upload the statements you already have. MoneyMap sorts every payment, finds your regular bills, keeps
        money moved between your own accounts out of your spending, and answers questions in plain English.
      </p>
      <div className="card">
        {demo && <DemoNotice />}
        {demo ? (
          <div style={{ display: "flex", justifyContent: "center", padding: "12px 0" }}>
            <button className="btn btn-primary" onClick={() => run(() => api.demo())} disabled={busy}>
              {busy ? "Loading sample data…" : "Try it with sample data"}
            </button>
          </div>
        ) : (
          <>
            <DropZone onFiles={(f) => f.length && run(() => api.upload(f))} busy={busy} />
            <div style={{ display: "flex", justifyContent: "center", marginTop: 12 }}>
              <button className="btn-link" onClick={() => run(() => api.demo())} disabled={busy}>
                Or try it with sample data (current account, savings and a credit card)
              </button>
            </div>
          </>
        )}
        {results && <UploadResults results={results} />}
        {error && <div className="error-box" style={{ marginTop: 12 }}>{error}</div>}
      </div>
      <div className="how">
        <div><b>Getting a Lloyds CSV</b>On a computer, open the account, choose Statement options, then Export transactions. Each export holds up to 150 rows.</div>
        <div><b>Several accounts</b>Upload each one. Transfers and card repayments between them are matched so nothing counts twice.</div>
        <div><b>Your files aren&apos;t kept</b>Statements are read, then thrown away. Only the transactions are saved, and you can delete them any time.</div>
      </div>
    </div>
  );
}
