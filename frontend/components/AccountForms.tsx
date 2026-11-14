"use client";

import Link from "next/link";
import { useActionState } from "react";

import { requestReset, resetPassword, type FormState } from "@/app/actions";

export function ForgotForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(requestReset, {});
  if (state.notice) {
    return (
      <>
        <p className="auth-notice" role="status">{state.notice}</p>
        <p className="auth-links"><Link href="/signin" className="btn-link">Back to sign in</Link></p>
      </>
    );
  }
  return (
    <>
      <form action={action} className="auth-form" noValidate>
        <label>Email<input className="input" name="email" type="email" autoComplete="email" required defaultValue={state.email} /></label>
        {state.error && <p className="auth-error" role="alert">{state.error}</p>}
        <button className="btn btn-primary auth-submit" disabled={pending}>{pending ? "Sending…" : "Email me a reset link"}</button>
      </form>
      <p className="auth-links">Remembered it? <Link href="/signin" className="btn-link">Sign in</Link></p>
    </>
  );
}

export function ResetForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(resetPassword, {});
  return (
    <>
      <form action={action} className="auth-form" noValidate>
        <input type="hidden" name="token" value={token} />
        <label>
          New password
          <input className="input" name="password" type="password" autoComplete="new-password" minLength={8} required />
          <span className="muted small">At least 8 characters.</span>
        </label>
        {state.error && <p className="auth-error" role="alert">{state.error}</p>}
        <button className="btn btn-primary auth-submit" disabled={pending}>{pending ? "Saving…" : "Save and sign in"}</button>
      </form>
      {state.error && <p className="auth-links"><Link href="/forgot" className="btn-link">Get a new link</Link></p>}
    </>
  );
}
