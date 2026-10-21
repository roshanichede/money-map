"use client";

import { useRef, useState } from "react";

import { api, type UploadResult } from "@/lib/api";
import { plural } from "@/lib/format";
import { Check, Dash, Warn } from "./icons";

export function useUpload(onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(job: () => Promise<{ results: UploadResult[] }>) {
    setBusy(true);
    setError(null);
    try {
      const r = await job();
      setResults(r.results);
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return {
    busy, results, error,
    upload: (files: File[]) => files.length && run(() => api.upload(files)),
    demo: () => run(() => api.demo()),
    clear: () => setResults(null),
  };
}

export function UploadResults({ results }: { results: UploadResult[] }) {
  return (
    <ul className="results">
      {results.map((r, i) => (
        <li key={i}>
          {!r.ok ? <Warn /> : r.reconciled === "ok" ? <Check /> : r.reconciled === "mismatch" ? <Warn /> : <Dash />}
          <span>
            <b>{r.filename}</b>:{" "}
            {r.ok ? (
              <>
                {plural(r.rows_added ?? 0, "new transaction")}
                {r.duplicates_skipped ? `, ${r.duplicates_skipped} already imported` : ""}. {r.reconciliation_note}
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

/** Hidden file input + button that opens it. */
export function PickFiles({ onFiles, children, className = "btn", disabled }: {
  onFiles: (f: File[]) => void; children: React.ReactNode; className?: string; disabled?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={ref} type="file" accept=".csv,.pdf,text/csv,application/pdf" multiple hidden
             onChange={(e) => { onFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
      <button type="button" className={className} disabled={disabled} onClick={() => ref.current?.click()}>{children}</button>
    </>
  );
}

export function EmptyState({ onDone }: { onDone: () => void }) {
  const up = useUpload(onDone);
  const [over, setOver] = useState(false);
  return (
    <div className="empty">
      <h1>See where your money went, without linking your bank.</h1>
      <p className="lede">
        Upload the statements you already have. MoneyMap sorts every payment, finds your regular bills and
        answers questions about your spending in plain English.
      </p>
      <div
        className={`drop${over ? " over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); up.upload(Array.from(e.dataTransfer.files)); }}
      >
        <strong>Drop CSV exports or PDF statements here</strong>
        <span className="quiet">Lloyds, Halifax and Bank of Scotland are read natively; most other UK banks&apos; CSVs work too.</span>
        <div className="drop-actions">
          <PickFiles onFiles={up.upload} className="btn btn-primary" disabled={up.busy}>
            {up.busy ? "Reading…" : "Choose files"}
          </PickFiles>
          <button className="btn" onClick={up.demo} disabled={up.busy}>Try it with sample data</button>
        </div>
        {up.results && <UploadResults results={up.results} />}
        {up.error && <div className="error-box">{up.error}</div>}
      </div>
      <div className="how">
        <div><b>Getting a Lloyds CSV</b>On a computer, open the account, choose Statement options, then Export transactions. Each export holds up to 150 rows.</div>
        <div><b>Overlaps are fine</b>Upload as many exports as you like. Payments that appear twice are only counted once.</div>
        <div><b>Your data stays yours</b>Everything is stored on this machine. Export or delete it all at any time.</div>
      </div>
    </div>
  );
}
