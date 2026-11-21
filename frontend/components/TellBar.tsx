"use client";

import { useState } from "react";

import { MicButton } from "./Chat";
import { IconChat } from "./icons";

const EXAMPLES = [
  "Abhishek Sharma for garba is entertainment",
  "Payments to Preeti up to £50 are groceries",
  "How much did I spend on eating out?",
];

/** Always-there box on the Overview: type or say anything, and the conversation opens with it. */
export function TellBar({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const send = (t: string) => { const v = t.trim(); if (v) { onSend(v); setText(""); } };
  return (
    <form className="tell-bar" onSubmit={(e) => { e.preventDefault(); send(text); }}>
      <span className="tell-icon" aria-hidden="true"><IconChat /></span>
      <label className="visually-hidden" htmlFor="tell-input">Tell or ask MoneyMap</label>
      <input id="tell-input" className="tell-input" value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
             placeholder={`Tell or ask MoneyMap anything, e.g. “${EXAMPLES[0]}”`} autoComplete="off" />
      <MicButton onText={setText} />
      <button className="btn btn-primary" disabled={!text.trim()}>Send</button>
    </form>
  );
}
