import { expect, type Locator, type Page } from '@playwright/test'

export type BrowserErrors = {
  readonly consoleErrors: string[]
  readonly expectedConsoleErrorsByStatus: Record<string, string[]>
  readonly pageErrors: string[]
}

export function captureBrowserErrors(page: Page, expectedHttpStatuses: readonly number[] = []): BrowserErrors {
  const consoleErrors: string[] = []
  const expectedStatusSet = new Set(expectedHttpStatuses)
  const expectedConsoleErrorsByStatus: Record<string, string[]> = {}
  for (const status of expectedHttpStatuses) expectedConsoleErrorsByStatus[String(status)] = []
  const pageErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    const text = message.text()
    const statusMatch = /\bstatus of (\d{3})(?:\s|\()/.exec(text)
    const status = statusMatch?.[1] === undefined ? Number.NaN : Number(statusMatch[1])
    if (expectedStatusSet.has(status)) expectedConsoleErrorsByStatus[String(status)]?.push(text)
    else consoleErrors.push(text)
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  return { consoleErrors, expectedConsoleErrorsByStatus, pageErrors }
}

export function expectHttpConsoleErrors(errors: BrowserErrors, status: number, count: number) {
  expect(errors.expectedConsoleErrorsByStatus[String(status)] ?? []).toHaveLength(count)
}

export async function layoutEvidence(page: Page) {
  return page.evaluate(async () => {
    const root = document.documentElement
    const selector = 'button, input, textarea, select, a[href], [role="button"]'
    const positionedAncestor = (element: Element | null) => {
      let current = element instanceof HTMLElement ? element : null
      while (current !== null) {
        const position = getComputedStyle(current).position
        if (position === 'sticky' || position === 'fixed') return current
        current = current.parentElement
      }
      return null
    }
    const controls = [...document.querySelectorAll<HTMLElement>(selector)]
      .filter((element) => {
        const box = element.getBoundingClientRect()
        return element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
          && !(element.classList.contains('skip-link') && document.activeElement !== element)
          && box.width >= 8 && box.height >= 8
      })
      .map((element, index) => {
        const label = element.getAttribute('aria-label') ?? element.innerText.trim()
        return { element, description: `${element.tagName}:${label || `control-${index}`}` }
      })
    const nestedInteractiveControls = controls.flatMap((control) => {
      const ancestor = control.element.parentElement?.closest<HTMLElement>(selector)
      return ancestor === null || ancestor === undefined
        ? []
        : [`${control.description} nested inside ${ancestor.tagName}:${ancestor.getAttribute('aria-label') ?? ancestor.innerText.trim()}`]
    })
    const scrollPositions = [...document.querySelectorAll<HTMLElement>('*')]
      .filter((element) => element.scrollHeight > element.clientHeight || element.scrollWidth > element.clientWidth)
      .map((element) => ({ element, left: element.scrollLeft, top: element.scrollTop }))
    const initialWindowScroll = { left: window.scrollX, top: window.scrollY }
    const offscreenControls = new Set<string>()
    const usabilityOcclusions = new Set<string>()
    const stickyOcclusions = new Set<string>()
    const overlaps = new Set<string>()
    const waitForLayout = () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
    const collectOverlaps = () => {
      const visibleControls = controls.filter((candidate) => {
        const candidateBox = candidate.element.getBoundingClientRect()
        return candidateBox.right > 0 && candidateBox.left < window.innerWidth
          && candidateBox.bottom > 0 && candidateBox.top < window.innerHeight
      })
      for (let leftIndex = 0; leftIndex < visibleControls.length; leftIndex += 1) {
        const left = visibleControls[leftIndex]
        if (left === undefined) continue
        for (let rightIndex = leftIndex + 1; rightIndex < visibleControls.length; rightIndex += 1) {
          const right = visibleControls[rightIndex]
          if (right === undefined || left.element.contains(right.element) || right.element.contains(left.element)) continue
          const leftPositioned = positionedAncestor(left.element)
          const rightPositioned = positionedAncestor(right.element)
          if ((leftPositioned === null) !== (rightPositioned === null)) continue
          const leftBox = left.element.getBoundingClientRect()
          const rightBox = right.element.getBoundingClientRect()
          const overlapWidth = Math.min(leftBox.right, rightBox.right) - Math.max(leftBox.left, rightBox.left)
          const overlapHeight = Math.min(leftBox.bottom, rightBox.bottom) - Math.max(leftBox.top, rightBox.top)
          if (overlapWidth > 1 && overlapHeight > 1) {
            overlaps.add(`${left.description} [${leftBox.left},${leftBox.top},${leftBox.right},${leftBox.bottom}] <> ${right.description} [${rightBox.left},${rightBox.top},${rightBox.right},${rightBox.bottom}]`)
          }
        }
      }
    }
    for (const control of controls) {
      control.element.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' })
      await waitForLayout()
      const box = control.element.getBoundingClientRect()
      const intersectsViewport = box.right > 0 && box.left < window.innerWidth && box.bottom > 0 && box.top < window.innerHeight
      if (!intersectsViewport) {
        offscreenControls.add(`${control.description} remains offscreen after scrollIntoView`)
        continue
      }
      const points = [
        [box.left + box.width / 2, box.top + box.height / 2],
        [box.left + 2, box.top + 2],
        [box.right - 2, box.bottom - 2],
      ] as const
      const hits = points.map(([rawX, rawY]) => document.elementFromPoint(
        Math.min(window.innerWidth - 1, Math.max(0, rawX)),
        Math.min(window.innerHeight - 1, Math.max(0, rawY)),
      ))
      const unrelatedStickyHits = hits.flatMap((hit) => {
        if (hit !== null && control.element.contains(hit)) return []
        const positioned = positionedAncestor(hit)
        if (positioned === null || positioned.contains(control.element) || control.element.contains(positioned)) return []
        return [positioned]
      })
      for (const positioned of unrelatedStickyHits) {
        stickyOcclusions.add(`${control.description} covered by ${positioned.tagName}`)
      }
      if (!hits.some((hit) => hit !== null && control.element.contains(hit))) {
        usabilityOcclusions.add(`${control.description} has no usable hit-test sample after scrollIntoView`)
      }
    }
    for (const position of scrollPositions) position.element.scrollTo({ left: position.left, top: position.top, behavior: 'instant' })
    window.scrollTo({ left: initialWindowScroll.left, top: initialWindowScroll.top, behavior: 'instant' })
    await waitForLayout()
    collectOverlaps()
    return {
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      horizontalOverflow: root.scrollWidth - root.clientWidth,
      controlCount: controls.length,
      nestedInteractiveControls,
      offscreenControls: [...offscreenControls],
      usabilityOcclusions: [...usabilityOcclusions],
      overlaps: [...overlaps],
      stickyOcclusions: [...stickyOcclusions],
    }
  })
}

export async function canvasColorVariation(canvas: Locator) {
  return canvas.evaluate((element) => {
    if (!(element instanceof HTMLCanvasElement)) return { opaquePixels: 0, nonBackgroundPixels: 0, colorCount: 0 }
    const context = element.getContext('2d')
    if (context === null) return { opaquePixels: 0, nonBackgroundPixels: 0, colorCount: 0 }
    const pixels = context.getImageData(0, 0, element.width, element.height).data
    const colors = new Map<number, number>()
    let opaquePixels = 0
    for (let pixel = 0; pixel < pixels.length; pixel += 4) {
      if ((pixels[pixel + 3] ?? 0) === 0) continue
      opaquePixels += 1
      const color = ((pixels[pixel] ?? 0) << 16) | ((pixels[pixel + 1] ?? 0) << 8) | (pixels[pixel + 2] ?? 0)
      colors.set(color, (colors.get(color) ?? 0) + 1)
    }
    const backgroundPixels = Math.max(0, ...colors.values())
    return { opaquePixels, nonBackgroundPixels: opaquePixels - backgroundPixels, colorCount: colors.size }
  })
}
