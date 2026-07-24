'use client'
import { useState, useCallback } from 'react'
import Link from 'next/link'
import UploadZone from '@/components/UploadZone'
import FileProgress, { FileItem } from '@/components/FileProgress'
import { uploadDocument, getProcessingStatus, getDocumentById } from '@/lib/api'
import { Layers, CheckCircle2, AlertCircle, Trash2, LogIn } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const POLL_INTERVAL = 2000 // 2 seconds

export default function UploadPage() {
  const { user, isLoading } = useAuth()
  const [files, setFiles] = useState<FileItem[]>([])
  const [isUploading, setIsUploading] = useState(false)

  // Poll a doc's processing status until terminal state
  const pollStatus = useCallback((fileId: string, docId: string) => {
    const interval = setInterval(async () => {
      try {
        const data = await getProcessingStatus(docId)
        const terminalStatuses = ['indexed', 'error']

        setFiles(prev => prev.map(f => {
          if (f.id !== fileId) return f
          return {
            ...f,
            status: data.status as FileItem['status'],
            message: data.message,
            error: data.error,
            docId: data.doc_id,
          }
        }))

        if (terminalStatuses.includes(data.status)) {
          clearInterval(interval)
          // Fetch full metadata to show auto-summary
          if (data.status === 'indexed' && data.doc_id) {
            getDocumentById(data.doc_id).then(meta => {
              setFiles(prev => prev.map(f => {
                if (f.id !== fileId) return f
                return {
                  ...f,
                  summary: meta.classification?.summary,
                  keyEntities: meta.classification?.key_entities,
                  documentType: meta.classification?.document_type,
                }
              }))
            }).catch(() => {})
          }
        }
      } catch {
        clearInterval(interval)
        setFiles(prev => prev.map(f =>
          f.id === fileId ? { ...f, status: 'error', error: 'Failed to poll status' } : f
        ))
      }
    }, POLL_INTERVAL)

    // Safety: max 5 minutes
    setTimeout(() => clearInterval(interval), 5 * 60 * 1000)
  }, [])

  // Process a single file: upload → get docId → poll
  const processFile = useCallback(async (fileItem: FileItem) => {
    try {
      // Uploading
      setFiles(prev => prev.map(f =>
        f.id === fileItem.id ? { ...f, status: 'uploading', progress: 10 } : f
      ))

      const data = await uploadDocument(fileItem.file, (progress) => {
        setFiles(prev => prev.map(f =>
          f.id === fileItem.id ? { ...f, progress: Math.min(progress * 0.15, 15) } : f
        ))
      })

      // Got docId → start polling
      setFiles(prev => prev.map(f =>
        f.id === fileItem.id ? { ...f, status: 'parsing', docId: data.doc_id, progress: 20 } : f
      ))
      pollStatus(fileItem.id, data.doc_id)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      setFiles(prev => prev.map(f =>
        f.id === fileItem.id ? { ...f, status: 'error', error: message } : f
      ))
    }
  }, [pollStatus])

  const handleFilesSelected = useCallback((newFiles: File[]) => {
    const items: FileItem[] = newFiles.map(file => ({
      id: crypto.randomUUID(),
      file,
      status: 'queued',
      progress: 0,
    }))

    setFiles(prev => [...prev, ...items])
    setIsUploading(true)

    // Process all files concurrently
    Promise.allSettled(items.map(item => processFile(item))).then(() => {
      setIsUploading(false)
    })
  }, [processFile])

  const handleRetry = useCallback((id: string) => {
    const item = files.find(f => f.id === id)
    if (!item) return
    // Reset to queued, then reprocess
    setFiles(prev => prev.map(f =>
      f.id === id ? { ...f, status: 'queued', progress: 0, error: undefined, message: undefined } : f
    ))
    processFile({ ...item, status: 'queued', progress: 0, error: undefined, message: undefined })
  }, [files, processFile])

  const handleRemove = useCallback((id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id))
  }, [])

  const handleClearAll = useCallback(() => {
    setFiles(prev => prev.filter(f =>
      !['indexed', 'error'].includes(f.status)
    ))
  }, [])

  const indexedCount = files.filter(f => f.status === 'indexed').length
  const errorCount = files.filter(f => f.status === 'error').length
  const activeCount = files.filter(f => ['uploading', 'parsing', 'classifying', 'indexing'].includes(f.status)).length
  const doneCount = files.filter(f => ['indexed', 'error'].includes(f.status)).length

  // Wait for auth state to resolve before deciding what to show
  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center text-slate-400">
        Loading...
      </div>
    )
  }

  // Not logged in - show login prompt instead of the upload UI
  if (!user) {
    return (
      <div className="max-w-md mx-auto px-4 py-16 text-center">
        <div className="w-14 h-14 rounded-xl bg-blue-100 flex items-center justify-center mx-auto mb-4">
          <Layers className="w-7 h-7 text-blue-600" />
        </div>
        <h1 className="text-xl font-bold text-slate-800 dark:text-white mb-2">
          Log in to upload documents
        </h1>
        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">
          Uploaded documents are private to your account. You can still ask questions
          about the public demo documents from the Chat page without logging in.
        </p>
        <Link
          href="/login"
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors"
        >
          <LogIn className="w-4 h-4" />
          Log in
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
            <Layers className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Document Upload</h1>
            <p className="text-slate-400 text-sm">Upload PDFs and text files for AI-powered analysis</p>
          </div>
        </div>
      </div>

      {/* Stats bar (if any files) */}
      {files.length > 0 && (
        <div className="flex items-center gap-4 mb-6 p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-1.5 text-sm">
            <span className="text-slate-500">Total:</span>
            <span className="font-semibold text-slate-800">{files.length}</span>
          </div>
          {indexedCount > 0 && (
            <div className="flex items-center gap-1.5 text-sm">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <span className="text-green-700 font-medium">{indexedCount} indexed</span>
            </div>
          )}
          {errorCount > 0 && (
            <div className="flex items-center gap-1.5 text-sm">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span className="text-red-600 font-medium">{errorCount} failed</span>
            </div>
          )}
          {activeCount > 0 && (
            <div className="flex items-center gap-1.5 text-sm">
              <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              <span className="text-blue-600 font-medium">{activeCount} processing</span>
            </div>
          )}
          {doneCount > 0 && (
            <button
              onClick={handleClearAll}
              className="ml-auto flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear done
            </button>
          )}
        </div>
      )}

      {/* Upload zone */}
      <UploadZone
        onFilesSelected={handleFilesSelected}
        disabled={isUploading && activeCount > 5}
      />

      {/* File progress list */}
      <FileProgress
        files={files}
        onRetry={handleRetry}
        onRemove={handleRemove}
      />

      {/* Tips */}
      {files.length === 0 && (
        <div className="mt-8 p-5 bg-blue-50 border border-blue-100 rounded-xl">
          <p className="text-sm font-semibold text-blue-800 mb-3">📋 Supported documents</p>
          <ul className="space-y-1.5 text-sm text-blue-700">
            <li>• <span className="font-medium">PDF</span> - invoices, reports, research papers, contracts (digital or scanned)</li>
            <li>• <span className="font-medium">TXT</span> - meeting notes, plain-text documents</li>
          </ul>
          <p className="text-xs text-blue-500 mt-3">
            Documents are automatically parsed, classified, and indexed for AI-powered Q&A.
            Table data and scanned pages are handled via OCR.
          </p>
        </div>
      )}
    </div>
  )
}