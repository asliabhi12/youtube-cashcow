"use client";

import { motion } from "framer-motion";

const TECHS = [
  "Python",
  "FastAPI",
  "Next.js",
  "TailwindCSS",
  "SQLite",
  "OpenRouter",
  "Gemini",
  "FFmpeg",
  "yt-dlp",
  "YouTube API",
];

export function TechStack() {
  return (
    <section id="tech" className="relative py-24">
      <div className="mx-auto max-w-5xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            <span className="bg-gradient-to-r from-purple-300 to-blue-300 bg-clip-text text-transparent">
              Technology
            </span>
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Built with modern, battle-tested tools.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mt-10 flex flex-wrap justify-center gap-3"
        >
          {TECHS.map((tech) => (
            <span
              key={tech}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-muted-foreground backdrop-blur-sm transition-all hover:border-purple-500/30 hover:text-purple-300"
            >
              {tech}
            </span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
