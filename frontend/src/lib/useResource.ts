import { useCallback, useEffect, useRef, useState } from 'react'
import { toApiError, type ApiError } from './api'

interface State<T> { key: string | null; data: T | null; error: ApiError | null }

/**
 * Fetch data for `key`. Changing the key refetches (loading=true); reload() refetches silently
 * (no spinner), which is what live updates use. While `loading` is true, `data` may still belong
 * to the previous key, so pages should show a spinner when loading.
 */
export function useResource<T>(key: string, fetcher: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null })
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    const ctrl = new AbortController()
    fetcherRef.current(ctrl.signal).then(
      (data) => setState({ key, data, error: null }),
      (err: unknown) => {
        if (ctrl.signal.aborted) return
        setState((s) => ({ key, data: s.data, error: toApiError(err) }))
      },
    )
    return () => ctrl.abort()
  }, [key, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  const settled = state.key === key
  return { data: state.data, error: settled ? state.error : null, loading: !settled, reload }
}