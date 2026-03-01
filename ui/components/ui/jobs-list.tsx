"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Job {
  title: string;
  summary: string;
  salaryRange: string;
  location: string;
  employmentType: string;
  level: string;
  description: string;
  responsibilities: string[];
  requirements: string[];
  skills: string[];
}

const jobs: Job[] = [
  {
    title: "Software Engineer",
    summary: "Build core product features across frontend and backend systems.",
    salaryRange: "$90,000 - $130,000",
    location: "Istanbul (Hybrid)",
    employmentType: "Full-time",
    level: "Mid / Senior",
    description:
      "You will design, build, and maintain user-facing and backend features with a strong focus on reliability, performance, and developer experience.",
    responsibilities: [
      "Ship end-to-end features with product and design teams.",
      "Write maintainable, tested code and review peer PRs.",
      "Improve system performance, observability, and reliability.",
    ],
    requirements: [
      "3+ years software engineering experience.",
      "Strong TypeScript/React and backend API fundamentals.",
      "Experience with SQL databases and cloud deployments.",
    ],
    skills: ["TypeScript", "React/Next.js", "Python/Node.js", "PostgreSQL", "Docker", "CI/CD"],
  },
  {
    title: "Data Scientist",
    summary: "Drive decisions and ML features through data and experimentation.",
    salaryRange: "$95,000 - $140,000",
    location: "Istanbul / Remote",
    employmentType: "Full-time",
    level: "Mid / Senior",
    description:
      "You will own analytical workflows and predictive modeling efforts, from framing business problems to production impact measurement.",
    responsibilities: [
      "Build and validate predictive models and forecasts.",
      "Design and analyze A/B tests for product decisions.",
      "Partner with engineering to deploy and monitor models.",
    ],
    requirements: [
      "Strong Python, SQL, and statistics foundations.",
      "Hands-on experience with ML model development.",
      "Ability to communicate insights to non-technical teams.",
    ],
    skills: ["Python", "SQL", "scikit-learn/PyTorch", "A/B Testing", "BigQuery/Snowflake", "MLOps"],
  },
  {
    title: "Product Manager",
    summary: "Own roadmap and cross-functional execution for core product areas.",
    salaryRange: "$100,000 - $150,000",
    location: "Istanbul (Hybrid)",
    employmentType: "Full-time",
    level: "Senior",
    description:
      "You will define priorities, align stakeholders, and ensure product delivery tracks to clear business and user outcomes.",
    responsibilities: [
      "Define product strategy, roadmap, and success metrics.",
      "Run discovery and turn insights into actionable plans.",
      "Coordinate execution across design, engineering, and GTM.",
    ],
    requirements: [
      "4+ years PM experience in digital products.",
      "Strong analytical and prioritization skills.",
      "Excellent communication and stakeholder management.",
    ],
    skills: ["Roadmapping", "User Discovery", "PRDs", "Analytics", "Stakeholder Alignment", "Delivery"],
  },
  {
    title: "UX Designer",
    summary: "Design intuitive, high-impact user journeys for web experiences.",
    salaryRange: "$80,000 - $120,000",
    location: "Istanbul / Remote",
    employmentType: "Full-time",
    level: "Mid / Senior",
    description:
      "You will lead UX work from discovery to polished interfaces while collaborating closely with product and engineering.",
    responsibilities: [
      "Create user flows, wireframes, and high-fidelity designs.",
      "Run usability tests and iterate on findings.",
      "Contribute to design system consistency and accessibility.",
    ],
    requirements: [
      "Strong portfolio with shipped digital products.",
      "Expertise in Figma and interaction design.",
      "Experience with research and usability methods.",
    ],
    skills: ["Figma", "UX Research", "Prototyping", "Design Systems", "Accessibility", "Interaction Design"],
  },
  {
    title: "DevOps Engineer",
    summary: "Scale infrastructure and delivery pipelines for reliability and speed.",
    salaryRange: "$95,000 - $145,000",
    location: "Istanbul (Hybrid)",
    employmentType: "Full-time",
    level: "Mid / Senior",
    description:
      "You will own CI/CD, infrastructure as code, and production observability to support secure and stable software delivery.",
    responsibilities: [
      "Build and maintain CI/CD workflows across services.",
      "Automate cloud infrastructure and deployment operations.",
      "Improve monitoring, alerting, and incident response readiness.",
    ],
    requirements: [
      "Hands-on cloud + container orchestration experience.",
      "Strong Terraform and automation mindset.",
      "Experience with monitoring and production support.",
    ],
    skills: ["AWS/GCP", "Docker", "Kubernetes", "Terraform", "GitHub Actions", "Observability"],
  },
  {
    title: "AI Engineer",
    summary: "Build production AI workflows with LLMs, RAG, and evaluation.",
    salaryRange: "$110,000 - $170,000",
    location: "Istanbul / Remote",
    employmentType: "Full-time",
    level: "Senior",
    description:
      "You will design and deploy AI features with strong guardrails, monitoring, and quality evaluation to support real user workflows.",
    responsibilities: [
      "Implement agentic and retrieval-based AI pipelines.",
      "Define evaluation suites and regression monitoring.",
      "Optimize latency/cost while preserving output quality.",
    ],
    requirements: [
      "Strong Python and API integration experience.",
      "Experience with LLM orchestration and vector search.",
      "Production mindset for reliability and observability.",
    ],
    skills: ["Python", "LLM APIs", "RAG", "Vector DBs", "FastAPI", "Evals & Monitoring"],
  },
];

interface JobsListProps {
  onApply?: (jobTitle: string) => void;
}

export default function JobsList({ onApply }: JobsListProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  const sectionRef = useRef<HTMLElement>(null);
  const isScrollingBack = useRef(false);
  const isScrollingToApply = useRef(false);

  const handleBack = () => {
    isScrollingBack.current = true;
    setSelectedIndex(null);
    setExpandedIndex(null);
    setIsVisible(false);
    setTimeout(() => {
      document.getElementById("hero")?.scrollIntoView({ behavior: "smooth" });
      setTimeout(() => {
        isScrollingBack.current = false;
      }, 1000);
    }, 50);
  };

  const toggle = (index: number) => {
    if (selectedIndex === index) {
      setSelectedIndex(null);
      setExpandedIndex(null);
    } else {
      setExpandedIndex(index);
      setSelectedIndex(index);
    }
  };

  useEffect(() => {
    const handleScroll = () => {
      if (isScrollingBack.current || isScrollingToApply.current) return;
      const section = sectionRef.current;
      if (!section) return;
      const rect = section.getBoundingClientRect();
      const visibleHeight = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
      const ratio = visibleHeight / rect.height;
      setIsVisible(ratio > 0.3);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <section
      ref={sectionRef}
      id="jobs"
      className="relative min-h-screen flex items-center justify-center py-24 px-6"
    >
      <div className="w-full max-w-2xl space-y-3">
        <div className="pb-4 text-center">
          <p className="text-xs uppercase tracking-[0.18em] text-foreground/45">Role Catalog</p>
          <h2 className="mt-2 text-2xl sm:text-3xl font-semibold text-foreground">Choose the role you want to interview for</h2>
          <p className="mt-2 text-sm sm:text-base text-foreground/55">
            Each role includes dedicated requirements, interview focus, and evaluation criteria.
          </p>
        </div>
        {jobs.map((job, index) => {
          const isSelected = selectedIndex === index;
          return (
            <motion.div
              key={job.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: index * 0.08 }}
            >
              <button
                onClick={() => toggle(index)}
                style={isSelected ? { outline: "2px solid rgba(255,255,255,0.5)", outlineOffset: "-2px" } : undefined}
                className={`w-full text-left rounded-xl backdrop-blur-2xl transition-all duration-300 overflow-hidden ${
                  isSelected
                    ? "bg-white/[0.07] shadow-[0_0_20px_rgba(255,255,255,0.1)]"
                    : "bg-white/[0.04] hover:bg-white/[0.07]"
                }`}
              >
                <div className="flex items-center justify-between px-6 py-5">
                  <span className="text-lg font-medium text-foreground">
                    {job.title}
                  </span>
                  <motion.span
                    animate={{ rotate: expandedIndex === index ? 45 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-foreground/50 text-xl"
                  >
                    +
                  </motion.span>
                </div>

                <AnimatePresence initial={false}>
                  {expandedIndex === index && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{
                        duration: 0.3,
                        ease: [0.25, 0.1, 0.25, 1],
                      }}
                      className="overflow-hidden"
                    >
                      <div className="px-6 pb-5 space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <div className="rounded-lg border border-foreground/10 bg-foreground/[0.03] px-3 py-2">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45">Salary</p>
                            <p className="mt-1 text-sm text-foreground/85">{job.salaryRange}</p>
                          </div>
                          <div className="rounded-lg border border-foreground/10 bg-foreground/[0.03] px-3 py-2">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45">Level</p>
                            <p className="mt-1 text-sm text-foreground/85">{job.level}</p>
                          </div>
                          <div className="rounded-lg border border-foreground/10 bg-foreground/[0.03] px-3 py-2">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45">Location</p>
                            <p className="mt-1 text-sm text-foreground/85">{job.location}</p>
                          </div>
                          <div className="rounded-lg border border-foreground/10 bg-foreground/[0.03] px-3 py-2">
                            <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45">Employment</p>
                            <p className="mt-1 text-sm text-foreground/85">{job.employmentType}</p>
                          </div>
                        </div>

                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45 mb-1">Role Summary</p>
                          <p className="text-foreground/70 text-sm leading-relaxed">{job.summary}</p>
                        </div>

                        <p className="text-foreground/70 text-sm leading-relaxed">
                          {job.description}
                        </p>

                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45 mb-1">What You Will Do</p>
                          <ul className="space-y-1">
                            {job.responsibilities.map((item) => (
                              <li key={item} className="text-foreground/75 text-sm leading-relaxed">
                                • {item}
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-foreground/45 mb-1">What We Are Looking For</p>
                          <ul className="space-y-1">
                            {job.requirements.map((item) => (
                              <li key={item} className="text-foreground/75 text-sm leading-relaxed">
                                • {item}
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          {job.skills.map((skill) => (
                            <Badge
                              key={skill}
                              variant="secondary"
                              className="bg-foreground/10 text-foreground/80 border-foreground/15 text-xs"
                            >
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </button>
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed bottom-8 left-8 z-50"
          >
            <Button
              size="lg"
              variant="outline"
              className="group h-auto border-white/20 text-foreground hover:bg-white/10 transition-all duration-300 backdrop-blur-xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
              onClick={handleBack}
            >
              <span className="relative block">
                <span className="block transition-opacity duration-300 group-hover:opacity-0">Back to Hero</span>
                <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&larr;</span>
              </span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedIndex !== null && isVisible && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed bottom-8 right-8 z-50"
          >
            <Button
              size="lg"
              className="group h-auto bg-white text-black hover:bg-white/90 transition-all duration-300 shadow-2xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
              onClick={() => {
                if (onApply && selectedIndex !== null) {
                  isScrollingToApply.current = true;
                  setIsVisible(false);
                  onApply(jobs[selectedIndex].title);
                  setTimeout(() => {
                    isScrollingToApply.current = false;
                  }, 1500);
                }
              }}
            >
              <span className="relative block">
                <span className="block transition-opacity duration-300 group-hover:opacity-0">Select Role</span>
                <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&rarr;</span>
              </span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
