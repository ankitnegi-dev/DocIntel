'use client'
import Link from 'next/link'
import { Brain, FileText, Search, Layers, ArrowRight, Sparkles, Database, Zap, Shield } from 'lucide-react'

const FEATURES = [
  {
    icon: Layers,
    color: 'from-blue-500 to-blue-600',
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    border: 'border-blue-100 dark:border-blue-800',
    title: 'Intelligent Parsing',
    desc: 'Digital PDFs, scanned docs (OCR), and text files - tables extracted to markdown automatically.',
  },
  {
    icon: Brain,
    color: 'from-purple-500 to-purple-600',
    bg: 'bg-purple-50 dark:bg-purple-900/20',
    border: 'border-purple-100 dark:border-purple-800',
    title: 'Auto Classification',
    desc: 'Claude Haiku classifies every document - type, domain, sensitivity, entities, and a one-line summary.',
  },
  {
    icon: Search,
    color: 'from-emerald-500 to-emerald-600',
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    border: 'border-emerald-100 dark:border-emerald-800',
    title: 'Agentic RAG Q&A',
    desc: 'Ask anything. Answers stream in real-time with inline [Doc, Page N] citations and page thumbnails.',
  },
]

const STEPS = [
  { step: '01', icon: FileText, label: 'Upload', desc: 'Drop PDFs or text files - up to 20 MB each' },
  { step: '02', icon: Layers, label: 'Index', desc: 'Parsed, classified, embedded & stored in ChromaDB' },
  { step: '03', icon: Brain, label: 'Ask', desc: 'Natural-language Q&A with streamed, cited answers' },
]

const SAMPLE_QUERIES = [
  'What is the total amount on the invoice?',
  'Summarise the Q3 revenue report',
  'What are the contract termination clauses?',
  'Key findings from the research paper?',
]

const BADGES = [
  { icon: Zap,      label: 'Streaming SSE' },
  { icon: Shield,   label: 'No hallucinations' },
  { icon: Database, label: '24 chunks indexed' },
]

export default function HomePage() {
  const chatHref   = '/chat'
  const uploadHref = '/upload'

  return (
    <div className="min-h-screen bg-slate-950 overflow-hidden">
      {/* ── Decorative background blobs ── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl animate-blob" />
        <div className="absolute top-0 right-0 w-80 h-80 bg-purple-600/20 rounded-full blur-3xl animate-blob animation-delay-2000" />
        <div className="absolute bottom-20 left-1/3 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl animate-blob animation-delay-4000" />
        {/* Grid overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:48px_48px]" />
      </div>

      <div className="relative max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* ── Hero ── */}
        <section className="pt-20 pb-16 text-center">
          {/* Pill badge */}
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-medium px-4 py-1.5 rounded-full mb-8 animate-fade-in">
            <Sparkles className="w-3.5 h-3.5" />
            Agentic RAG · Claude Haiku · ChromaDB
          </div>

          <h1 className="text-5xl sm:text-6xl font-extrabold tracking-tight mb-5 animate-slide-up">
            <span className="text-white">Talk to your </span>
            <span className="bg-gradient-to-r from-blue-400 via-cyan-400 to-purple-400 bg-clip-text text-transparent">
              documents
            </span>
          </h1>

          <p className="text-slate-400 text-lg sm:text-xl max-w-2xl mx-auto leading-relaxed mb-10 animate-slide-up animation-delay-200">
            Upload PDFs and text files. Ask questions in plain English.
            Get streamed answers with exact page citations — grounded, never hallucinated.
          </p>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-10 animate-slide-up animation-delay-300">
            <Link
              href={chatHref}
              className="group flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-7 py-3.5 rounded-2xl shadow-lg shadow-blue-900/40 hover:shadow-blue-900/60 transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
            >
              <Brain className="w-5 h-5" />
              Start Chatting
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              href={uploadHref}
              className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-slate-200 font-semibold px-7 py-3.5 rounded-2xl transition-all duration-200 hover:-translate-y-0.5"
            >
              <Layers className="w-5 h-5 text-slate-400" />
              Upload Docs
            </Link>
          </div>

          {/* Stat badges */}
          <div className="flex flex-wrap items-center justify-center gap-3 animate-fade-in animation-delay-500">
            {BADGES.map(({ icon: Icon, label }) => (
              <span key={label} className="flex items-center gap-1.5 text-xs text-slate-400 bg-white/5 border border-white/10 px-3 py-1.5 rounded-full">
                <Icon className="w-3.5 h-3.5 text-blue-400" />
                {label}
              </span>
            ))}
          </div>
        </section>

        {/* ── Sample queries ticker ── */}
        <section className="mb-16 animate-fade-in animation-delay-500">
          <p className="text-center text-xs font-medium text-slate-500 uppercase tracking-widest mb-4">Try asking</p>
          <div className="flex flex-wrap justify-center gap-2">
            {SAMPLE_QUERIES.map((q, i) => (
              <Link
                key={i}
                href={chatHref}
                className="text-sm text-slate-300 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-blue-500/40 px-4 py-2 rounded-full transition-all duration-200 hover:-translate-y-0.5"
                style={{ animationDelay: `${i * 100}ms` }}
              >
                &ldquo;{q}&rdquo;
              </Link>
            ))}
          </div>
        </section>

        {/* ── Features ── */}
        <section className="mb-20">
          <h2 className="text-center text-sm font-semibold text-slate-500 uppercase tracking-widest mb-8">Capabilities</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {FEATURES.map(({ icon: Icon, color, bg, border, title, desc }, i) => (
              <div
                key={title}
                className={`${bg} border ${border} rounded-2xl p-6 hover:scale-[1.02] transition-transform duration-200 animate-card-in`}
                style={{ animationDelay: `${i * 120}ms` }}
              >
                <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center mb-4 shadow-lg`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <h3 className="font-semibold text-slate-200 mb-2">{title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="mb-20">
          <h2 className="text-center text-sm font-semibold text-slate-500 uppercase tracking-widest mb-10">How it works</h2>
          <div className="relative flex flex-col sm:flex-row gap-4 sm:gap-0">
            {/* Connector line */}
            <div className="hidden sm:block absolute top-8 left-[calc(16.6%+24px)] right-[calc(16.6%+24px)] h-px bg-gradient-to-r from-blue-500/0 via-blue-500/50 to-blue-500/0" />

            {STEPS.map(({ step, icon: Icon, label, desc }, i) => (
              <div key={step} className="flex-1 text-center px-4 animate-slide-up" style={{ animationDelay: `${i * 150}ms` }}>
                <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600/20 to-blue-500/10 border border-blue-500/20 mx-auto mb-3 shadow-md">
                  <Icon className="w-7 h-7 text-blue-400" />
                  <span className="absolute -top-2 -right-2 text-[10px] font-bold text-blue-300 bg-slate-950 border border-blue-500/30 px-1.5 rounded-full">
                    {step}
                  </span>
                </div>
                <h3 className="font-semibold text-slate-200 mb-1">{label}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Final CTA ── */}
        <section className="pb-20 text-center">
          <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-white/10 rounded-3xl p-10">
            <h2 className="text-2xl font-bold text-white mb-3">Ready to explore your documents?</h2>
            <p className="text-slate-400 mb-6 text-sm">6 sample documents are already indexed — no upload needed to try it out.</p>
            <Link
              href={chatHref}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-8 py-3 rounded-2xl shadow-lg shadow-blue-900/40 transition-all duration-200 hover:-translate-y-0.5"
            >
              <Brain className="w-5 h-5" />
              Try it now
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>

      </div>
    </div>
  )
}