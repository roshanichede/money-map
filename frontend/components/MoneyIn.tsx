"use client";

import { useState } from "react";

import type { Earnings } from "@/lib/api";
import { KIND_TAG, moneyRound, monthLabel, plural } from "@/lib/format";

type Props = { earnings: Earnings; onSeePayer: (name: string) => void };

/** Who paid you, and how each payment was read: earnings, or someone paying you back. */
export function MoneyIn({ earnings, onSeePayer }: Props) {
  const [explain, setExplain] = useState(false);
  const first = earnings.months[0]?.month;
  const sources = earnings.sources.slice(0, 4);
  return (
    <section className="card" aria-labelledby="in-h">
      <div className="card-head">
        <h2 id="in-h">Money in</h2>
        <p>{first ? `since ${monthLabel(first)}` : ""}</p>
      </div>
      {sources.length === 0 ? (
        <p className="quiet">Nothing has come in yet in these statements.</p>
      ) : (
        <ul className="sources">
          {sources.map((s) => {
            const tag = KIND_TAG[s.kind];
            return (
              <li key={s.name + s.kind}>
                <button className="source-row" onClick={() => onSeePayer(s.name)}
                        title={`${plural(s.count, "payment")} from ${s.name}. Select to see them.`}>
                  <span className="source-name">{s.name}</span>
                  {tag && <span className={`tag tag-${s.kind}`} title={tag.title}>{tag.label}</span>}
                  <span className="source-val num">{moneyRound(s.total_pence)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <div className="card-foot">
        <span className="muted small">
          Money from people is never counted as earnings.
        </span>
        <button className="btn-link small" aria-expanded={explain} onClick={() => setExplain((e) => !e)}>
          {explain ? "Hide" : "How is this decided?"}
        </button>
      </div>
      {explain && (
        <dl className="explain">
          <div>
            <dt><span className="tag tag-salary">salary</span></dt>
            <dd>
              Paid by payroll (BGC on your statement) in two or more months, even when the amount changes with
              your shifts. Or a company paying you a similar amount most months, or a payment marked SALARY or WAGES.
            </dd>
          </div>
          <div>
            <dt><span className="tag tag-income">income</span></dt>
            <dd>Other money from a company or the bank: interest, a one-off payroll payment, a freelance invoice, a tax refund.</dd>
          </div>
          <div>
            <dt><span className="tag tag-paid_back">paid back</span></dt>
            <dd>
              A person whose note says what it&apos;s for, like a flatmate&apos;s RENT share or a friend&apos;s CAB or
              FOOD share. It&apos;s taken off that spending, so your rent shows what you really paid.
            </dd>
          </div>
          <div>
            <dt><span className="tag tag-from_person">from a person</span></dt>
            <dd>A person with no note we understand. Not counted as earnings or as spending.</dd>
          </div>
          <div>
            <dt><span className="tag">transfer</span></dt>
            <dd>Money from another of your own accounts, or marked SELF TRANSFER. Not counted at all.</dd>
          </div>
          <p className="muted small">Wrong? Change the category on the payment. A person who really pays you can be set to Salary or Other income, and future payments follow.</p>
        </dl>
      )}
    </section>
  );
}
