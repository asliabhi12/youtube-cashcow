"use client";

import { motion } from "framer-motion";
import { Server, ShieldCheck, WifiOff } from "lucide-react";

export function OfflineFirst() {
  return (
    <section className="border-b py-24">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.45 }}
          className="grid gap-8 rounded-xl border bg-card/80 p-6 shadow-xl shadow-[var(--shadow-color)] lg:grid-cols-[minmax(0,1fr)_24rem] lg:p-8"
        >
          <div>
            <div className="grid size-11 place-items-center rounded-md border border-primary/20 bg-primary/10 text-primary">
              <WifiOff className="size-5" />
            </div>
            <h2 className="mt-6 text-3xl font-semibold tracking-tight sm:text-4xl">
              Demo mode is a first-class state.
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
              CashCow is designed to run with a local backend. When that backend is unavailable, the interface clearly switches to a preview state instead of surfacing broken workflow errors.
            </p>
          </div>

          <div className="grid gap-3">
            <div className="rounded-lg border bg-background/45 p-4">
              <Server className="size-4 text-primary" />
              <p className="mt-3 text-sm font-semibold">Local backend</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">Enables real downloads, processing, metadata, and publishing.</p>
            </div>
            <div className="rounded-lg border bg-background/45 p-4">
              <ShieldCheck className="size-4 text-primary" />
              <p className="mt-3 text-sm font-semibold">Private workflow</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">Core video operations stay on your machine by default.</p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
