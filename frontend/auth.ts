import { createHash } from "node:crypto";

import NextAuth, { CredentialsSignin } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

/**
 * Sign-in is on whenever INTERNAL_API_SECRET exists (./start.sh creates it in .env):
 *   - email + password accounts, checked by the backend (passwords are only stored as scrypt hashes)
 *   - "Continue with Google" as well, if AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET are set
 * Without the secrets MoneyMap runs in local mode: one user, no sign-in.
 */
export const loginEnabled = Boolean(process.env.INTERNAL_API_SECRET);

/** The session-signing key: AUTH_SECRET if set, otherwise derived from INTERNAL_API_SECRET for a separate purpose,
 *  so a deployment only needs one secret copied between the website and the API. */
function sessionSecret(): string {
  if (process.env.AUTH_SECRET) return process.env.AUTH_SECRET;
  if (process.env.INTERNAL_API_SECRET) {
    return createHash("sha256").update(`moneymap-session:${process.env.INTERNAL_API_SECRET}`).digest("base64");
  }
  return "local-mode-no-sessions"; // local mode never issues sessions, but Auth.js still needs a secret to boot
}
export const googleEnabled = loginEnabled && Boolean(process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET);

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Server-to-server call to the backend's account endpoints, which only accept the shared secret. */
export async function accountCall(path: "signin" | "signup", body: Record<string, string>) {
  const res = await fetch(`${API_URL}/api/account/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-internal-secret": process.env.INTERNAL_API_SECRET ?? "" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data } as { ok: boolean; status: number; data: { email?: string; name?: string; detail?: string } };
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: loginEnabled
    ? [
        Credentials({
          credentials: { email: {}, password: {} },
          async authorize(c) {
            const r = await accountCall("signin", { email: String(c?.email ?? ""), password: String(c?.password ?? "") });
            if (!r.ok || !r.data.email) throw new CredentialsSignin();
            return { id: r.data.email, email: r.data.email, name: r.data.name ?? r.data.email };
          },
        }),
        ...(googleEnabled ? [Google] : []),
      ]
    : [],
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  trustHost: true,
  secret: sessionSecret(),
});

export type SessionUser = { name: string; email: string; image: string | null } | null;

export async function currentUser(): Promise<SessionUser> {
  if (!loginEnabled) return null;
  const session = await auth();
  const u = session?.user;
  return u?.email ? { name: u.name ?? u.email, email: u.email, image: u.image ?? null } : null;
}
