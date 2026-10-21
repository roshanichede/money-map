"use client";

import type { Highlight } from "@/lib/api";
import { currencySymbol } from "@/lib/format";

const MARK: Record<Highlight["kind"], string> = {
  top: "●",
  up: "▲",
  down: "▼",
  unsorted: "?",
  paid_back: "↩",
  from_people: "→",
  salary: "£",
};

type Props = { items: Highlight[]; onCategory: (category: string) => void };

/** The few things worth knowing about the month: at most three, one short line each. */
export function Highlights({ items, onCategory }: Props) {
  const shown = items.filter((h) => h.kind !== "top").slice(0, 3);
  return (
    <section className="card" aria-labelledby="hl-h">
      <div className="card-head">
        <h2 id="hl-h">Worth knowing</h2>
      </div>
      {shown.length === 0 ? (
        <p className="quiet">Nothing unusual this month.</p>
      ) : (
        <ul className="highlights">
          {shown.map((h, i) => {
            const body = (
              <>
                <span className="hl-mark" aria-hidden="true">{h.kind === "salary" ? currencySymbol() : MARK[h.kind]}</span>
                <span>{h.text}</span>
              </>
            );
            return (
              <li key={i} className={`hl hl-${h.kind}`}>
                {h.category ? <button className="hl-btn" onClick={() => onCategory(h.category!)}>{body}</button> : <div className="hl-btn">{body}</div>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
