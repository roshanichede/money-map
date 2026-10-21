"use client";

import { useEffect, useState } from "react";

import { api, type ImportRow } from "@/lib/api";
import { plural } from "@/lib/format";
import { Check, Dash, Warn } from "./icons";

export function YourData({ refreshKey, categorisedRate, onDeleted }: {
  refreshKey: number; categorisedRate: number; onDeleted: () => void;
}) {
  const [imports, setImports] = useState<ImportRow[]>([]);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => { api.imports().then(setImports).catch(() => setImports([])); }, [refreshKey]);

  async function remove() {
    await api.deleteAll();
    setConfirming(false);
    onDeleted();
  }

  return (
    <section aria-labelledby="data-h">
      <div className="section-head">
        <h2 id="data-h">Your data</h2>
        <p>{Math.round(categorisedRate * 100)}% of transactions sorted automatically</p>
      </div>
      <ul className="data-list">
        {imports.map((u) => (
          <li key={u.id}>
            {u.reconciled === "ok" ? <Check /> : u.reconciled === "mismatch" ? <Warn /> : <Dash />}
            <span>
              <b>{u.filename}</b>{" "}
              <span className="quiet">
                {plural(u.rows_added, "transaction")} added
                {u.duplicates_skipped ? `, ${u.duplicates_skipped} duplicates skipped` : ""}.
              </span>
              <span className="sub muted" style={{ display: "block", fontSize: 13 }}>{u.reconciliation_note}</span>
            </span>
          </li>
        ))}
      </ul>
      <div className="data-actions">
        <a className="btn" href="/api/export" download>Export all as CSV</a>
        {confirming ? (
          <>
            <span className="quiet">Delete every transaction and category rule?</span>
            <button className="btn btn-danger" onClick={remove}>Yes, delete everything</button>
            <button className="btn-link" onClick={() => setConfirming(false)}>Cancel</button>
          </>
        ) : (
          <button className="btn btn-danger" onClick={() => setConfirming(true)}>Delete all data</button>
        )}
      </div>
    </section>
  );
}
