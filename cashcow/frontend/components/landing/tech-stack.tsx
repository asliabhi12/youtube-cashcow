"use client";

import { motion } from "framer-motion";

const GROUPS = [
  { title: "Frontend", tech: ["Next.js", "React", "Tailwind CSS"] },
  { title: "Backend", tech: ["Python", "FastAPI", "SQLite"] },
  { title: "Media", tech: ["FFmpeg", "yt-dlp", "YouTube API"] },
  { title: "AI", tech: ["OpenRouter", "Gemini", "Fallback routing"] },
];

export function TechStack() {
  return (
    <section id="tech" className="border-b py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
              Technology
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              Practical tools, cleanly organized.
            </h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-muted-foreground">
            The stack stays familiar and maintainable, with no extra UI dependencies added for the redesign.
          </p>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-4">
          {GROUPS.map((group, index) => (
            <motion.div
              key={group.title}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: index * 0.04 }}
              className="rounded-xl border bg-card/70 p-5 shadow-sm shadow-[var(--shadow-color)]"
            >
              <h3 className="text-sm font-semibold">{group.title}</h3>
              <div className="mt-4 flex flex-wrap gap-2">
                {group.tech.map((tech) => (
                  <span key={tech} className="rounded-md border bg-background/50 px-2.5 py-1 text-xs text-muted-foreground">
                    {tech}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
