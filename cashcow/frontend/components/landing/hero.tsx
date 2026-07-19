"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";

export function Hero() {
  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden pt-16">
      {/* Floating gradient blobs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 -top-32 h-[500px] w-[500px] rounded-full bg-purple-600/20 blur-[120px]" />
        <div className="absolute -right-32 top-1/3 h-[400px] w-[400px] rounded-full bg-blue-600/15 blur-[100px]" />
        <div className="absolute -bottom-32 left-1/3 h-[350px] w-[350px] rounded-full bg-purple-500/10 blur-[90px]" />
      </div>

      <div className="relative z-10 mx-auto max-w-5xl px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-purple-500/20 bg-purple-500/10 px-4 py-1.5 text-xs font-medium text-purple-300">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-2 animate-ping rounded-full bg-purple-400" />
              <span className="relative inline-flex size-2 rounded-full bg-purple-500" />
            </span>
            Offline-First Architecture
          </div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: "easeOut" }}
          className="text-5xl font-bold tracking-tight sm:text-6xl md:text-7xl"
        >
          <span className="bg-gradient-to-r from-purple-300 via-white to-blue-300 bg-clip-text text-transparent">
            CashCow
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2, ease: "easeOut" }}
          className="mt-4 text-lg text-purple-200/80 sm:text-xl"
        >
          Offline-First AI Video Automation
        </motion.p>

        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3, ease: "easeOut" }}
          className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base"
        >
          Automate YouTube content creation entirely on your own device.
          Download videos, process media, generate AI metadata, and publish to
          YouTube while keeping your data private.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4, ease: "easeOut" }}
          className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row"
        >
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-600/25 transition-all hover:shadow-purple-600/40 hover:scale-[1.02]"
          >
            Launch Dashboard
            <ArrowRight size={16} />
          </Link>
          <a
            href="#workflow"
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-foreground backdrop-blur-sm transition-all hover:bg-white/10"
          >
            <Play size={16} />
            Watch Demo
          </a>
        </motion.div>

        {/* Animated workflow illustration */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.6, ease: "easeOut" }}
          className="mt-16"
        >
          <div className="mx-auto max-w-3xl rounded-2xl border border-white/5 bg-white/[0.02] p-6 backdrop-blur-sm">
            <div className="flex flex-wrap items-center justify-center gap-2 text-xs sm:gap-3 sm:text-sm">
              {[
                "Video URL",
                "Download",
                "Process",
                "Transcript",
                "Metadata",
                "Upload",
              ].map((step, i) => (
                <div key={step} className="flex items-center gap-2 sm:gap-3">
                  <span className="rounded-lg border border-purple-500/20 bg-purple-500/10 px-3 py-1.5 font-medium text-purple-300">
                    {step}
                  </span>
                  {i < 5 && (
                    <span className="text-muted-foreground/40">&rarr;</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
