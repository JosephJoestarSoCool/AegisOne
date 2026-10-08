export const C = { gold: '#f5b03a', teal: '#2dd4bf', red: '#f87171', blue: '#60a5fa', violet: '#a78bfa', muted: '#8f9db8', line: '#26334f', card2: '#1a253d' }
export const axis = { stroke: C.muted, fontSize: 11, tickLine: false, axisLine: { stroke: C.line } }
export const TYPE_LABEL = {
  move_budget: 'Move budget', increase_budget: 'Increase budget', decrease_budget: 'Decrease budget',
  pause_campaign: 'Pause campaign', replace_creative: 'Replace creative',
}
export const KIND_TONE = {
  creative_fatigue: 'violet', auction_pressure: 'blue', competitor_price_pressure: 'gold', post_click_issue: 'red',
  margin_squeeze: 'red', stockout_risk: 'red', overstock_risk: 'gold',
}

/** Plain-language metric definitions, shown on hover, keyboard focus, or tap. */
export const GLOSS = {
  roas: 'Revenue generated per ₹1 of ad spend (average, all spend so far).',
  mroas: 'Revenue from the next ₹1 of spend. Falls as a campaign saturates.',
  ppr: 'Contribution profit from the next ₹1 after COGS and the ₹1 itself: marginal ROAS × margin − 1. This is what the engine ranks on.',
  value: 'Incremental profit per ₹1 plus the company’s policy weights: growth, inventory pressure, CAC and risk.',
  margin: 'Contribution margin per unit sold: (price − unit cost) ÷ price.',
  cac: 'Marginal CAC: ad spend needed to win one more order at today’s budget.',
  cvr: 'Share of clicks that become orders.',
  inv: 'Days of stock left at the current sell-through rate.',
  risk: 'Chance the SKU stocks out before replenishment, given lead time.',
  conf: 'How much to trust this estimate: elasticity fit quality, stock safety and ROAS stability.',
  health: 'Transparent 0–100 score blending profit, ROAS, conversion, inventory fit, creative freshness and stability.',
  budget: 'Daily budget before and after the recommended move.',
}

export const nameOf = (x) => `${x.sku_name} × ${x.platform}`

export const shortName = (n) => n.replace(' · ', ' ').replace('Lookalike 1%', 'LAL').replace('Interest-based', 'Interest').replace('Retargeting 30d', 'RT').replace(' · ', ' ')
export const fx = (n, d = 2) => '₹' + n.toFixed(d)

export const DIM_NOTE = {
  profitability: 'Weight on contribution profit after COGS and ad spend.',
  growth: 'Weight on acquiring new customers, valued at lifetime value.',
  revenue: 'Weight on top-line revenue.',
  inventory: 'Weight on moving stock that is piling up and protecting stock that is running out.',
  cac: 'Weight on keeping acquisition cost and ROAS inside their limits.',
  risk: 'Weight on avoiding volatile or flagged campaigns.',
}

/** Plain-language API failure message. Never shows response bodies or stack traces. */
export function errorText(error, what = 'this data') {
  if (error?.kind === 'http') return `The API returned an error (${error.status}) while loading ${what}.`
  return `Couldn’t reach the API while loading ${what}. The analysis service may be starting up or temporarily unavailable.`
}
