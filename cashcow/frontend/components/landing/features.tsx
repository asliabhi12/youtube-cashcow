"use client";

import { motion } from "framer-motion";
import {
  Cpu,
  Sparkles,
  Workflow,
  Route,
  Upload,
  Shield,
} from "lucide-react";

const FEATURES = [
  {
    icon: Cpu,
    title: "Offline First",
    description:
      "All downloading, processing, transcription, and AI automation happens locally on your device. No cloud processing required.",
  },
  {
    icon: Sparkles,
    title: "AI Metadata",
    description:
      "Generate optimized titles, descriptions, and tags using multiple AI providers with automatic model fallback.",
  },
  {
    icon: Workflow,
    title: "Smart Workflow",
    description:
      "Resume interrupted jobs. Skip completed work. Persistent task memory prevents redundant processing.",
  },
  {
    icon: Route,
    title: "Automatic Model Routing",
    description:
      "If one AI provider fails, CashCow automatically switches to another configured model without losing progress.",
  },
  {
    icon: Upload,
    title: "YouTube Publishing",
    description:
      "Upload videos directly to YouTube with retry support and progress tracking throughout the pipeline.",
  },
  {
    icon: Shield,
    title: "Privacy",
    description:
      "Your videos stay on your computer. Cloud services are optional and never required for core functionality.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative py-24">
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
              Everything You Need
            </span>
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            A complete local-first video automation pipeline.
          </p>
        </motion.div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="group rounded-xl border border-white/5 bg-white/[0.02] p-6 backdrop-blur-sm transition-all hover:border-purple-500/20 hover:bg-white/[0.04]"
            >
              <div className="flex size-10 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                <f.icon size={20} />
              </div>
              <h3 className="mt-4 font-semibold text-foreground">
                {f.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {f.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
