'use client';

import Link from 'next/link';
import { useAuth } from '../contexts/AuthContext';
import { useRouter } from 'next/navigation';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { user, logout, hasRole } = useAuth();
  const router = useRouter();

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', minRole: 'OBSERVER' },
    { name: 'API Explorer', href: '/api-demo', minRole: 'OBSERVER' },
    { name: 'API Docs', href: '/docs', minRole: 'OBSERVER' },
    { name: 'Home', href: '/', minRole: 'OBSERVER' },
    { name: 'Communications', href: '/comms', minRole: 'OBSERVER' },
    { name: 'Memory', href: '/memory', minRole: 'OBSERVER' },
    { name: 'Audit', href: '/audit', minRole: 'OBSERVER' },
    { name: 'Logs', href: '/logs', minRole: 'OBSERVER' },
    { name: 'Tools', href: '/tools', minRole: 'OBSERVER' },
    { name: 'System', href: '/system', minRole: 'OBSERVER' },
    { name: 'Config', href: '/config', minRole: 'ADMIN' },
    { name: 'Users', href: '/users', minRole: 'ADMIN' },
    { name: 'WA', href: '/wa', minRole: 'OBSERVER' }, // Will be filtered by the page itself based on ADMIN or AUTHORITY role
  ];

  const visibleNavigation = navigation.filter(item => hasRole(item.minRole));

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex flex-1 items-center">
              <div className="flex-shrink-0 flex items-center mr-8">
                <h1 className="text-xl font-bold">CIRIS GUI</h1>
              </div>
              <div className="flex-1 flex items-center justify-start overflow-x-auto">
                <div className="flex space-x-4">
                  {visibleNavigation.map((item) => (
                    <Link
                      key={item.name}
                      href={item.href}
                      className="whitespace-nowrap border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                    >
                      {item.name}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex items-center ml-4">
              {user && (
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-700 whitespace-nowrap">
                    {user.username || user.user_id} ({user.role})
                  </span>
                  <button
                    onClick={() => logout()}
                    className="text-sm text-gray-500 hover:text-gray-700 whitespace-nowrap"
                  >
                    Logout
                  </button>
                  {hasRole('SYSTEM_ADMIN') && (
                    <button
                      onClick={() => router.push('/emergency')}
                      className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700 whitespace-nowrap"
                    >
                      Emergency
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
      <main className="w-full py-6 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}