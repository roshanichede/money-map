/** A small line icon per category, so lists can be scanned without reading. 24×24, 1.75 stroke. */
const PATHS: Record<string, string> = {
  Groceries: "M5 8h14l-1.4 10.2a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8L5 8Zm4 0V7a3 3 0 0 1 6 0v1",
  "Eating out": "M7 3v8m-2.5-8v5a2.5 2.5 0 0 0 5 0V3M7 11v10M17 21V3c-2.2 1.2-3.5 3.6-3.5 6.5V13H17",
  Takeaways: "M6 8h12l-1 12H7L6 8Zm3 0a3 3 0 0 1 6 0M9.5 12.5h5",
  Transport: "M6 16V7a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v9M6 16h12M6 16v3m12-3v3M6 11h12M8.5 13.5h.01M15.5 13.5h.01",
  "Bills & utilities": "M13 3 5 14h6l-1 7 8-11h-6l1-7Z",
  "Rent & housing": "M4 11 12 4l8 7M6 9.5V20h12V9.5M10 20v-5h4v5",
  Subscriptions: "M4 12a8 8 0 0 1 13.7-5.6L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.6L4 15.5M4 20v-4.5h4.5",
  Shopping: "M3.5 12.5 11 5h7v7l-7.5 7.5a1.5 1.5 0 0 1-2.1 0l-4.9-4.9a1.5 1.5 0 0 1 0-2.1ZM15 8.5h.01",
  Entertainment: "M4 8a2 2 0 0 0 2-2h12a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H6a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4V8Zm10-2v12",
  "Health & fitness": "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z",
  "Personal care": "M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5m7 7L18 18M6 18l2.5-2.5m7-7L18 6",
  Travel: "M10.5 13.5 4 11l1.5-1.5 6.5 1 4-4.5a2 2 0 0 1 3 3L14.5 13l1 6.5L14 21l-2.5-6.5L8 18v2.5L6.5 22 5 19l-3-1.5L3.5 16H6l3.5-3.5",
  Education: "M3 9l9-4 9 4-9 4-9-4Zm4 2v5c3 2 7 2 10 0v-5M21 9v5",
  "Gifts & charity": "M4 11h16v9H4v-9Zm-1-4h18v4H3V7Zm9 0v13M12 7c-1.5-3-5-3-5-1s3 1 5 1Zm0 0c1.5-3 5-3 5-1s-3 1-5 1Z",
  Cash: "M3 7h18v10H3V7Zm9 2.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5ZM6 10v4m12-4v4",
  "Fees & charges": "M6 18 18 6M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm8 8a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z",
  "Card repayments": "M3 7h18v10H3V7Zm0 3h18M7 14h3",
  Salary: "M4 8h16v11H4V8Zm5 0V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M4 13h16",
  "Other income": "M12 4v16m4-12.5c-.8-1.2-2.3-2-4-2-2.2 0-4 1.3-4 3s1.8 2.5 4 3 4 1.3 4 3-1.8 3-4 3c-1.7 0-3.2-.8-4-2",
  "From people": "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-5 9a5 5 0 0 1 10 0M16 11a2.5 2.5 0 1 0 0-5M17 15a4 4 0 0 1 3 5",
  Transfers: "M4 8h14m0 0-3-3m3 3-3 3M20 16H6m0 0 3-3m-3 3 3 3",
  Other: "M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17.5h.01",
};

export function CategoryIcon({ category, size = 18 }: { category: string; size?: number }) {
  return (
    <span className={`cat-icon${category === "Other" ? " unsorted" : ""}`} aria-hidden="true">
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}
           strokeLinecap="round" strokeLinejoin="round">
        <path d={PATHS[category] ?? PATHS.Other} />
      </svg>
    </span>
  );
}
