type P = { size?: number };

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

/** The brand mark: a folded map whose middle panel is a rising/falling line. */
export const Mark = () => (
  <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M2 5l6.5-2.5 7 2.5L22 2.5v16.5L15.5 21.5l-7-2.5L2 21.5z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    <path d="M8.5 2.5v16.5M15.5 5v16.5" stroke="currentColor" strokeWidth="1.2" opacity="0.45" />
    <path d="M4 15l4.5-4 4 2.5 6.5-6" fill="none" stroke="var(--spend)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
