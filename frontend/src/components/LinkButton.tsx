import { Link, type LinkProps } from 'react-router-dom'
import { useTheme } from './theme'

/** A router link that looks like the primary button. */
export function LinkButton({ className = '', ...rest }: LinkProps) {
  const theme = useTheme()
  return (
    <Link
      className={`inline-flex items-center justify-center rounded-md px-3.5 py-2 text-sm font-medium shadow-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 ${theme.primary} ${className}`}
      {...rest}
    />
  )
}