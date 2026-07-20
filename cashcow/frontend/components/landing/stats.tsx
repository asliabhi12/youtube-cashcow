"use client";

import { motion } from "framer-motion";
import { Activity, CheckCircle2, Cpu, Server } from "lucide-react";

const STATS = [
  { icon: Activity, value: "10+", label: "Pipeline steps" },
  { icon: CheckCircle2, value: "138", label: "Backend tests" },
  { icon: Server, value: "Local", label: "Processing mode" },
  { icon: Cpu, value: "Multi", label: "AI provider routing" },
];

export function Stats() {
  return (
    <section className="border-b py-14">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: index * 0.04 }}
              className="rounded-xl border bg-card/70 p-5 shadow-sm shadow-[var(--shadow-color)]"
            >
              <stat.icon className="size-4 text-primary" />
              <p className="mt-4 text-2xl font-semibold tracking-tight">{stat.value}</p>
              <p className="mt-1 text-sm text-muted-foreground">{stat.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
