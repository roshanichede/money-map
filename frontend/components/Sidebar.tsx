"use client";

import type { SessionUser } from "@/auth";
import { signOutAction } from "@/app/actions";
import { IconBank, IconList, IconOverview, IconRepeat, IconShield, IconSignOut, Mark } from "./icons";

export type View = "overview" | "transactions" | "regular" | "accounts" | "data";

export const VIEWS: { id: View; label: string; Icon: (p: { size?: number }) => React.ReactElement }[] = [
  { id: "overview", label: "Overview", Icon: IconOverview },
  { id: "transactions", label: "Transactions", Icon: IconList },
  { id: "regular", label: "Regular payments", Icon: IconRepeat },
  { id: "accounts", label: "Accounts", Icon: IconBank },
  { id: "data", label: "Your data", Icon: IconShield },
];

type Props = {
  view: View;
  onView: (v: View) => void;
  user: SessionUser;
  loginEnabled: boolean;
  accountCount: number;
};

export function Sidebar({ view, onView, user, loginEnabled, accountCount }: Props) {
  const initial = (user?.name || user?.email || "Y").trim()[0]?.toUpperCase();
  return (
    <aside className="sidebar" aria-label="Main">
      <div className="brand"><Mark /><span>MoneyMap</span></div>
      <nav className="nav">
        {VIEWS.map(({ id, label, Icon }) => (
          <a key={id} href={`#/${id}`} className="nav-item" aria-current={view === id ? "page" : undefined}
             onClick={(e) => { e.preventDefault(); onView(id); }}>
            <Icon />
            {label}
            {id === "accounts" && accountCount > 0 && <span className="nav-count">{accountCount}</span>}
          </a>
        ))}
      </nav>
      <div className="sidebar-foot">
        {loginEnabled && user ? (
          <>
            <span className="avatar">
              {user.image ? (
                // A 30px avatar from Google; next/image would need a remote-host allowlist for no real gain.
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.image} alt="" referrerPolicy="no-referrer" />
              ) : initial}
            </span>
            <span className="who"><b>{user.name}</b><span>{user.email}</span></span>
            <form action={signOutAction}>
              <button className="btn btn-ghost" type="submit" title="Sign out" aria-label="Sign out"><IconSignOut /></button>
            </form>
          </>
        ) : (
          <>
            <span className="avatar">{initial}</span>
            <span className="who"><b>Local mode</b><span>No login. Data stays on this machine.</span></span>
          </>
        )}
      </div>
    </aside>
  );
}
