import { useCallback, useEffect, useRef, useState } from 'react'
import { toApiError, type ApiError } from './api'

interface State<T> { key: string | null; data: T | null; error: ApiError | null }

/**
 * Fetch data for `key`. Changing the key refetches (loading=true); reload() refetches silently
 * (no spinner), which is what live updates use. While `loading` is true, `data` may still belong
 * to the previous key (so lists can keep showing old rows while typing). A failed silent reload
 * keeps the current data and sets `error`; a failed fetch for a NEW key drops the old data.
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
        setState((s) => ({ key, data: s.key === key ? s.data : null, error: toApiError(err) }))
      },
    )
    return () => ctrl.abort()
  }, [key, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  const settled = state.key === key
  return { data: state.data, error: settled ? state.error : null, loading: !settled, reload }
}