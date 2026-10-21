"use client";

import type { Summary } from "@/lib/api";
import { categoryLabel, money, moneyRound, plural } from "@/lib/format";
import { CategoryIcon } from "./CategoryIcon";

type Props = { summary: Summary; onSelect: (category: string) => void; partial: boolean };

function Change({ delta, prev, partial }: { delta: number; prev: number; partial: boolean }) {
  const pounds = Math.round(delta / 100);
  if (prev === 0) return <span className="pill pill-new">new</span>;
  if (pounds === 0) return <span className="pill">same</span>;
  if (partial && delta < 0) return <span className="pill" title="This month isn't finished yet">so far</span>;
  const up = delta > 0;
  return (
    <span className={`pill ${up ? "pill-up" : "pill-down"}`} title={`${moneyRound(Math.abs(delta))} ${up ? "more" : "less"} than last month`}>
      <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true"><path d={up ? "M5 1 9 7H1Z" : "M5 9 1 3h8Z"} fill="currentColor" /></svg>
      {moneyRound(Math.abs(delta))}
    </span>
  );
}

export function CategoryBars({ summary, onSelect, partial }: Props) {
  const rows = summary.categories;
  const max = Math.max(...rows.map((r) => r.spend_pence), 1);
  const prev = new Map(summary.comparison?.changes.map((c) => [c.category, c]) ?? []);
  const hasPrev = Boolean(summary.comparison);

  return (
    <section className="card" aria-labelledby="where-h">
      <div className="card-head">
        <h2 id="where-h">Where it went</h2>
        {hasPrev && <p>vs last month</p>}
      </div>
      {rows.length === 0 ? (
        <p className="quiet">No spending this month.</p>
      ) : (
        <ul className="cat-list">
          {rows.map((r) => {
            const change = prev.get(r.category);
            return (
              <li key={r.category}>
                <button className="cat-row" onClick={() => onSelect(r.category)}
                        title={`${categoryLabel(r.category)}: ${money(r.spend_pence)} across ${plural(r.count, "payment")}. Select to see them.`}>
                  <CategoryIcon category={r.category} />
                  <span className="cat-main">
                    <span className="cat-line">
                      <span className={`cat-name${r.category === "Other" ? " unsorted" : ""}`}>{categoryLabel(r.category)}</span>
                      <span className="cat-val num">{moneyRound(r.spend_pence)}</span>
                    </span>
                    <span className="cat-track"><span className="cat-bar" style={{ width: `${(r.spend_pence / max) * 100}%` }} /></span>
                  </span>
                  <span className="cat-delta">
                    {hasPrev && <Change delta={change ? change.delta_pence : r.spend_pence} prev={change ? change.prev_pence : 0} partial={partial} />}
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
