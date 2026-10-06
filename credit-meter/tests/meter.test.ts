import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

// Stand in for the engine beneath the plugin.
const engine = (on: On) => {
  on('session.measure', (_$, e) => ({ changed: e.changed }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.render', () => ({ type: 'Box', props: {}, children: [] }))
}

const BAND = {
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 120,
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

const measure = (usd: number) => ({
  context: { tokens: 50_000, window: 200_000, percent: 25 },
  rateLimits: [{ kind: 'five_hour', percentUsed: 42 }],
  cost: { usd },
  changed: ['cost' as const],
})

test('the band shows session cost, context and limits on every surface', async ($, on) => {
  engine(on)
  await $.session.measure(measure(1.234))

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'credit-meter', surface, ...BAND })
    expect(await ui.find({ type: 'Text', text: /Sessão \$1\.23/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /25%/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /Limite 5h/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /42%/ })).toBeDefined()
    await ui.unmount()
  }
})

test('the band is empty before any measurement', async ($, on) => {
  engine(on)
  const ui = await $.ui.mount({ plugin: 'credit-meter', surface: 'terminal', ...BAND })
  expect(await ui.find({ type: 'Text', text: /Sessão/ })).toBeUndefined()
  await ui.unmount()
})
