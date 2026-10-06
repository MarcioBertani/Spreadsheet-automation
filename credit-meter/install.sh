#!/usr/bin/env bash
# Instala o mod credit-meter do Claude Code em ~/.claude/skills/credit-meter,
# pasta que o Claude Code carrega sozinho em toda sessão nova.
set -euo pipefail
DEST="${HOME}/.claude/skills/credit-meter"
mkdir -p "$DEST/.claude-plugin" "$DEST/hooks" "$DEST/types"
cat > "$DEST/.claude-plugin/plugin.json" <<'CREDIT_METER_EOF'
{ "name": "credit-meter", "version": "0.1.0", "description": "Barra em tempo real acima do prompt com o gasto de créditos: custo da sessão, custo do último prompt, contexto e limites de uso", "types": "./types/index.d.ts" }
CREDIT_METER_EOF
cat > "$DEST/hooks/hooks.json" <<'CREDIT_METER_EOF'
{ "modules": ["./register.tsx"] }
CREDIT_METER_EOF
cat > "$DEST/hooks/register.tsx" <<'CREDIT_METER_EOF'
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, SessionMeasureInput, SessionUsage } from 'claude-code'

import type { Limit, Meter } from '../types'

const meter = atom({ plugin: 'credit-meter', key: 'meter' } as const, null)
const isHidden = atom({ plugin: 'credit-meter', key: 'isHidden' } as const, false)

const LIMIT_NAMES: Record<string, string> = {
  five_hour: '5h',
  seven_day: '7 dias',
  spend_limit: 'gasto',
}

export const bar = (percent: number, width = 12): string => {
  const clamped = Math.max(0, Math.min(100, percent))
  const filled = Math.round((clamped / 100) * width)
  return '█'.repeat(filled) + '░'.repeat(width - filled)
}

export const usd = (value: number): string =>
  value < 0.01 && value > 0 ? '<$0.01' : `$${value.toFixed(2)}`

const tokens = (value: number): string =>
  value >= 1000 ? `${Math.round(value / 1000)}k` : String(value)

const colorFor = (percent: number) =>
  percent >= 90 ? 'error' : percent >= 70 ? 'warning' : 'success'

type Figures = Pick<SessionUsage, 'context' | 'rateLimits' | 'cost'> | SessionMeasureInput

async function refresh(
  $: EngineInterface,
  figures: Figures,
  usdAtPrompt: number | null,
  isRunning?: boolean,
) {
  const sessionUsd = figures.cost?.usd ?? null
  const limits: Limit[] = figures.rateLimits.map(l => ({
    kind: l.kind,
    percentUsed: l.percentUsed,
    resetsAt: l.resetsAt,
  }))

  await update($, meter, previous => ({
    sessionUsd,
    promptUsd:
      sessionUsd !== null && usdAtPrompt !== null
        ? Math.max(0, sessionUsd - usdAtPrompt)
        : (previous?.promptUsd ?? null),
    contextPercent: figures.context.percent ?? null,
    contextTokens: figures.context.tokens ?? null,
    contextWindow: figures.context.window,
    limits,
    isRunning: isRunning ?? previous?.isRunning ?? false,
  }))

  if (sessionUsd !== null) {
    $.ui.status(`💳 ${usd(sessionUsd)}`)
  }
}

export const register: Register = on => {
  // Cost total when the current prompt was sent; the module's own variable,
  // so a reload simply starts the per-prompt count over.
  let usdAtPrompt: number | null = null

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'credit-meter',
      description: 'Mostra ou esconde a barra de gasto de créditos',
    })
    const result = await next(e)
    await refresh($, await $.session.usage(), usdAtPrompt)
    return result
  })

  on('prompt.submit', async ($, e, next) => {
    // Never hold the prompt up over the meter.
    try {
      const usage = await $.session.usage()
      usdAtPrompt = usage.cost?.usd ?? 0
      await refresh($, usage, usdAtPrompt, true)
    } catch {
      // The bar just catches up at the next measurement.
    }
    return next(e)
  })

  // Pushed by the engine after each turn step and whenever a limit moves.
  on('session.measure', async ($, e, next) => {
    await refresh($, e, usdAtPrompt)
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    await refresh($, await $.session.usage(), usdAtPrompt, false)
    return result
  })

  on('command.run', { command: 'credit-meter' }, async ($, e) => {
    const hidden = await update($, isHidden, h => !h)
    return { text: hidden ? 'Barra de créditos escondida.' : 'Barra de créditos visível.' }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const m = await read($, meter)
    if (e.props.hasSurvey || m === null || (await read($, isHidden))) {
      return next(e)
    }

    const { Box, Text } = $.ui.resolve(e)

    return (
      <Box flexDirection="row" flexWrap="wrap" columnGap={2}>
        <Text>
          <Text bold color="claude">💳 Sessão {m.sessionUsd === null ? '—' : usd(m.sessionUsd)}</Text>
          {m.promptUsd !== null ? (
            <Text dimColor>
              {' '}({m.isRunning ? 'este prompt' : 'último prompt'}: +{usd(m.promptUsd)})
            </Text>
          ) : null}
        </Text>
        {m.contextPercent !== null ? (
          <Text>
            <Text dimColor>Contexto </Text>
            <Text color={colorFor(m.contextPercent)}>{bar(m.contextPercent, 10)}</Text>
            <Text dimColor>
              {' '}{m.contextPercent}%
              {m.contextTokens !== null ? ` (${tokens(m.contextTokens)}/${tokens(m.contextWindow)})` : ''}
            </Text>
          </Text>
        ) : null}
        {m.limits.map(l => (
          <Text key={l.kind}>
            <Text dimColor>Limite {LIMIT_NAMES[l.kind] ?? l.kind} </Text>
            <Text color={colorFor(l.percentUsed)}>{bar(l.percentUsed, 10)}</Text>
            <Text dimColor> {l.percentUsed}%</Text>
          </Text>
        ))}
      </Box>
    )
  })
}
CREDIT_METER_EOF
cat > "$DEST/types/index.d.ts" <<'CREDIT_METER_EOF'
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
CREDIT_METER_EOF
echo "credit-meter instalado em $DEST. Abra uma nova sessão do Claude Code."
