import { NextRequest, NextResponse } from 'next/server'

export const config = {
  matcher: ['/((?!_next|api|favicon\\.ico|.*\\..*).*)', '/'],
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (pathname.startsWith('/quality-console') || pathname.startsWith('/admin')) return NextResponse.next()

  // Already on /ru subtree — never redirect (prevents loop)
  if (pathname.startsWith('/ru')) return NextResponse.next()

  // 1. Respect user's explicit locale cookie (set by language switcher)
  const cookie = req.cookies.get('damiworks_locale')?.value
  if (cookie === 'en') return NextResponse.next()
  if (cookie === 'ru') return NextResponse.redirect(new URL('/ru', req.url))

  // 2. Accept-Language: ru or kk → /ru
  const primary = (req.headers.get('accept-language') ?? '')
    .split(',')[0]
    .split(';')[0]
    .trim()
    .toLowerCase()

  if (primary.startsWith('ru') || primary.startsWith('kk')) {
    return NextResponse.redirect(new URL('/ru', req.url))
  }

  // 3. Country=KZ only when Accept-Language doesn't express English preference
  // (avoids redirecting English-browser users who happen to be in Kazakhstan)
  const country = req.headers.get('x-vercel-ip-country')
  if (country === 'KZ' && !primary.startsWith('en')) {
    return NextResponse.redirect(new URL('/ru', req.url))
  }

  return NextResponse.next()
}
