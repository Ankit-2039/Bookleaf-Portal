import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-stone-50 px-4 text-center">
      <p className="text-5xl font-semibold text-stone-300">404</p>
      <h1 className="text-lg font-medium text-stone-800">Page not found</h1>
      <Link to="/" className="text-sm font-medium text-emerald-700 hover:underline">Go to your home page</Link>
    </div>
  )
}