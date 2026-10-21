"use client";

import { useState } from "react";

import type { MonthRow } from "@/lib/api";
import { compactPounds, isUnfinished, monthLabel, money, shortDate, signedMoney } from "@/lib/format";

const W = 960;
const H = 230;
const PAD = { top: 16, right: 8, bottom: 40, left: 48 };
const BAR = 16; // <= 24px per the mark spec
const GAP = 2; // surface gap between the two touching bars

/** A top value that splits into 4 round steps (e.g. £3,000 = 4 × £750 is avoided; £4,000 = 4 × £1,000). */
function niceMax(v: number) {
  const raw = v / 100 / 4;
  const mag = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((s) => s >= raw) ?? 10 * mag;
  return step * 4 * 100;
}

/** 4px rounded data-end, square at the baseline. */
function columnPath(x: number, y: number, w: number, h: number) {
  const r = Math.min(4, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

export function MonthsChart({ months, selected, onSelect }: { months: MonthRow[]; selected: string; onSelect: (m: string) => void }) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const max = niceMax(Math.max(...months.flatMap((m) => [m.spend_pence, m.income_pence]), 1));
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const band = plotW / months.length;
  const y = (p: number) => PAD.top + plotH - (p / max) * plotH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const hovered = hover === null ? null : months[hover];

  return (
    <section className="card" aria-labelledby="months-h">
      <div className="card-head">
        <h2 id="months-h">Month by month</h2>
        <div className="legend">
          <span><i style={{ background: "var(--spend)" }} />Spent</span>
          <span><i style={{ background: "var(--income)" }} />Came in</span>
          <button className="btn-link" onClick={() => setAsTable((v) => !v)}>
            {asTable ? "Show chart" : "Show as table"}
          </button>
        </div>
      </div>

      {asTable ? (
        <table className="table">
          <thead>
            <tr><th>Month</th><th className="right">Spent</th><th className="right">Came in</th><th className="right">Left over</th></tr>
          </thead>
          <tbody>
            {months.map((m) => (
              <tr key={m.month}>
                <td>{monthLabel(m.month)}{isUnfinished(m, months) ? ` (to ${shortDate(m.last_date)})` : ""}</td>
                <td className="right num">{money(m.spend_pence)}</td>
                <td className="right num">{money(m.income_pence)}</td>
                <td className="right num">{signedMoney(m.net_pence)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="chart chart-wrap" onMouseLeave={() => setHover(null)}>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Spending and income by month">
            {ticks.map((t) => (
              <g key={t}>
                <line className={t === 0 ? "base" : "grid-line"} x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} />
                <text className="tick" x={PAD.left - 8} y={y(t) + 4} textAnchor="end">{compactPounds(t)}</text>
              </g>
            ))}
            {months.map((m, i) => {
              const cx = PAD.left + band * i + band / 2;
              const partial = isUnfinished(m, months);
              return (
                <g key={m.month}>
                  <rect
                    className={`band${m.month === selected ? " active" : ""}`}
                    x={PAD.left + band * i + 2} y={PAD.top} width={band - 4} height={plotH} rx={6}
                    onMouseEnter={() => setHover(i)}
                    onClick={() => onSelect(m.month)}
                    style={{ cursor: "pointer" }}
                  />
                  {m.spend_pence > 0 && (
                    <path d={columnPath(cx - BAR - GAP / 2, y(m.spend_pence), BAR, y(0) - y(m.spend_pence))}
                          fill="var(--spend)" pointerEvents="none" />
                  )}
                  {m.income_pence > 0 && (
                    <path d={columnPath(cx + GAP / 2, y(m.income_pence), BAR, y(0) - y(m.income_pence))}
                          fill="var(--income)" pointerEvents="none" />
                  )}
                  <text className="xlab" x={cx} y={H - PAD.bottom + 18} textAnchor="middle"
                        fontWeight={m.month === selected ? 650 : 400}>
                    {monthLabel(m.month, "short")}
                  </text>
                  {partial && (
                    <text className="tick" x={cx} y={H - PAD.bottom + 33} textAnchor="middle">to {shortDate(m.last_date)}</text>
                  )}
                </g>
              );
            })}
          </svg>
          {hovered && hover !== null && (
            <div
              className="tooltip"
              style={{
                left: `${((PAD.left + band * hover + band / 2) / W) * 100}%`,
                top: 0,
                transform: hover > months.length / 2 ? "translateX(-105%)" : "translateX(12px)",
              }}
            >
              <b>{monthLabel(hovered.month)}</b>
              <div className="row"><span><i style={{ background: "var(--spend)" }} />Spent</span><span className="num">{money(hovered.spend_pence)}</span></div>
              <div className="row"><span><i style={{ background: "var(--income)" }} />Came in</span><span className="num">{money(hovered.income_pence)}</span></div>
              <div className="row quiet"><span>Left over</span><span className="num">{signedMoney(hovered.net_pence)}</span></div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
