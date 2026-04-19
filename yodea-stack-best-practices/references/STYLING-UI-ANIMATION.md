# Tailwind CSS v4, shadcn/ui & Motion Animations

## Tailwind CSS v4

### CSS-First Configuration

No more `tailwind.config.js`. All config lives in CSS:

```css
@import "tailwindcss";

@theme {
  --color-brand-500: oklch(0.60 0.20 250);
  --font-sans: "Figtree Variable", sans-serif;
  --radius-4xl: 2rem;
}
```

This auto-generates `bg-brand-500`, `text-brand-500`, `font-sans`, `rounded-4xl`, etc.
Every `@theme` token becomes a real CSS custom property.

### Vite Integration

Use `@tailwindcss/vite` plugin (faster than PostCSS):

```typescript
// vite.config.ts
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

### Runtime Theme Switching (No Rebuild)

```css
[data-theme="dark"] {
  --color-surface: #09090b;
  --color-text-primary: #fafafa;
}
```

Switch with `document.documentElement.dataset.theme = 'dark'`.

### New Features

- **Container queries**: built-in (`@container`, `@sm:`, `@lg:`) -- no plugin needed
- **`@utility`**: define custom utilities in CSS (Tailwind auto-generates variants)
- **`@variant`**: `@variant hocus (&:hover, &:focus);`
- **3D transforms**: `perspective-*`, `rotate-x-*`, `rotate-y-*`
- **Wide-gamut colors**: OKLCH palette with automatic sRGB fallbacks
- **`not-*` variant**: `not-disabled:opacity-100`

### Performance

- Full rebuilds: ~100ms (was ~3,500ms in v3) -- **35x faster**
- Incremental rebuilds: ~5ms (was ~350ms) -- **70x faster**
- CSS bundle size: ~15% smaller

### Migration Key Renames

| v3 | v4 |
|---|---|
| `bg-gradient-to-r` | `bg-linear-to-r` |
| `flex-shrink` / `flex-grow` | `shrink` / `grow` |
| `overflow-ellipsis` | `text-ellipsis` |
| `shadow-sm` | `shadow-xs` |

Run `npx @tailwindcss/upgrade` for automated migration (~90% of renames).

## shadcn/ui + Radix UI

### Component Architecture

Treat shadcn as source code, not a dependency. Organize into three tiers:

```
ui/           -- Raw shadcn components (minimal modification)
primitives/   -- Lightly customized wrappers
blocks/       -- Product-level compositions (pricing cards, auth forms)
```

Create app-specific wrappers (e.g., `AppButton`) for global consistency.

### Performance Patterns

- **Prefer CSS over React state** for hover/focus/active:

```tsx
// BAD
const [hovered, setHovered] = useState(false);
<div onMouseEnter={() => setHovered(true)} className={hovered ? "bg-blue" : ""} />

// GOOD
<div className="hover:bg-blue" />
```

- Use CSS animations instead of JS-driven for simple transitions
- Keep variant counts low -- each adds bundle weight
- Primitives are tree-shakeable and SSR-friendly

### Accessibility

Radix provides ARIA, keyboard, and focus management by default. Do not break it by:
- Incorrectly using `asChild`
- Nesting interactive elements (button inside button)
- Overriding focus ring styles without replacement

Re-test keyboard navigation and screen reader behavior after semantic changes.

### Design Tokens

Define tokens early as CSS variables mapped to Tailwind `@theme`:

```css
@theme {
  --color-primary: oklch(0.488 0.243 264.376);
  --color-primary-foreground: oklch(0.97 0.014 254.604);
  --radius-lg: 0.625rem;
}
```

Avoid hardcoding Tailwind values in components -- reference tokens instead.

## Motion (Framer Motion) v12

### GPU Compositing Rules

**Always animate (compositor-safe, 120fps):**
- `transform` (translate, scale, rotate)
- `opacity`

**Never animate directly:**
- `width`, `height`, `padding`, `margin`
- `top`, `left`, `right`, `bottom`
- `border-width`, `box-shadow`, `border-radius`

**Alternatives:**
- `filter: drop-shadow()` instead of `boxShadow`
- `clipPath: inset(0 round X)` instead of `borderRadius`

### WAAPI Hardware Acceleration

Use string-based transform syntax for GPU acceleration:

```typescript
// GPU-accelerated
animate(".box", { transform: "translateX(100px) scale(2)" })

// NOT accelerated (uses CSS variables)
animate(".box", { x: 100, scale: 2 })
```

### Layout Animations

- `layout` prop uses FLIP: measures change, animates with `transform`
- Apply `layout` to child elements too (counters scale distortion)
- Set `border-radius` and `box-shadow` via `style` prop for correction during scale
- Use `layoutId` for shared element transitions between components
- Pitfall: `display: inline` elements cannot receive transform animations

### Exit Animations (AnimatePresence)

```tsx
<AnimatePresence mode="popLayout">
  {items.map(item => (
    <motion.div
      key={item.id}  // Stable, unique key (NEVER array index)
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    />
  ))}
</AnimatePresence>
```

- Every direct child needs a unique, stable `key`
- Place `AnimatePresence` at the conditional boundary, not inside
- Mode: `"sync"` (simultaneous), `"wait"` (sequential), `"popLayout"` (removes from flow)
- `initial={false}` to skip animation on first render
- `onExitComplete` for cleanup after all exits

### Performance Checklist

1. Audit all animations: replace layout-triggering properties with transform/opacity
2. Use string-based transform for WAAPI hardware acceleration
3. Use `AnimatePresence` with stable keys and appropriate `mode`
4. Apply `layout` to children of layout-animated parents
5. Profile with Chrome DevTools on throttled CPU (4x slowdown)
6. At 60fps you have 16.7ms per frame; layout properties can take >100ms
