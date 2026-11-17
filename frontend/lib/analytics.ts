/**
 * Product analytics (PostHog, EU cloud), set up for a money app:
 *  - no cookies or local storage for tracking (an anonymous id lives in memory for the visit)
 *  - no autocapture, heatmaps or session recordings: the screen shows amounts and payee names, so only the
 *    named events below are sent, with no money data in them
 *  - addresses are sent without their query string or #, so invite codes and reset tokens never leave
 *  - signed-in people are identified by a one-way hash of their email, never the email itself
 *  - anyone can switch it off in Your data
 * Requests go through /ingest on our own domain (see next.config.ts), so no third-party script is loaded.
 */
import posthog from "posthog-js";

const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY ?? "phc_y3Gwb6e9Vup3QoMZVW8agGFJYfaMgCs4CUg8hebVN2Sy"; // public by design
const OPT_OUT = "mm-no-analytics";
let started = false;

export type AnalyticsEvent =
  | "view_opened" | "statements_uploaded" | "upload_failed" | "sample_data_loaded" | "live_link_created"
  | "feedback_sent" | "account_deleted" | "data_deleted" | "category_changed" | "chat_asked" | "csv_exported";

function optedOut() {
  try { return localStorage.getItem(OPT_OUT) === "1"; } catch { return false; }
}

const strip = (url: unknown) => {
  if (typeof url !== "string" || !url) return url;
  try { const u = new URL(url, window.location.origin); return u.origin + u.pathname; } catch { return undefined; }
};

export function initAnalytics() {
  if (started || !KEY || typeof window === "undefined" || window.location.hostname === "localhost") return;
  started = true;
  posthog.init(KEY, {
    api_host: "/ingest",
    ui_host: "https://eu.posthog.com",
    defaults: "2025-05-24",
    persistence: "memory",
    person_profiles: "identified_only",
    autocapture: false,
    capture_dead_clicks: false,
    capture_heatmaps: false,
    disable_session_recording: true,
    disable_surveys: true,
    enable_recording_console_log: false,
    capture_performance: false,
    mask_all_text: true,
    mask_all_element_attributes: true,
    opt_out_capturing_by_default: optedOut(),
    before_send: (event) => {
      if (!event) return null;
      const p = event.properties ?? {};
      for (const k of ["$current_url", "$referrer", "$initial_referrer", "$initial_current_url"]) {
        if (k in p) p[k] = strip(p[k]);
      }
      delete p.$pathname_search; // never send query strings
      if (event.$set) delete event.$set.$current_url;
      return event;
    },
  });
}

export function track(event: AnalyticsEvent, props?: Record<string, string | number | boolean>) {
  if (started) posthog.capture(event, props);
}

export async function identify(email: string) {
  if (!started || !email || !crypto?.subtle) return;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email.trim().toLowerCase()));
  const id = Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
  posthog.identify(id);
}

export function resetAnalytics() {
  if (started) posthog.reset();
}

export function analyticsOn() {
  return !optedOut();
}

export function setAnalytics(on: boolean) {
  try { if (on) localStorage.removeItem(OPT_OUT); else localStorage.setItem(OPT_OUT, "1"); } catch { /* private mode */ }
  if (!started) return;
  if (on) posthog.opt_in_capturing(); else posthog.opt_out_capturing();
}
