export type Limit = { kind: string; percentUsed: number; resetsAt?: string }

export type Meter = {
  sessionUsd: number | null
  promptUsd: number | null
  contextPercent: number | null
  contextTokens: number | null
  contextWindow: number
  limits: Limit[]
  isRunning: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'credit-meter': { meter: Meter | null; isHidden: boolean }
  }
}
