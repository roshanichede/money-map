"use client";

import { useEffect, useState } from "react";

import { api, type Account, type Txn } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

type Props = {
  month: string;
  accountId: number | null;
  accounts: Account[];
  category: string | null;
  onCategory: (category: string | null) => void;
  categories: string[];
  refreshKey: number;
  onRecategorised: (message: string) => void;
  /** Compact mode for the overview: no filters, a few rows and a "See all" link. */
  limit?: number;
  onSeeAll?: () => void;
};

const PAGE = 30;

export function Transactions(props: Props) {
  const { month, accountId, accounts, category, onCategory, categories, refreshKey, onRecategorised, limit, onSeeAll } = props;
  const [rows, setRows] = useState<Txn[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);
  const filterKey = `${month}|${accountId}|${category}|${q}`;
  const [page, setPage] = useState({ key: filterKey, shown: PAGE });
  const shown = limit ?? (page.key === filterKey ? page.shown : PAGE);
  const names = new Map(accounts.map((a) => [a.id, a.name]));
  const showAccount = accounts.length > 1 && accountId === null && !limit;

  useEffect(() => {
    const t = setTimeout(() => {
      api.transactions({ month, category: category ?? undefined, q: q.trim() || undefined, accountId })
        .then((r) => { setRows(r); setError(null); })
        .catch((e) => setError(e.message));
    }, 120);
    return () => clearTimeout(t);
  }, [month, accountId, category, q, refreshKey]);

  async function recategorise(t: Txn, next: string) {
    try {
      const r = await api.setCategory(t.id, next, true);
      onRecategorised(
        r.updated > 1
          ? `Moved ${r.updated} ${r.merchant} payments to ${next}. New ones will go there too.`
          : `Moved ${r.merchant} to ${next}. New ${r.merchant} payments will go there too.`,
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="card" id="transactions" aria-labelledby="txn-h">
      <div className="card-head">
        <h2 id="txn-h" className={limit ? undefined : "visually-hidden"}>{limit ? "Latest transactions" : "Transactions"}</h2>
        {!limit && <p>Change a category and every payment to that merchant follows.</p>}
      </div>
      {!limit && (
        <div className="filters">
          <label className="visually-hidden" htmlFor="txn-search">Search transactions</label>
          <input id="txn-search" className="input" placeholder="Search, e.g. Tesco" value={q} onChange={(e) => setQ(e.target.value)} />
          <label className="visually-hidden" htmlFor="txn-cat">Category</label>
          <select id="txn-cat" className="select" value={category ?? ""} onChange={(e) => onCategory(e.target.value || null)}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <span className="muted small">{rows.length} {rows.length === 1 ? "transaction" : "transactions"}</span>
        </div>
      )}
      {error && <div className="error-box">{error}</div>}
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th className="col-date">Date</th>
              <th>Payee</th>
              {showAccount && <th className="col-acct">Account</th>}
              <th className="col-cat">Category</th>
              <th className="right col-amt">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, shown).map((t) => (
              <tr key={t.id}>
                <td className="num quiet nowrap">{shortDate(t.date)}</td>
                <td>
                  {t.merchant} {t.is_transfer && <span className="tag" title="Matched with a payment in another of your accounts">transfer</span>}
                  <span className="sub" title={t.description}>{t.description}</span>
                </td>
                {showAccount && <td className="quiet small acct-cell" title={names.get(t.account_id)}>{names.get(t.account_id)}</td>}
                <td>
                  <label className="visually-hidden" htmlFor={`cat-${t.id}`}>Category for {t.merchant}</label>
                  <select id={`cat-${t.id}`} className={`cat-select${t.category === "Other" ? " other" : ""}`}
                          value={t.category} onChange={(e) => recategorise(t, e.target.value)}>
                    {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
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
      <div className="card-foot">
        <span />
        {limit && onSeeAll && rows.length > limit && <button className="btn-link" onClick={onSeeAll}>See all {rows.length}</button>}
        {!limit && rows.length > shown && (
          <button className="btn" onClick={() => setPage({ key: filterKey, shown: shown + PAGE })}>
            Show {Math.min(PAGE, rows.length - shown)} more
          </button>
        )}
      </div>
    </section>
  );
}
