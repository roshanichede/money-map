"use client";

import type { Summary } from "@/lib/api";
import { money, moneyRound, plural, signedRound } from "@/lib/format";

type Props = {
  summary: Summary;
  selected: string | null;
  onSelect: (category: string | null) => void;
};

export function CategoryBars({ summary, selected, onSelect }: Props) {
  const rows = summary.categories;
  const max = Math.max(...rows.map((r) => r.spend_pence), 1);
  const prev = new Map(summary.comparison?.changes.map((c) => [c.category, c]) ?? []);
  const hasPrev = Boolean(summary.comparison);

  return (
    <section aria-labelledby="where-h">
      <div className="section-head">
        <h2 id="where-h">Where it went</h2>
        <p>Select a category to see its transactions.</p>
      </div>
      <div className="cat-head" aria-hidden="true">
        <span>Category</span>
        <span />
        <span>Spent</span>
        <span>{hasPrev ? "vs last month" : ""}</span>
      </div>
      <ul className="cat-list">
        {rows.map((r) => {
          const change = prev.get(r.category);
          const delta = change ? change.delta_pence : hasPrev ? r.spend_pence : 0;
          const prevPence = change ? change.prev_pence : 0;
          const isSelected = selected === r.category;
          return (
            <li key={r.category}>
              <button
                className="cat-row"
                aria-pressed={isSelected}
                onClick={() => onSelect(isSelected ? null : r.category)}
                title={`${r.category}: ${money(r.spend_pence)} across ${plural(r.count, "payment")}${
                  hasPrev ? `; ${money(prevPence)} last month` : ""
                }`}
              >
                <span className="cat-name">{r.category}</span>
                <span className="cat-track">
                  <span className="cat-bar" style={{ display: "block", width: `${(r.spend_pence / max) * 100}%` }} />
                </span>
                <span className="cat-val num">{moneyRound(r.spend_pence)}</span>
                <span className={`cat-delta num${delta > 0 ? " up" : ""}`}>
                  {hasPrev ? (delta === 0 ? "same" : signedRound(delta)) : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {rows.length === 0 && <p className="quiet">No spending recorded this month.</p>}
    </section>
  );
}
