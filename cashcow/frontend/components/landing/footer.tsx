import Link from "next/link";

export function LandingFooter() {
  return (
    <footer className="border-t border-white/5">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-6 py-10 sm:flex-row sm:justify-between">
        <div className="text-center sm:text-left">
          <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-sm font-bold text-transparent">
            CashCow
          </span>
          <p className="mt-1 text-xs text-muted-foreground">
            Offline-First AI Video Automation
          </p>
        </div>

        <div className="flex items-center gap-6 text-xs text-muted-foreground">
          <span>Built for Hackathon 2026</span>
          <a
            href="https://github.com/anomalyco/opencode"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-foreground"
          >
            GitHub
          </a>
          <Link
            href="/dashboard"
            className="transition-colors hover:text-foreground"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </footer>
  );
}
