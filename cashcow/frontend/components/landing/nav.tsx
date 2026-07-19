"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

const LINKS = [
  { label: "Features", href: "#features" },
  { label: "Workflow", href: "#workflow" },
  { label: "Technology", href: "#tech" },
  { label: "Dashboard", href: "/dashboard" },
];

export function LandingNav() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-black/60 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-xl font-bold tracking-tight text-transparent">
            CashCow
          </span>
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          {LINKS.slice(0, 3).map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {l.label}
            </a>
          ))}
          <Link
            href="/dashboard"
            className="rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            Dashboard
          </Link>
          <a
            href="https://github.com/anomalyco/opencode"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            GitHub
          </a>
        </div>

        <button
          onClick={() => setOpen(!open)}
          className="text-muted-foreground md:hidden"
          aria-label="Toggle menu"
        >
          {open ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {open && (
        <div className="border-t border-white/5 bg-black/90 px-6 pb-4 pt-2 md:hidden">
          <div className="flex flex-col gap-3">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
            <a
              href="https://github.com/anomalyco/opencode"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              GitHub
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
