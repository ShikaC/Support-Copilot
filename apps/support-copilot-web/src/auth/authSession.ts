import * as z from 'zod'

const ACCESS_TOKEN_KEY = 'support-copilot.access-token'
const accessTokenSchema = z.string().min(16).max(8192).regex(/^[\x21-\x7E]+$/)

export type AuthMode = 'demo' | 'secured'
export type AuthState =
  | { readonly mode: 'demo'; readonly status: 'demo' }
  | { readonly mode: 'secured'; readonly status: 'authenticated' | 'unauthenticated' }

export interface AuthSession {
  readonly mode: AuthMode
  state(): AuthState
  accessToken(): string | null
  setAccessToken(value: string): void
  clearAccessToken(): void
}

type AuthSessionOptions = { readonly mode: AuthMode; readonly storage?: Storage }

function browserSessionStorage(): Storage | undefined {
  return typeof window === 'undefined' ? undefined : window.sessionStorage
}

export function createAuthSession(options: AuthSessionOptions): AuthSession {
  const storage = options.storage ?? browserSessionStorage()
  let memoryToken: string | null =
    options.mode === 'secured' ? storage?.getItem(ACCESS_TOKEN_KEY) ?? null : null

  return {
    mode: options.mode,
    state() {
      if (options.mode === 'demo') return { mode: 'demo', status: 'demo' }
      return { mode: 'secured', status: memoryToken === null ? 'unauthenticated' : 'authenticated' }
    },
    accessToken() {
      return options.mode === 'secured' ? memoryToken : null
    },
    setAccessToken(value) {
      if (options.mode === 'demo') return
      const token = accessTokenSchema.parse(value)
      memoryToken = token
      storage?.setItem(ACCESS_TOKEN_KEY, token)
    },
    clearAccessToken() {
      memoryToken = null
      storage?.removeItem(ACCESS_TOKEN_KEY)
    },
  }
}

export function configuredAuthMode(): AuthMode {
  return import.meta.env.VITE_AUTH_MODE === 'secured' ? 'secured' : 'demo'
}
