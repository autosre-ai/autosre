import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';

export function Layout() {
  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-900">
      <Sidebar />
      <main className="lg:pl-64 min-h-screen transition-all duration-200">
        <Outlet />
      </main>
    </div>
  );
}
