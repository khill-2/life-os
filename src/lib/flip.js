const CH = '0123456789'

export function flipReveal(el, target, ms) {
  if (!el) return
  const frames = Math.floor((ms || 500) / 55)
  let f = 0
  const digits = (target.match(/\d/g) || []).length
  clearInterval(el._flip)
  el._flip = setInterval(() => {
    f++
    if (f >= frames) { el.textContent = target; clearInterval(el._flip); return }
    let i = 0
    el.textContent = target.replace(/\d/g, d =>
      (f / frames) > (i++ / digits) * 0.7 + 0.3 ? d : CH[Math.random() * 10 | 0]
    )
  }, 55)
}

export function flipHide(el, target, ms) {
  if (!el) return
  const frames = Math.floor((ms || 280) / 55)
  const hidden = target.replace(/\d/g, '–')
  let f = 0
  clearInterval(el._flip)
  el.textContent = target.replace(/\d/g, () => CH[Math.random() * 10 | 0])
  el._flip = setInterval(() => {
    f++
    if (f >= frames) { el.textContent = hidden; clearInterval(el._flip); return }
    el.textContent = target.replace(/\d/g, () => CH[Math.random() * 10 | 0])
  }, 55)
}
