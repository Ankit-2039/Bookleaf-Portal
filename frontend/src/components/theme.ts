import { createContext, useContext } from 'react'

export interface Theme {
  name: 'author' | 'admin'
  primary: string
  link: string
  focus: string
  sidebar: string
  sidebarBorder: string
  sidebarMuted: string
  brand: string
  navIdle: string
  navActive: string
}

// Class strings are written out in full so Tailwind can see them.
export const authorTheme: Theme = {
  name: 'author',
  primary: 'bg-emerald-700 text-white hover:bg-emerald-800 focus-visible:outline-emerald-700',
  link: 'text-emerald-700 hover:text-emerald-900',
  focus: 'focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/25',
  sidebar: 'bg-white text-stone-800',
  sidebarBorder: 'border-stone-200',
  sidebarMuted: 'text-stone-500',
  brand: 'text-emerald-800',
  navIdle: 'text-stone-600 hover:bg-stone-100 hover:text-stone-900',
  navActive: 'bg-emerald-50 text-emerald-800',
}

export const adminTheme: Theme = {
  name: 'admin',
  primary: 'bg-indigo-600 text-white hover:bg-indigo-700 focus-visible:outline-indigo-600',
  link: 'text-indigo-600 hover:text-indigo-800',
  focus: 'focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/25',
  sidebar: 'bg-slate-900 text-slate-100',
  sidebarBorder: 'border-slate-800',
  sidebarMuted: 'text-slate-400',
  brand: 'text-white',
  navIdle: 'text-slate-300 hover:bg-slate-800 hover:text-white',
  navActive: 'bg-slate-700 text-white',
}

export const ThemeContext = createContext<Theme>(authorTheme)
export const useTheme = () => useContext(ThemeContext)