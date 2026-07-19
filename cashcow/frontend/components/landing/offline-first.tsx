"use client";

import { motion } from "framer-motion";
import { Server, WifiOff } from "lucide-react";

export function OfflineFirst() {
  return (
    <section className="relative py-24">
      <div className="mx-auto max-w-5xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6 }}
          className="relative overflow-hidden rounded-2xl border border-purple-500/10 bg-gradient-to-br from-purple-900/20 via-blue-900/10 to-black p-8 sm:p-12"
        >
          {/* Decorative blobs */}
          <div className="pointer-events-none absolute -right-20 -top-20 h-60 w-60 rounded-full bg-purple-600/10 blur-[80px]" />
          <div className="pointer-events-none absolute -bottom-20 -left-20 h-60 w-60 rounded-full bg-blue-600/10 blur-[80px]" />

          <div className="relative z-10 flex flex-col items-center text-center">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-purple-500/10">
              <WifiOff size={28} className="text-purple-400" />
            </div>

            <h2 className="mt-6 text-3xl font-bold tracking-tight sm:text-4xl">
              <span className="bg-gradient-to-r from-purple-300 to-blue-300 bg-clip-text text-transparent">
                Built for Local AI
              </span>
            </h2>

            <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
              CashCow is designed for creators who prefer local processing over
              cloud uploads. Your videos remain on your device throughout the
              workflow. The hosted demo showcases the interface only.
            </p>

            <div className="mt-8 flex items-center gap-8 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Server size={16} className="text-purple-400" />
                <span>100% Local</span>
              </div>
              <div className="flex items-center gap-2">
                <WifiOff size={16} className="text-purple-400" />
                <span>No Cloud Required</span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
