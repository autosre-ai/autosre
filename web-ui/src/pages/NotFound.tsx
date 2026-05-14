import { Link } from 'react-router-dom';
import { 
  ExclamationTriangleIcon,
  HomeIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline';

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="text-center max-w-md">
        {/* Icon */}
        <div className="inline-flex items-center justify-center w-20 h-20 bg-amber-100 dark:bg-amber-900/30 rounded-full mb-6">
          <ExclamationTriangleIcon className="w-10 h-10 text-amber-600 dark:text-amber-400" />
        </div>

        {/* Error Code */}
        <h1 className="text-7xl font-bold text-stone-200 dark:text-stone-700 mb-2">
          404
        </h1>

        {/* Title */}
        <h2 className="text-2xl font-semibold text-stone-900 dark:text-stone-100 mb-3">
          Page Not Found
        </h2>

        {/* Description */}
        <p className="text-stone-500 dark:text-stone-400 mb-8">
          The page you're looking for doesn't exist or has been moved. 
          This might be a misconfigured route or an old bookmark.
        </p>

        {/* SRE Humor */}
        <div className="bg-stone-100 dark:bg-stone-800 rounded-lg p-4 mb-8 text-sm text-stone-600 dark:text-stone-400 font-mono">
          <span className="text-red-500">ERROR:</span> Route not found in service mesh.
          <br />
          <span className="text-stone-400">Suggestion:</span> Check your ingress config.
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 transition-colors"
          >
            <HomeIcon className="w-4 h-4" />
            Go to Dashboard
          </Link>
          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-medium text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-800 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 transition-colors"
          >
            <ArrowLeftIcon className="w-4 h-4" />
            Go Back
          </button>
        </div>

        {/* Help Links */}
        <div className="mt-12 pt-8 border-t border-stone-200 dark:border-stone-700">
          <p className="text-sm text-stone-500 dark:text-stone-400 mb-3">
            Looking for something specific?
          </p>
          <div className="flex flex-wrap gap-4 justify-center text-sm">
            <Link
              to="/alerts"
              className="text-amber-600 dark:text-amber-400 hover:underline"
            >
              View Alerts
            </Link>
            <Link
              to="/investigations"
              className="text-amber-600 dark:text-amber-400 hover:underline"
            >
              Investigations
            </Link>
            <Link
              to="/chat"
              className="text-amber-600 dark:text-amber-400 hover:underline"
            >
              AI Chat
            </Link>
            <Link
              to="/settings"
              className="text-amber-600 dark:text-amber-400 hover:underline"
            >
              Settings
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
