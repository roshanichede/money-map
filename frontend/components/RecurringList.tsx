import type { Recurring } from "@/lib/api";
import { money, moneyRound, shortDate } from "@/lib/format";

type Props = { items: Recurring[]; monthlyTotal: number; limit?: number; onSeeAll?: () => void };

export function RecurringList({ items, monthlyTotal, limit, onSeeAll }: Props) {
  const active = items.filter((i) => i.active).sort((a, b) => a.next_expected.localeCompare(b.next_expected));
  const stopped = items.filter((i) => !i.active);
  const shown = limit ? active.slice(0, limit) : active;
  return (
    <section className="card" aria-labelledby="rec-h">
      <div className="card-head">
        <h2 id="rec-h">{limit ? "Coming up" : "Regular payments"}</h2>
        <p><span className="num">{moneyRound(monthlyTotal)}</span> a month across {active.length} payments</p>
      </div>
      {active.length === 0 ? (
        <p className="quiet">None found yet. A payment needs to appear at least three times at a regular interval.</p>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Payee</th>
                {!limit && <th>How often</th>}
                <th>Next</th>
                <th className="right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.merchant_key}>
                  <td>{r.merchant}<span className="sub">{r.category}</span></td>
                  {!limit && <td>{r.frequency[0].toUpperCase() + r.frequency.slice(1)}</td>}
                  <td className="num">{shortDate(r.next_expected)}</td>
                  <td className="right num">{r.amount_varies ? "about " : ""}{money(r.typical_amount_pence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {limit && active.length > limit && onSeeAll && (
        <div className="card-foot"><span /><button className="btn-link" onClick={onSeeAll}>See all {active.length}</button></div>
      )}
      {!limit && stopped.length > 0 && (
        <p className="muted small" style={{ marginTop: 12 }}>
          Looks stopped: {stopped.map((s) => `${s.merchant} (last ${shortDate(s.last_date)})`).join(", ")}.
        </p>
      )}
    </section>
  );
}
