"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Play, ShieldCheck } from "lucide-react";

const STEPS = [
  { label: "URL", detail: "Source locked" },
  { label: "Profile", detail: "Rules applied" },
  { label: "Process", detail: "FFmpeg run" },
  { label: "Metadata", detail: "AI copy" },
  { label: "Publish", detail: "YouTube ready" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b pt-24">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-7xl items-center gap-12 px-6 pb-16 pt-10 lg:grid-cols-[minmax(0,1fr)_30rem]">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <div className="inline-flex items-center gap-2 rounded-full border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
            <ShieldCheck className="size-3.5 text-primary" />
            Local-first AI video operations
          </div>

          <h1 className="mt-6 max-w-4xl text-5xl font-semibold tracking-tight text-foreground sm:text-6xl lg:text-7xl">
            CashCow
          </h1>
          <p className="mt-5 max-w-2xl text-xl leading-8 text-foreground/85 sm:text-2xl">
            A professional workflow console for turning source videos into finished YouTube assets.
          </p>
          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground">
            Download, process, generate AI metadata, and publish through a private local pipeline with queue visibility and reusable creative profiles.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/dashboard"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/15 transition-all hover:bg-primary/90 hover:shadow-primary/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Launch dashboard
              <ArrowRight className="size-4" />
            </Link>
            <a
              href="#workflow"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md border bg-card/70 px-5 text-sm font-medium text-foreground shadow-sm transition-all hover:border-primary/35 hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Play className="size-4" />
              View workflow
            </a>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.1, ease: "easeOut" }}
          className="rounded-xl border bg-card/85 p-4 shadow-2xl shadow-[var(--shadow-color)]"
        >
          <div className="flex items-center justify-between border-b pb-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Workflow run
              </p>
              <p className="mt-1 text-sm font-semibold">Mumbai ride edit</p>
            </div>
            <span className="rounded-full border border-success-border bg-success-surface px-2.5 py-1 text-xs font-medium text-success-foreground">
              Ready
            </span>
          </div>

          <div className="mt-5 space-y-3">
            {STEPS.map((step, index) => (
              <div key={step.label} className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-3">
                <span className="grid size-8 place-items-center rounded-md border border-primary/20 bg-primary/10 text-primary">
                  <CheckCircle2 className="size-4" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{step.label}</p>
                  <p className="truncate text-xs text-muted-foreground">{step.detail}</p>
                </div>
                <span className="font-mono text-xs text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-lg border bg-background/45 p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-muted-foreground">Pipeline progress</span>
              <span className="font-mono text-foreground">84%</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-muted">
              <div className="h-full w-[84%] rounded-full bg-primary" />
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
