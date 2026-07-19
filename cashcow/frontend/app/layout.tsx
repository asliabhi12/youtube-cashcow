import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "CashCow — Offline-First AI Video Automation",
  description:
    "Automate YouTube content creation entirely on your own device. Download videos, process media, generate AI metadata, and publish to YouTube while keeping your data private.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="antialiased bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
