"use client";

import { motion } from "framer-motion";
import { Activity, CheckCircle2, Server, Cpu } from "lucide-react";

const STATS = [
  { icon: Activity, value: "10+", label: "Workflow Steps" },
  { icon: CheckCircle2, value: "138", label: "Passing Tests" },
  { icon: Server, value: "100%", label: "Offline-First" },
  { icon: Cpu, value: "Multi", label: "Model AI Support" },
];

export function Stats() {
  return (
    <section className="relative py-16">
      <div className="mx-auto max-w-5xl px-6">
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          {STATS.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="flex flex-col items-center rounded-xl border border-white/5 bg-white/[0.02] p-6 backdrop-blur-sm"
            >
              <s.icon size={20} className="text-purple-400" />
              <span className="mt-3 text-2xl font-bold text-foreground">
                {s.value}
              </span>
              <span className="mt-1 text-xs text-muted-foreground">
                {s.label}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
