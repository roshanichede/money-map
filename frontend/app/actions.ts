"use server";

import { AuthError } from "next-auth";

import { accountCall, signIn, signOut } from "@/auth";

export type FormState = { error?: string; email?: string; name?: string };

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
  if (!check.ok) return { error: check.data.detail ?? "Couldn't sign you in. Try again.", email };
  return finishSignIn(email, password);
}

export async function signUpWithPassword(_: FormState, form: FormData): Promise<FormState> {
  const email = String(form.get("email") ?? "").trim();
  const name = String(form.get("name") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const r = await accountCall("signup", { email, name, password });
  if (!r.ok) return { error: r.data.detail ?? "Couldn't create your account. Try again.", email, name };
  return finishSignIn(email, password);
}
