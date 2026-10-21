import type { Recurring } from "@/lib/api";
import { money, moneyRound, shortDate } from "@/lib/format";

export function RecurringList({ items, monthlyTotal }: { items: Recurring[]; monthlyTotal: number }) {
  const active = items.filter((i) => i.active);
  const stopped = items.filter((i) => !i.active);
  return (
    <section aria-labelledby="rec-h">
      <div className="section-head">
        <h2 id="rec-h">Regular payments</h2>
        <p>
          <span className="rec-total">{moneyRound(monthlyTotal)}</span> a month across {active.length} payments
        </p>
      </div>
      {active.length === 0 ? (
        <p className="quiet">None found yet. A payment needs to appear at least three times at a regular interval.</p>
      ) : (
        <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Payee</th>
              <th>How often</th>
              <th>Next expected</th>
              <th className="right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {active.map((r) => (
              <tr key={r.merchant_key}>
                <td>
                  {r.merchant}
                  <span className="sub">{r.category}</span>
                </td>
                <td>{r.frequency[0].toUpperCase() + r.frequency.slice(1)}</td>
                <td className="num">{shortDate(r.next_expected)}</td>
                <td className="right num">
                  {r.amount_varies ? "about " : ""}
                  {money(r.typical_amount_pence)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
      {stopped.length > 0 && (
        <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          Looks stopped: {stopped.map((s) => `${s.merchant} (last ${shortDate(s.last_date)})`).join(", ")}.
        </p>
      )}
    </section>
  );
}
