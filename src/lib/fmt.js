export function fmt(n) {
  return '$' + (+n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function fmtShort(n) {
  if (n >= 1000) return '$' + (n / 1000).toFixed(1) + 'k'
  return '$' + Math.round(n)
}

export function relDate(iso) {
  if (!iso) return '—'
  const diff = Math.round((new Date(iso) - new Date()) / 86400000)
  if (diff < -1)  return `${Math.abs(diff)}d overdue`
  if (diff === -1) return 'Yesterday'
  if (diff === 0)  return 'Today'
  if (diff === 1)  return 'Tomorrow'
  if (diff <= 7)   return `${diff}d`
  return iso
}
