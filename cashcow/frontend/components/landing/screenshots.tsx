"use client";

import { motion } from "framer-motion";
import { LayoutDashboard, ListOrdered, ScrollText } from "lucide-react";

const PREVIEWS = [
  { icon: LayoutDashboard, title: "Dashboard", rows: ["YouTube URL", "Creative profile", "Export quality"] },
  { icon: ListOrdered, title: "Job queue", rows: ["Running", "Queued", "Completed"] },
  { icon: ScrollText, title: "Logs", rows: ["Download", "Encode", "Metadata"] },
];

export function Screenshots() {
  return (
    <section className="border-b py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Interface
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            Purpose-built screens for repeated workflow use.
          </h2>
        </div>

        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          {PREVIEWS.map((preview, index) => (
            <motion.div
              key={preview.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: index * 0.05 }}
              className="overflow-hidden rounded-xl border bg-card/75 shadow-xl shadow-[var(--shadow-color)]"
            >
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div className="flex items-center gap-2">
                  <preview.icon className="size-4 text-primary" />
                  <span className="text-sm font-semibold">{preview.title}</span>
                </div>
                <span className="rounded-full bg-success-surface px-2 py-0.5 text-[11px] font-medium text-success-foreground">
                  Live
                </span>
              </div>
              <div className="space-y-3 p-4">
                {preview.rows.map((row, rowIndex) => (
                  <div key={row} className="rounded-lg border bg-background/45 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{row}</span>
                      <span className="font-mono text-xs text-muted-foreground">
                        0{rowIndex + 1}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${90 - rowIndex * 18}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
