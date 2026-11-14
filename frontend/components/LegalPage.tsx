import Link from "next/link";

import { Mark } from "./icons";

export function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <main className="legal">
      <Link href="/" className="auth-brand"><Mark />MoneyMap</Link>
      <h1>{title}</h1>
      <p className="legal-date">Last updated {updated}</p>
      {children}
      <p style={{ marginTop: 40 }}><Link href="/privacy">Privacy</Link> · <Link href="/terms">Terms</Link> · <Link href="/">Back to MoneyMap</Link></p>
    </main>
  );
}

/** How to reach the person running MoneyMap. CONTACT_EMAIL is optional; without it, the in-app feedback button. */
export function Contact() {
  const email = process.env.CONTACT_EMAIL;
  return email
    ? <>email <a href={`mailto:${email}`}>{email}</a>, or use <b>Send feedback</b> in the app</>
    : <>use <b>Send feedback</b> in the app (tick “you can reply to me” so we can answer)</>;
}
