"use client";

import { useEffect, useState } from "react";

import { api, type Txn } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

type Props = {
  month: string;
  category: string | null;
  onClearCategory: () => void;
  categories: string[];
  refreshKey: number;
  onRecategorised: (message: string) => void;
};

const PAGE = 25;

export function Transactions({ month, category, onClearCategory, categories, refreshKey, onRecategorised }: Props) {
  const [rows, setRows] = useState<Txn[]>([]);
  const [q, setQ] = useState("");
  // How many rows are visible; resets to one page whenever the filters change.
  const filterKey = `${month}|${category}|${q}`;
  const [page, setPage] = useState({ key: filterKey, shown: PAGE });
  const shown = page.key === filterKey ? page.shown : PAGE;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      api.transactions({ month, category: category ?? undefined, q: q.trim() || undefined })
        .then((r) => { setRows(r); setError(null); })
        .catch((e) => setError(e.message));
    }, 150);
    return () => clearTimeout(t);
  }, [month, category, q, refreshKey]);

  async function recategorise(t: Txn, next: string) {
    try {
      const r = await api.setCategory(t.id, next, true);
      onRecategorised(
        r.updated > 1
          ? `Moved ${r.updated} ${r.merchant} payments to ${next}. New ${r.merchant} payments will go there too.`
          : `Moved ${r.merchant} to ${next}. New ${r.merchant} payments will go there too.`,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section id="transactions" aria-labelledby="txn-h">
      <div className="section-head">
        <h2 id="txn-h">Transactions</h2>
        <p>Wrong category? Change it and every payment to that merchant follows.</p>
      </div>
      <div className="filters">
        <label className="visually-hidden" htmlFor="txn-search">Search transactions</label>
        <input id="txn-search" className="input" placeholder="Search, e.g. Tesco" value={q} onChange={(e) => setQ(e.target.value)} />
        {category && (
          <span className="chip">
            {category}
            <button aria-label={`Remove ${category} filter`} onClick={onClearCategory}>×</button>
          </span>
        )}
      </div>
      {error && <div className="error-box">{error}</div>}
      <div className="table-scroll">
      <table className="table txn-table">
        <thead>
          <tr>
            <th className="col-date">Date</th>
            <th>Payee</th>
            <th className="col-cat">Category</th>
            <th className="right col-amt">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, shown).map((t) => (
            <tr key={t.id}>
              <td className="num quiet">{shortDate(t.date)}</td>
              <td>
                {t.merchant}
                <span className="sub" title={t.description}>{t.description}</span>
              </td>
              <td>
                <label className="visually-hidden" htmlFor={`cat-${t.id}`}>Category for {t.merchant}</label>
                <select
                  id={`cat-${t.id}`}
                  className={`cat-select${t.category === "Other" ? " other" : ""}`}
                  value={t.category}
                  onChange={(e) => recategorise(t, e.target.value)}
                >
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                {t.category_source !== "rule" && <span className="learned">yours</span>}
              </td>
              <td className={`right num${t.amount_pence > 0 ? " amount-in" : ""}`}>
                {t.amount_pence > 0 ? "+" : ""}{money(t.amount_pence)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {rows.length === 0 && !error && <p className="quiet">No transactions match.</p>}
      {rows.length > shown && (
        <button className="btn show-more" onClick={() => setPage({ key: filterKey, shown: shown + PAGE })}>
          Show {Math.min(PAGE, rows.length - shown)} more{rows.length - shown > PAGE ? ` of ${rows.length - shown}` : ""}
        </button>
      )}
    </section>
  );
}
