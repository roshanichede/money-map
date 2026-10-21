"use client";

import type { Highlight } from "@/lib/api";

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

/** The few things worth knowing about the month, each one plain sentence. */
export function Highlights({ items, onCategory }: Props) {
  return (
    <section className="card" aria-labelledby="hl-h">
      <div className="card-head">
        <h2 id="hl-h">What stands out</h2>
      </div>
      {items.length === 0 ? (
        <p className="quiet">Nothing unusual this month.</p>
      ) : (
        <ul className="highlights">
          {items.map((h, i) => (
            <li key={i} className={`hl hl-${h.kind}`}>
              <span className="hl-mark" aria-hidden="true">{MARK[h.kind]}</span>
              <span>
                {h.text}{" "}
                {h.category && (
                  <button className="btn-link small" onClick={() => onCategory(h.category!)}>
                    {h.kind === "unsorted" ? "Sort them" : "See payments"}
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
