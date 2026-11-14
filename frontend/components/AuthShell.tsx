import Link from "next/link";

import { Mark } from "./icons";

/** The simple centred layout for account pages: forgot password, reset, confirm email. */
export function AuthShell({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <main className="auth auth-single">
      <section className="auth-panel">
        <div className="auth-panel-inner">
          <Link href="/signin" className="auth-brand" style={{ color: "var(--ink)", textDecoration: "none", marginBottom: 28 }}>
            <Mark />MoneyMap
          </Link>
          <h2 className="auth-title">{title}</h2>
          {sub && <p className="auth-sub">{sub}</p>}
          {children}
        </div>
      </section>
    </main>
  );
}
