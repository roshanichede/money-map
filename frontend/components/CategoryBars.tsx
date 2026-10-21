"use client";

import type { Summary } from "@/lib/api";
import { categoryLabel, changeWords, money, moneyRound, plural } from "@/lib/format";

type Props = { summary: Summary; onSelect: (category: string) => void };

export function CategoryBars({ summary, onSelect }: Props) {
  const rows = summary.categories;
  const max = Math.max(...rows.map((r) => r.spend_pence), 1);
  const prev = new Map(summary.comparison?.changes.map((c) => [c.category, c]) ?? []);
  const hasPrev = Boolean(summary.comparison);

  return (
    <section className="card" aria-labelledby="where-h">
      <div className="card-head">
        <h2 id="where-h">Where it went</h2>
        <p>{hasPrev ? "compared with last month" : "Select one to see its payments"}</p>
      </div>
      {rows.length === 0 ? (
        <p className="quiet">No spending this month.</p>
      ) : (
        <ul className="cat-list">
          {rows.map((r) => {
            const change = prev.get(r.category);
            const delta = change ? change.delta_pence : hasPrev ? r.spend_pence : 0;
            const prevPence = change ? change.prev_pence : 0;
            return (
              <li key={r.category}>
                <button
                  className="cat-row"
                  onClick={() => onSelect(r.category)}
                  title={`${categoryLabel(r.category)}: ${money(r.spend_pence)} across ${plural(r.count, "payment")}${hasPrev ? `; ${money(prevPence)} last month` : ""}. Select to see them.`}
                >
                  <span className={`cat-name${r.category === "Other" ? " unsorted" : ""}`}>{categoryLabel(r.category)}</span>
                  <span className="cat-track"><span className="cat-bar" style={{ width: `${(r.spend_pence / max) * 100}%` }} /></span>
                  <span className="cat-val num">{moneyRound(r.spend_pence)}</span>
                  <span className={`cat-delta num${delta > 0 ? " up" : ""}`}>
                    {hasPrev ? changeWords(delta, prevPence) : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
