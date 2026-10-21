import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

/**
 * Google login switches on when AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET are set (see .env.example).
 * Without them MoneyMap runs in local mode: one user, no sign-in, data on this machine.
 */
export const loginEnabled = Boolean(process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET);

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: loginEnabled ? [Google] : [],
  session: { strategy: "jwt" },
  pages: { signIn: "/signin" },
  trustHost: true,
  // Local mode never issues sessions, but Auth.js still needs a secret to boot.
  secret: process.env.AUTH_SECRET ?? (loginEnabled ? undefined : "local-mode-no-sessions"),
});

export type SessionUser = { name: string; email: string; image: string | null } | null;

export async function currentUser(): Promise<SessionUser> {
  if (!loginEnabled) return null;
  const session = await auth();
  const u = session?.user;
  return u?.email ? { name: u.name ?? u.email, email: u.email, image: u.image ?? null } : null;
}
