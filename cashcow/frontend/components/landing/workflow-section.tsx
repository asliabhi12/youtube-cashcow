"use client";

import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";

const STEPS = [
  "Video URL",
  "Download",
  "Processing",
  "Transcript",
  "Metadata",
  "Upload",
  "Completed",
];

export function WorkflowSection() {
  return (
    <section id="workflow" className="relative py-24">
      <div className="mx-auto max-w-3xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            <span className="bg-gradient-to-r from-purple-300 to-blue-300 bg-clip-text text-transparent">
              How It Works
            </span>
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            A simple, reliable pipeline from URL to YouTube.
          </p>
        </motion.div>

        <div className="mt-12 space-y-0">
          {STEPS.map((step, i) => (
            <div key={step} className="flex items-start gap-4">
              <div className="flex flex-col items-center">
                <motion.div
                  initial={{ scale: 0 }}
                  whileInView={{ scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1, type: "spring", stiffness: 200 }}
                  className="flex size-8 items-center justify-center rounded-full border border-purple-500/30 bg-purple-500/10"
                >
                  <CheckCircle2 size={16} className="text-purple-400" />
                </motion.div>
                {i < STEPS.length - 1 && (
                  <div className="mt-1 h-10 w-px bg-gradient-to-b from-purple-500/30 to-transparent" />
                )}
              </div>
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.4 }}
                className="flex h-8 items-center"
              >
                <span className="text-sm font-medium text-foreground">
                  {step}
                </span>
              </motion.div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
