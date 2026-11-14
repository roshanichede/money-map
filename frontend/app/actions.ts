"use server";

import { headers } from "next/headers";
import { AuthError } from "next-auth";

import { accountCall, signIn, signOut } from "@/auth";

export type FormState = { error?: string; email?: string; name?: string; invite?: string; notice?: string; unconfirmed?: boolean };

export async function signInWithGoogle() {
  await signIn("google", { redirectTo: "/" });
}

export async function signOutAction() {
  await signOut({ redirectTo: "/signin" });
}

async function finishSignIn(email: string, password: string): Promise<FormState> {
  try {
    await signIn("credentials", { email, password, redirectTo: "/" });
  } catch (e) {
    if (e instanceof AuthError) return { error: "That email and password don't match.", email };
    throw e; // the redirect to the dashboard
  }
  return {};
}

export async function signInWithPassword(_: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  if (!email || !password) return { error: "Enter your email and password.", email };
  // Ask the backend first so the message can say exactly what went wrong (e.g. too many attempts).
  const check = await accountCall("signin", { email, password });
  if (!check.ok) {
    return { error: check.data.detail ?? "Couldn't sign you in. Try again.", email, unconfirmed: check.status === 403 };
  }
  return finishSignIn(email, password);
}

/** The site's own address, for links in emails (confirm, reset). */
async function origin() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return host ? `${proto}://${host}` : "";
}

export async function signUpWithPassword(_: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const name = String(form.get("name") ?? "").trim();
  const invite = String(form.get("invite") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const r = await accountCall("signup", { email, name, password, invite, origin: await origin() });
  if (!r.ok) return { error: r.data.detail ?? "Couldn't create your account. Try again.", email, name, invite };
  if (r.data.needs_confirming) {
    return { notice: `Almost there: we've sent a link to ${email}. Open it to confirm your email, then sign in.`, email };
  }
  return finishSignIn(email, password);
}

export async function resendConfirmation(_: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  await accountCall("resend", { email, origin: await origin() });
  return { notice: "If that account is waiting for confirmation, a new link is on its way.", email };
}

export async function requestReset(_: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  if (!email) return { error: "Enter your email." };
  const r = await accountCall("forgot", { email, origin: await origin() });
  if (!r.ok) return { error: r.data.detail ?? "Couldn't send the email. Try again.", email };
  return { notice: "If there's an account for that email, a reset link is on its way. It works for 1 hour.", email };
}

export async function resetPassword(_: FormState, form: FormData): Promise<FormState> {
  const token = String(form.get("token") ?? "");
  const password = String(form.get("password") ?? "");
  const r = await accountCall("reset", { token, password });
  if (!r.ok) return { error: r.data.detail ?? "Couldn't reset your password." };
  return finishSignIn(r.data.email!, password);
}
