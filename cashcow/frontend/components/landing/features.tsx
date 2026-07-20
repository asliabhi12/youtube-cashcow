"use client";

import { motion } from "framer-motion";
import { Cpu, Route, Shield, Sparkles, Upload, Workflow } from "lucide-react";

const FEATURES = [
  {
    icon: Cpu,
    title: "Local media engine",
    description:
      "Downloading, trimming, encoding, transcription, and file handling run on your machine.",
  },
  {
    icon: Sparkles,
    title: "AI metadata generation",
    description:
      "Create titles, descriptions, and tags with provider fallback when a model is unavailable.",
  },
  {
    icon: Workflow,
    title: "Reusable creative profiles",
    description:
      "Save resize, audio, colour, overlay, and export settings as profiles for repeatable runs.",
  },
  {
    icon: Route,
    title: "Resumable workflows",
    description:
      "Skip completed work and recover interrupted jobs without restarting the entire pipeline.",
  },
  {
    icon: Upload,
    title: "Publishing controls",
    description:
      "Export files or upload to YouTube with retry support and visible job progress.",
  },
  {
    icon: Shield,
    title: "Private by default",
    description:
      "Core processing stays local, with cloud AI and YouTube services used only when configured.",
  },
];

export function Features() {
  return (
    <section id="features" className="border-b py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Platform
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            Built for creators who want an operations-grade workflow.
          </h2>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            CashCow brings the media pipeline, AI copywriting, queue state, and publishing handoff into one calm interface.
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.4, delay: index * 0.04 }}
              className="group rounded-xl border bg-card/70 p-5 shadow-sm shadow-[var(--shadow-color)] transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-lg"
            >
              <div className="grid size-10 place-items-center rounded-md border border-primary/20 bg-primary/10 text-primary">
                <feature.icon className="size-5" />
              </div>
              <h3 className="mt-5 text-base font-semibold tracking-tight">{feature.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
