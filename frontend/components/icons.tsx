type P = { size?: number };

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export const Check = ({ size = 15 }: P) => (
  <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
    <circle cx="8" cy="8" r="7.25" fill="none" stroke="var(--good)" strokeWidth="1.5" />
    <path d="M4.8 8.2l2.1 2.1 4.3-4.6" fill="none" stroke="var(--good)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Warn = ({ size = 15 }: P) => (
  <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
    <path d="M8 1.6l6.6 12H1.4z" fill="none" stroke="var(--bad)" strokeWidth="1.5" strokeLinejoin="round" />
    <path d="M8 6.2v3.4M8 11.6v.2" stroke="var(--bad)" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

export const Dash = ({ size = 15 }: P) => (
  <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
    <circle cx="8" cy="8" r="7.25" fill="none" stroke="var(--muted)" strokeWidth="1.5" />
    <path d="M5 8h6" stroke="var(--muted)" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

export const Info = ({ size = 15 }: P) => (
  <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
    <circle cx="8" cy="8" r="7.25" fill="none" stroke="var(--accent)" strokeWidth="1.5" />
    <path d="M8 7.2v4M8 4.8v.2" stroke="var(--accent)" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

/** The brand mark: a folded map whose middle panel is a rising/falling line. */
export const Mark = () => (
  <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M2 5l6.5-2.5 7 2.5L22 2.5v16.5L15.5 21.5l-7-2.5L2 21.5z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    <path d="M8.5 2.5v16.5M15.5 5v16.5" stroke="currentColor" strokeWidth="1.2" opacity="0.45" />
    <path d="M4 15l4.5-4 4 2.5 6.5-6" fill="none" stroke="var(--spend)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const IconOverview = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <rect x="2.5" y="2.5" width="6.5" height="8" rx="1.5" /><rect x="11" y="2.5" width="6.5" height="5" rx="1.5" />
    <rect x="2.5" y="12.5" width="6.5" height="5" rx="1.5" /><rect x="11" y="9.5" width="6.5" height="8" rx="1.5" />
  </svg>
);
export const IconList = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M7 5h10M7 10h10M7 15h10" /><circle cx="3.5" cy="5" r=".8" /><circle cx="3.5" cy="10" r=".8" /><circle cx="3.5" cy="15" r=".8" />
  </svg>
);
export const IconRepeat = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M3 9V8a3 3 0 013-3h10l-3-3M17 11v1a3 3 0 01-3 3H4l3 3" />
  </svg>
);
export const IconBank = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M2.5 7.5L10 3l7.5 4.5M4 8.5v6M8 8.5v6M12 8.5v6M16 8.5v6M2.5 17h15" />
  </svg>
);
export const IconCard = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <rect x="2.5" y="4.5" width="15" height="11" rx="2" /><path d="M2.5 8h15M5.5 12.5h3" />
  </svg>
);
export const IconPiggy = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M4 9.5a5.5 4.5 0 0110.6-1.6H16l1.5 1v3l-1.6.6A5.5 5 0 0113 15v2h-2v-1.3H8.4V17h-2v-2.2A4.6 4.6 0 014 11z" /><path d="M8 5.5a2 2 0 013.5-1.2" />
  </svg>
);
export const IconShield = ({ size = 17 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M10 2.5l6 2.2v4.6c0 3.9-2.6 6.9-6 8.2-3.4-1.3-6-4.3-6-8.2V4.7z" /><path d="M7.4 10l1.8 1.8 3.5-3.6" />
  </svg>
);
export const IconChat = ({ size = 16 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M3.5 5.5a2 2 0 012-2h9a2 2 0 012 2v6.5a2 2 0 01-2 2H9l-3.5 3v-3h0a2 2 0 01-2-2z" />
  </svg>
);
export const IconUpload = ({ size = 16 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M10 13V3.5M6 7.5l4-4 4 4M3.5 13.5v1.5a2 2 0 002 2h9a2 2 0 002-2v-1.5" />
  </svg>
);
export const IconClose = ({ size = 16 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M5 5l10 10M15 5L5 15" />
  </svg>
);
export const IconSignOut = ({ size = 16 }: P) => (
  <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" {...stroke}>
    <path d="M8 3.5H5.5a2 2 0 00-2 2v9a2 2 0 002 2H8M12.5 6.5L16 10l-3.5 3.5M16 10H7.5" />
  </svg>
);

export function AccountIcon({ type, size = 18 }: { type: string; size?: number }) {
  if (type === "credit_card") return <IconCard size={size} />;
  if (type === "savings") return <IconPiggy size={size} />;
  return <IconBank size={size} />;
}
