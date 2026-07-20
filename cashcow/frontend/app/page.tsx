import { LandingNav } from "@/components/landing/nav";
import { Hero } from "@/components/landing/hero";
import { Stats } from "@/components/landing/stats";
import { Features } from "@/components/landing/features";
import { WorkflowSection } from "@/components/landing/workflow-section";
import { TechStack } from "@/components/landing/tech-stack";
import { Screenshots } from "@/components/landing/screenshots";
import { OfflineFirst } from "@/components/landing/offline-first";
import { LandingFooter } from "@/components/landing/footer";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingNav />
      <Hero />
      <Stats />
      <Features />
      <WorkflowSection />
      <TechStack />
      <Screenshots />
      <OfflineFirst />
      <LandingFooter />
    </div>
  );
}
