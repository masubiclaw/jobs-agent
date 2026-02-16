import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import {
  Home,
  User,
  Briefcase,
  FileText,
  Settings,
  LogOut,
  Star,
  Plus,
  Shield,
  Workflow,
  Menu,
  X,
} from 'lucide-react'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/', icon: Home, label: 'Dashboard' },
    { to: '/profiles', icon: User, label: 'Profiles' },
    { to: '/jobs', icon: Briefcase, label: 'Jobs' },
    { to: '/jobs/top', icon: Star, label: 'Top Matches' },
    { to: '/jobs/add', icon: Plus, label: 'Add Job' },
    { to: '/documents', icon: FileText, label: 'Documents' },
  ]

  const adminItems = user?.is_admin ? [
    { to: '/admin', icon: Shield, label: 'Admin' },
    { to: '/admin/pipeline', icon: Workflow, label: 'Auto-Match' },
    { to: '/admin/scraper', icon: Settings, label: 'System Tools' },
    { to: '/admin/jobs', icon: Briefcase, label: 'All Jobs' },
  ] : []

  const closeSidebar = () => setSidebarOpen(false)

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="p-6 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-primary-600">Jobs Agent</h1>
          <p className="text-sm text-gray-500">Find Your Next Role</p>
        </div>
        <button
          onClick={closeSidebar}
          className="md:hidden p-1 text-gray-400 hover:text-gray-600"
        >
          <X size={20} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={closeSidebar}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-600 hover:bg-gray-50'
              }`
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}

        {adminItems.length > 0 && (
          <>
            <div className="pt-4 pb-2">
              <span className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Admin
              </span>
            </div>
            {adminItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                onClick={closeSidebar}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`
                }
              >
                <Icon size={20} />
                <span>{label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* User section */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
            <User size={20} className="text-primary-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {user?.name}
            </p>
            <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
        >
          <LogOut size={18} />
          <span>Sign out</span>
        </button>
      </div>
    </>
  )

  return (
    <div className="min-h-screen flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar — hidden on mobile, shown on md+ */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 flex flex-col
        transform transition-transform duration-200 ease-in-out
        md:relative md:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {sidebarContent}
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        {/* Mobile header */}
        <div className="md:hidden flex items-center gap-3 p-4 border-b border-gray-200 bg-white sticky top-0 z-30">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            <Menu size={22} />
          </button>
          <h1 className="text-lg font-bold text-primary-600">Jobs Agent</h1>
        </div>

        <div className="p-4 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
