"use client";

import { useActionState, useState } from "react";

import { signInWithGoogle, signInWithPassword, signUpWithPassword, type FormState } from "@/app/actions";

function GoogleG() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

function SignInForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(signInWithPassword, {});
  return (
    <form action={action} className="auth-form" noValidate>
      <label>Email<input className="input" name="email" type="email" autoComplete="email" required defaultValue={state.email} /></label>
      <label>Password<input className="input" name="password" type="password" autoComplete="current-password" required /></label>
      {state.error && <p className="auth-error" role="alert">{state.error}</p>}
      <button className="btn btn-primary auth-submit" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button>
    </form>
  );
}

function SignUpForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(signUpWithPassword, {});
  return (
    <form action={action} className="auth-form" noValidate>
      <label>Your name<input className="input" name="name" autoComplete="name" defaultValue={state.name} /></label>
      <label>Email<input className="input" name="email" type="email" autoComplete="email" required defaultValue={state.email} /></label>
      <label>
        Password
        <input className="input" name="password" type="password" autoComplete="new-password" minLength={8} required />
        <span className="muted small">At least 8 characters.</span>
      </label>
      {state.error && <p className="auth-error" role="alert">{state.error}</p>}
      <button className="btn btn-primary auth-submit" disabled={pending}>{pending ? "Creating your account…" : "Create account"}</button>
    </form>
  );
}

export function AuthForms({ googleEnabled, startWith, demo = false }: {
  googleEnabled: boolean; startWith: "signin" | "signup"; demo?: boolean;
}) {
  const [mode, setMode] = useState(startWith);
  const signingIn = mode === "signin";
  return (
    <>
      <h2 className="auth-title">{signingIn ? "Welcome back" : "Create your account"}</h2>
      <p className="auth-sub">
        {signingIn ? "Sign in to see where your money went." : "It takes a few seconds. No bank login needed."}
      </p>
      {googleEnabled && (
        <>
          <form action={signInWithGoogle}>
            <button className="btn google-btn" type="submit"><GoogleG />Continue with Google</button>
          </form>
          <div className="auth-or"><span>or with email</span></div>
        </>
      )}
      {signingIn ? <SignInForm key="in" /> : <SignUpForm key="up" />}
      <p className="auth-switch">
        {signingIn ? "New to MoneyMap?" : "Already have an account?"}{" "}
        <button className="btn-link" onClick={() => setMode(signingIn ? "signup" : "signin")}>
          {signingIn ? "Create an account" : "Sign in"}
        </button>
      </p>
      {demo && (
        <p className="auth-demo">
          <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M12 11v5M12 8h.01" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          This is a public demo. Create an account with any email and explore it with sample data.
        </p>
      )}
    </>
  );
}
