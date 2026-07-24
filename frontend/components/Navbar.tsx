'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { getDocuments } from '@/lib/api'
import { FileText, Upload, Brain, Database, Sun, Moon, LogOut, User as UserIcon } from 'lucide-react'
import { useTheme } from './ThemeProvider'
import { useAuth } from '@/context/AuthContext'

export default function Navbar() {
  const pathname  = usePathname()
  const router = useRouter()
  const [docCount, setDocCount] = useState<number>(0)
  const { theme, toggle } = useTheme()
  const { user, logout, isLoading } = useAuth()

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const data = await getDocuments()
        setDocCount(data.total)
      } catch {
        // Ignore errors - backend may not be ready
      }
    }
    fetchCount()
    const interval = setInterval(fetchCount, 10000)
    return () => clearInterval(interval)
  }, [user])

  const handleLogout = () => {
    logout()
    router.push('/chat')
  }

  const navLinks = [
    { href: '/chat', label: 'Chat', icon: Brain },
    { href: '/upload', label: 'Upload', icon: Upload },
  ]

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link href={'/chat'} className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
            <FileText className="w-5 h-5 text-blue-500" />
            <span>DocIntel</span>
            <span className="hidden sm:block text-xs font-normal text-slate-400 dark:text-slate-500 ml-1">
              AI Document Intelligence
            </span>
          </Link>

          {/* Nav Links + controls */}
          <div className="flex items-center gap-1">
            {navLinks.map(({ href, label, icon: Icon }) => {
              const isActive = pathname.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300'
                      : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </Link>
              )
            })}

            {/* Document count badge */}
            <div className="flex items-center gap-1.5 ml-2 px-2.5 py-1 bg-slate-100 dark:bg-slate-800 rounded-full text-xs text-slate-500 dark:text-slate-400">
              <Database className="w-3 h-3" />
              <span>{docCount} doc{docCount !== 1 ? 's' : ''}</span>
            </div>

            {/* Auth state */}
            {!isLoading && (
              user ? (
                <div className="flex items-center gap-2 ml-2">
                  <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 dark:bg-slate-800 rounded-full text-xs text-slate-600 dark:text-slate-300">
                    <UserIcon className="w-3 h-3" />
                    <span className="max-w-[140px] truncate">{user.email}</span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-red-600 dark:hover:text-red-400 transition-all"
                  >
                    <LogOut className="w-4 h-4" />
                    <span className="hidden sm:inline">Logout</span>
                  </button>
                </div>
              ) : (
                <Link
                  href="/login"
                  className="ml-2 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-all"
                >
                  <UserIcon className="w-4 h-4" />
                  Login
                </Link>
              )
            )}

            {/* Dark mode toggle */}
            <button
              onClick={toggle}
              className="ml-1 p-2 rounded-md text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200 transition-all"
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? (
                <Moon className="w-4 h-4" />
              ) : (
                <Sun className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}