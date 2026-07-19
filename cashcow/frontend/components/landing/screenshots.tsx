"use client";

import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Workflow,
  FileText,
  ListOrdered,
  ScrollText,
} from "lucide-react";

const MOCKS = [
  { icon: LayoutDashboard, label: "Dashboard", color: "from-purple-500/20 to-blue-500/10" },
  { icon: Workflow, label: "Workflow", color: "from-blue-500/20 to-purple-500/10" },
  { icon: FileText, label: "Metadata Editor", color: "from-purple-500/20 to-blue-500/10" },
  { icon: ListOrdered, label: "Job Queue", color: "from-blue-500/20 to-purple-500/10" },
  { icon: ScrollText, label: "Logs", color: "from-purple-500/20 to-blue-500/10" },
];

export function Screenshots() {
  return (
    <section className="relative py-24">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            <span className="bg-gradient-to-r from-purple-300 to-blue-300 bg-clip-text text-transparent">
              Interface
            </span>
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Clean, intuitive screens for every part of the workflow.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {MOCKS.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="group overflow-hidden rounded-xl border border-white/5 bg-gradient-to-br from-white/[0.02] to-white/[0.01] backdrop-blur-sm transition-all hover:border-purple-500/20"
            >
              {/* Mock browser chrome */}
              <div className="flex items-center gap-1.5 border-b border-white/5 px-4 py-3">
                <span className="size-2.5 rounded-full bg-red-500/60" />
                <span className="size-2.5 rounded-full bg-yellow-500/60" />
                <span className="size-2.5 rounded-full bg-green-500/60" />
                <span className="ml-3 flex-1 rounded bg-white/5 px-3 py-1 text-[10px] text-muted-foreground">
                  cashcow.local/{m.label.toLowerCase().replace(/\s+/g, "-")}
                </span>
              </div>

              {/* Mock content area */}
              <div className="flex flex-col items-center justify-center p-12">
                <div
                  className={`flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br ${m.color} mb-4`}
                >
                  <m.icon size={28} className="text-purple-300" />
                </div>
                <span className="text-sm font-medium text-foreground">
                  {m.label}
                </span>
                <span className="mt-1 text-xs text-muted-foreground">
                  Interface Preview
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
