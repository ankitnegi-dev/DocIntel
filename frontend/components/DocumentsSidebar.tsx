'use client'
import { useEffect, useState, useCallback } from 'react'
import { FileText, Trash2, ChevronLeft, ChevronRight, RefreshCw, AlertCircle, Eye, RotateCcw } from 'lucide-react'
import { getDocuments, deleteDocument, DocumentMetadata, API_URL } from '@/lib/api'
import DocPreviewModal from './DocPreviewModal'

const TYPE_COLOURS: Record<string, string> = {
  invoice:   'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  financial: 'bg-blue-100  text-blue-700  dark:bg-blue-900  dark:text-blue-300',
  research:  'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300',
  medical:   'bg-red-100   text-red-700   dark:bg-red-900   dark:text-red-300',
  legal:     'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  contract:  'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  meeting:   'bg-teal-100  text-teal-700  dark:bg-teal-900  dark:text-teal-300',
  report:    'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300',
}

function typeColour(doc: DocumentMetadata): string {
  const dtype = (doc.classification?.document_type ?? '').toLowerCase()
  for (const [key, cls] of Object.entries(TYPE_COLOURS)) {
    if (dtype.includes(key)) return cls
  }
  return 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
}

function shortType(doc: DocumentMetadata): string {
  const dtype = doc.classification?.document_type ?? 'Unknown'
  return dtype.length > 16 ? dtype.slice(0, 14) + '…' : dtype
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

interface Props {
  isOpen: boolean
  onToggle: () => void
}

export default function DocumentsSidebar({ isOpen, onToggle }: Props) {
  const [docs, setDocs]           = useState<DocumentMetadata[]>([])
  const [loading, setLoading]     = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [reindexingId, setReindexingId] = useState<string | null>(null)
  const [previewDoc, setPreviewDoc] = useState<DocumentMetadata | null>(null)
  const [error, setError]         = useState<string | null>(null)

  const fetchDocs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getDocuments()
      setDocs(data.documents)
    } catch {
      setError('Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchDocs() }, [fetchDocs])

  const handleDelete = async (docId: string) => {
    setDeletingId(docId)
    try {
      await deleteDocument(docId)
      setDocs(prev => prev.filter(d => d.doc_id !== docId))
    } catch {
      setError('Delete failed - please try again')
    } finally {
      setDeletingId(null)
    }
  }

  const handleReindex = async (docId: string) => {
    setReindexingId(docId)
    try {
      await fetch(`${API_URL}/documents/${docId}/reindex`, { method: 'POST' })
      setTimeout(fetchDocs, 3000)  // Refresh after background task starts
    } catch {
      setError('Reindex failed')
    } finally {
      setReindexingId(null)
    }
  }

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={onToggle}
        className={`
          fixed top-[72px] z-40 flex items-center justify-center
          w-6 h-12 rounded-r-lg
          bg-white dark:bg-slate-800
          border border-l-0 border-slate-200 dark:border-slate-700
          text-slate-500 dark:text-slate-400
          hover:bg-slate-50 dark:hover:bg-slate-700
          shadow-sm transition-all duration-200
          ${isOpen ? 'left-64' : 'left-0'}
        `}
        aria-label={isOpen ? 'Close sidebar' : 'Open sidebar'}
      >
        {isOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
      </button>

      {/* Sidebar panel */}
      <aside className={`
        fixed top-14 left-0 bottom-0 z-30
        w-64 flex flex-col
        bg-white dark:bg-slate-900
        border-r border-slate-200 dark:border-slate-700
        shadow-md
        transition-transform duration-300
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Documents</h2>
            <p className="text-xs text-slate-400 dark:text-slate-500">{docs.length} indexed</p>
          </div>
          <button
            onClick={fetchDocs}
            disabled={loading}
            className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors disabled:opacity-40"
            aria-label="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {error && (
          <div className="mx-3 mt-2 flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 px-2 py-1.5 rounded-md">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Document list */}
        <div className="flex-1 overflow-y-auto py-2">
          {loading && docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-2">
              <RefreshCw className="w-5 h-5 animate-spin text-slate-400" />
              <p className="text-xs text-slate-400">Loading…</p>
            </div>
          ) : docs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-2 px-4 text-center">
              <FileText className="w-8 h-8 text-slate-300 dark:text-slate-600" />
              <p className="text-xs text-slate-400 dark:text-slate-500">No documents yet.<br />Upload some to get started.</p>
            </div>
          ) : (
            docs.map(doc => (
              <div
                key={doc.doc_id}
                className="group mx-2 mb-1 rounded-lg px-3 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="flex items-start gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <button
                        onClick={() => setPreviewDoc(doc)}
                        className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate leading-snug text-left hover:text-blue-600 dark:hover:text-blue-400 transition-colors w-full"
                        title={`Preview ${doc.original_filename}`}
                      >
                        {doc.original_filename}
                      </button>
                      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${typeColour(doc)}`}>
                          {shortType(doc)}
                        </span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">
                          {doc.page_count}p · {formatSize(doc.file_size)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => setPreviewDoc(doc)}
                      className="p-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/40 text-slate-400 hover:text-blue-500 transition-all"
                      title="Preview pages"
                    >
                      <Eye className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => handleReindex(doc.doc_id)}
                      disabled={reindexingId === doc.doc_id}
                      className="p-1 rounded hover:bg-amber-50 dark:hover:bg-amber-900/40 text-slate-400 hover:text-amber-500 transition-all disabled:opacity-40"
                      title="Re-index document"
                    >
                      {reindexingId === doc.doc_id
                        ? <RefreshCw className="w-3 h-3 animate-spin" />
                        : <RotateCcw className="w-3 h-3" />}
                    </button>
                    <button
                      onClick={() => handleDelete(doc.doc_id)}
                      disabled={deletingId === doc.doc_id}
                      className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/40 text-slate-400 hover:text-red-500 transition-all disabled:opacity-40"
                      title="Delete document"
                    >
                      {deletingId === doc.doc_id
                        ? <RefreshCw className="w-3 h-3 animate-spin" />
                        : <Trash2 className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                {doc.classification?.summary && (
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1.5 leading-relaxed line-clamp-2">
                    {doc.classification.summary}
                  </p>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 border-t border-slate-200 dark:border-slate-700">
          <a
            href="/upload"
            className="flex items-center justify-center gap-1.5 w-full text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors py-1"
          >
            + Upload new document
          </a>
        </div>
      </aside>

      {/* Doc preview modal */}
      {previewDoc && (
        <DocPreviewModal doc={previewDoc} onClose={() => setPreviewDoc(null)} />
      )}
    </>
  )
}