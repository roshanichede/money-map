import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MoneyMap",
  description: "Upload your bank statements and see where your money went, in plain English. No bank login.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-GB">
      <body>{children}</body>
    </html>
  );
}
