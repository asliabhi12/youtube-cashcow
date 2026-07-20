"use client";

import { motion } from "framer-motion";
import { Bot, Clapperboard, Download, FileText, Scissors, UploadCloud } from "lucide-react";

const STEPS = [
  { icon: Clapperboard, title: "Capture source", description: "Paste a YouTube URL and fetch video details." },
  { icon: Download, title: "Download locally", description: "Pull media into the local processing workspace." },
  { icon: Scissors, title: "Process clip", description: "Trim, resize, grade, overlay, and encode." },
  { icon: Bot, title: "Generate metadata", description: "Create AI title, description, and tags." },
  { icon: FileText, title: "Review output", description: "Inspect logs, progress, metadata, and files." },
  { icon: UploadCloud, title: "Publish", description: "Download the result or upload to YouTube." },
];

export function WorkflowSection() {
  return (
    <section id="workflow" className="border-b py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-10 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
              Workflow
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              One visible run from source to publishing.
            </h2>
            <p className="mt-4 text-base leading-7 text-muted-foreground">
              The interface shows where every job is, what is running now, and what needs attention.
            </p>
          </div>

          <div className="rounded-xl border bg-card/75 p-4 shadow-xl shadow-[var(--shadow-color)]">
            <div className="grid gap-3 md:grid-cols-2">
              {STEPS.map((step, index) => (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, y: 14 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-60px" }}
                  transition={{ duration: 0.35, delay: index * 0.04 }}
                  className="rounded-lg border bg-background/45 p-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                      <step.icon className="size-4" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold">{step.title}</p>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">{step.description}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
