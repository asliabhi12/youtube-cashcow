import Link from "next/link";
import { BookOpen, Github, LayoutDashboard } from "lucide-react";

const LINKS = [
  { label: "GitHub", href: "https://github.com/anomalyco/opencode", icon: Github, external: true },
  { label: "Documentation", href: "/#workflow", icon: BookOpen, external: false },
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, external: false },
];

export function LandingFooter() {
  return (
    <footer>
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="grid size-8 place-items-center rounded-md border border-primary/25 bg-primary/10 text-xs font-semibold text-primary">
              CC
            </span>
            <span className="text-sm font-semibold tracking-tight">CashCow</span>
          </div>
          <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
            Offline-first AI video automation for repeatable creator workflows.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          {LINKS.map((link) => {
            const content = (
              <>
                <link.icon className="size-4" />
                {link.label}
              </>
            );
            const className =
              "inline-flex items-center gap-2 rounded-md border bg-card/70 px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

            return link.external ? (
              <a key={link.label} href={link.href} target="_blank" rel="noopener noreferrer" className={className}>
                {content}
              </a>
            ) : (
              <Link key={link.label} href={link.href} className={className}>
                {content}
              </Link>
            );
          })}
        </div>
      </div>
    </footer>
  );
}
