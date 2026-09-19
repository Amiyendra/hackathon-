import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aurethis QA — Control Center | No Sale Ships Unscored",
  description: "Deterministic B2B AI Operations & Compliance QA Gate Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-50/50 text-slate-900 min-h-screen">
        {children}
      </body>
    </html>
  );
}
