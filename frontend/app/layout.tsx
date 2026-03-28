import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolicyBridge — Compliance Conversion Platform",
  description: "AI-powered policy migration to Irish & EU law compliance",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
