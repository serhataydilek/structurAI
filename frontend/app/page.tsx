import Link from "next/link";
import { ArrowRight, Building2, Cpu, FileText, ScanLine, Video, type LucideIcon } from "lucide-react";

const featureCards: Array<{ title: string; text: string; Icon: LucideIcon }> = [
  { title: "Inspection", text: "Review capture quality, surface concerns, and progress remotely.", Icon: ScanLine },
  { title: "Renovation", text: "Mark potential renovation zones and share capture-backed summaries.", Icon: FileText },
  { title: "Progress Tracking", text: "Prepare the pipeline for repeat captures on active construction sites.", Icon: Video }
];

const pipeline = [
  "Phone Photos / Video",
  "Upload Service",
  "Frame Extraction",
  "COLMAP Optional Validation / Sparse Reconstruction Check",
  "RealityScan Primary Client-Quality Model Generation",
  "OBJ + MTL + Texture ZIP",
  "Model Artifacts + Readiness Report"
];

export default function LandingPage() {
  return (
    <main className="min-h-screen px-5 py-6">
      <nav className="mx-auto flex max-w-7xl items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md border border-brand/40 bg-brand/10">
            <Building2 className="text-brand" size={20} />
          </span>
          <span className="font-semibold tracking-wide text-white">Structura AI</span>
        </Link>
        <Link href="/dashboard" className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 hover:bg-white/10">
          Dashboard
        </Link>
      </nav>

      <section className="mx-auto grid min-h-[74vh] max-w-7xl items-center gap-10 py-12 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <div className="mb-5 inline-flex rounded-full border border-brand/25 bg-brand/10 px-3 py-1 text-xs font-medium text-cyan-100">
            Local capture to sparse reconstruction prototype
          </div>
          <h1 className="max-w-4xl text-5xl font-semibold tracking-normal text-white md:text-7xl">
            Structura AI
          </h1>
          <p className="mt-5 max-w-2xl text-2xl text-cyan-100">
            RealityScan production models with optional capture validation.
          </p>
          <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">
            Structura AI manages capture quality, external photogrammetry artifacts, and honest progress readiness for inspection, renovation, and construction workflows.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/projects/new" className="inline-flex items-center gap-2 rounded-md bg-brand px-5 py-3 font-semibold text-ink hover:bg-cyan-200">
              Start Scan Demo <ArrowRight size={18} />
            </Link>
            <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-md border border-white/10 px-5 py-3 text-slate-100 hover:bg-white/10">
              View Projects
            </Link>
          </div>
        </div>

        <div className="glass-panel rounded-lg p-5">
          <div className="rounded-lg border border-white/10 bg-slate-950/70 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">RealityScan model generation</p>
                <p className="text-xs text-slate-400">Primary client-quality production model workflow</p>
              </div>
              <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-200">Ready</span>
            </div>
            <div className="relative h-80 overflow-hidden rounded-lg border border-white/10 bg-[#0a1020]">
              <div className="absolute inset-x-10 bottom-10 h-28 skew-x-[-12deg] border border-cyan-300/40 bg-cyan-300/10" />
              <div className="absolute left-12 top-16 h-44 w-4 border border-slate-400/25 bg-slate-500/30" />
              <div className="absolute right-16 top-12 h-52 w-5 border border-slate-400/25 bg-slate-500/30" />
              <div className="absolute left-24 top-24 h-24 w-36 border border-brand/40 bg-brand/15" />
              <div className="absolute bottom-16 right-20 h-20 w-28 border border-violet-300/30 bg-violet-400/10" />
              <div className="absolute inset-0 bg-[linear-gradient(rgba(103,232,249,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(103,232,249,0.08)_1px,transparent_1px)] bg-[size:28px_28px]" />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl pb-14">
        <div className="grid gap-4 md:grid-cols-3">
          {featureCards.map(({ title, text, Icon }) => (
            <div key={title} className="glass-panel rounded-lg p-5">
              <Icon className="text-brand" size={22} />
              <h2 className="mt-4 font-semibold text-white">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl pb-16">
        <div className="glass-panel rounded-lg p-6">
          <div className="mb-6 flex items-center gap-3">
            <Cpu className="text-brand" size={22} />
            <div>
              <h2 className="text-xl font-semibold text-white">Reconstruction Pipeline</h2>
              <p className="text-sm text-slate-400">Structura uses external photogrammetry engines for client-quality geometry.</p>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-7">
            {pipeline.map((step, index) => (
              <div key={step} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                <p className="text-xs text-brand">0{index + 1}</p>
                <p className="mt-2 text-sm font-medium text-slate-100">{step}</p>
              </div>
            ))}
          </div>
          <p className="mt-5 text-sm text-slate-400">
            RealityScan generates the production model artifact. COLMAP can be used to validate image coverage and alignment quality before or after RealityScan.
          </p>
        </div>
      </section>
    </main>
  );
}
