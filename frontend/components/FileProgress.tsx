'use client'
import { useEffect, useRef, useState } from 'react'
import { CheckCircle, XCircle, Loader2, FileText, RefreshCw, X, ChevronDown, Tag } from 'lucide-react'

export interface FileItem {
  id: string
  file: File
  status: 'queued' | 'uploading' | 'parsing' | 'classifying' | 'indexing' | 'indexed' | 'error'
  progress: number
  message?: string
  error?: string
  docId?: string
  summary?: string          // Auto-generated summary from classification
  keyEntities?: string[]    // Key entities extracted during classification
  documentType?: string     // Document type label
}

interface FileProgressProps {
  files: FileItem[]
  onRetry: (id: string) => void
  onRemove: (id: string) => void
}

// Statuses that mean "actively being handled, no granular stage available".
// Processing runs in a separate background worker (not the API process), so
// fine-grained live stages (parsing/classifying/indexing %) aren't tracked
// here -- only queued -> indexed/error. We show elapsed time instead of a
// fake stepper so the wait is honest rather than misleading.
const ACTIVE_STATUSES = ['uploading', 'queued', 'parsing', 'classifying', 'indexing']

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

// Circular ring progress. Indeterminate (spinning quarter-arc) while active
// with no known percentage; solid ring on done/error.
function RingProgress({ active, done, error }: { active: boolean; done: boolean; error: boolean }) {
  const r = 16
  const circ = 2 * Math.PI * r
  const arc = circ * 0.25 // quarter-circle arc for the spinner look

  return (
    <div className={active ? 'animate-spin' : ''} style={{ width: 44, height: 44 }}>
      <svg width="44" height="44" className="flex-shrink-0 -rotate-90">
        <circle cx="22" cy="22" r={r} fill="none" strokeWidth="3"
          className="stroke-slate-200 dark:stroke-slate-700" />
        <circle cx="22" cy="22" r={r} fill="none" strokeWidth="3"
          strokeLinecap="round"
          style={{
            strokeDasharray: active ? `${arc} ${circ}` : circ,
            strokeDashoffset: error ? 0 : done ? 0 : active ? 0 : circ,
            transition: 'stroke-dashoffset 0.5s ease',
          }}
          className={
            error ? 'stroke-red-400' :
            done  ? 'stroke-emerald-500' :
            active ? 'stroke-blue-500' :
            'stroke-slate-300 dark:stroke-slate-600'
          }
        />
      </svg>
    </div>
  )
}

function SummaryCard({ item }: { item: FileItem }) {
  const [expanded, setExpanded] = useState(false)
  if (!item.summary) return null

  return (
    <div className="mt-2.5 rounded-xl border border-emerald-100 dark:border-emerald-900/50 bg-emerald-50 dark:bg-emerald-950/30 overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between px-3 py-2 text-left"
      >
        <div className="flex items-center gap-1.5">
          <Tag className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
          <span className="text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
            Auto-Summary
          </span>
          {item.documentType && (
            <span className="text-[9px] bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.5 rounded-full font-medium">
              {item.documentType}
            </span>
          )}
        </div>
        <ChevronDown className={`w-3 h-3 text-emerald-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>
      {expanded && (
        <div className="px-3 pb-3">
          <p className="text-xs text-emerald-800 dark:text-emerald-300 leading-relaxed">
            {item.summary}
          </p>
          {item.keyEntities && item.keyEntities.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {item.keyEntities.slice(0, 6).map((entity, i) => (
                <span
                  key={i}
                  className="text-[9px] bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 px-1.5 py-0.5 rounded-full"
                >
                  {entity}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function FileProgress({ files, onRetry, onRemove }: FileProgressProps) {
  // Track when each file entered an "active" state so we can show real
  // elapsed time instead of a fake progress percentage.
  const startTimes = useRef<Record<string, number>>({})
  const [, tick] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => tick(t => t + 1), 1000)
    return () => clearInterval(interval)
  }, [])

  if (files.length === 0) return null

  return (
    <div className="mt-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Processing Queue
          <span className="ml-2 text-xs font-normal text-slate-400">{files.length} file{files.length !== 1 ? 's' : ''}</span>
        </h3>
        <div className="flex gap-3 text-xs">
          <span className="text-emerald-600 dark:text-emerald-400 font-medium">
            {files.filter(f => f.status === 'indexed').length} indexed
          </span>
          {files.filter(f => f.status === 'error').length > 0 && (
            <span className="text-red-500 font-medium">
              {files.filter(f => f.status === 'error').length} failed
            </span>
          )}
        </div>
      </div>

      {files.map((item, fileIdx) => {
        const isActive = ACTIVE_STATUSES.includes(item.status)
        const isDone = item.status === 'indexed'
        const isError = item.status === 'error'

        if (isActive && !startTimes.current[item.id]) {
          startTimes.current[item.id] = Date.now()
        }
        const elapsedSec = startTimes.current[item.id]
          ? Math.max(0, Math.floor((Date.now() - startTimes.current[item.id]) / 1000))
          : 0

        return (
          <div
            key={item.id}
            className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-4 shadow-sm animate-message-in"
            style={{ animationDelay: `${fileIdx * 60}ms` }}
          >
            <div className="flex items-start gap-3">
              <RingProgress active={isActive} done={isDone} error={isError} />

              <div className="flex-1 min-w-0">
                {/* Filename + actions */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">{item.file.name}</p>
                    <span className="text-xs text-slate-400 flex-shrink-0">{formatFileSize(item.file.size)}</span>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {isError && (
                      <button onClick={() => onRetry(item.id)}
                        className="p-1 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded text-slate-400 hover:text-blue-600 transition-colors"
                        title="Retry">
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {(isDone || isError) && (
                      <button onClick={() => onRemove(item.id)}
                        className="p-1 hover:bg-red-50 dark:hover:bg-red-900/30 rounded text-slate-300 hover:text-red-500 transition-colors"
                        title="Remove">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Active / processing state — honest elapsed time, no fake stepper */}
                {isActive && (
                  <div className="flex items-center gap-1.5 text-xs text-blue-500 dark:text-blue-400">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>
                      Processing document{elapsedSec > 3 ? ` — ${formatElapsed(elapsedSec)} elapsed` : '…'}
                    </span>
                  </div>
                )}
                {isActive && elapsedSec > 20 && (
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                    Larger or scanned documents can take a few minutes — parsing, classifying, and indexing happen in the background.
                  </p>
                )}

                {/* Error state */}
                {isError && (
                  <div className="flex items-center gap-1.5 text-xs text-red-500 mt-1">
                    <XCircle className="w-3.5 h-3.5" />
                    {item.error || 'Upload failed'}
                  </div>
                )}

                {/* Status message */}
                {item.message && !isError && !isActive && (
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{item.message}</p>
                )}

                {/* Done badge */}
                {isDone && (
                  <div className="flex items-center gap-1 mt-1">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      Successfully indexed - ready to chat
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Auto-summary card (shown after indexing) */}
            {isDone && <SummaryCard item={item} />}
          </div>
        )
      })}
    </div>
  )
}