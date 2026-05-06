# Design

## Physical Scene

An operator checks a sensitive proactive Weixin system on a desktop browser during ordinary daytime work or a quiet late-night debugging session, trying to understand the system quickly without reading full logs.

## Theme

Light neutral operations desk with warm tinted surfaces. The UI should feel modern and clean, with floating rounded panels used as distinct work areas, but the information density stays practical.

## Color

Use OKLCH colors only. The strategy is restrained: tinted neutrals carry the interface, one teal accent marks active navigation and primary actions, semantic colors mark success, warning, error, and muted states.

- Page: `oklch(0.965 0.006 105)`
- Surface: `oklch(0.992 0.004 105)`
- Surface muted: `oklch(0.945 0.009 105)`
- Text: `oklch(0.245 0.018 245)`
- Muted text: `oklch(0.50 0.025 245)`
- Border: `oklch(0.872 0.012 105)`
- Accent: `oklch(0.56 0.12 174)`
- Success: `oklch(0.55 0.12 150)`
- Warning: `oklch(0.67 0.13 75)`
- Error: `oklch(0.58 0.17 28)`
- Info: `oklch(0.58 0.11 240)`

## Typography

Use a system sans stack: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`. Type scale is compact and fixed for product work. Headings use weight and spacing rather than display effects.

## Layout

The app shell uses a fixed sidebar and scrolling content area. Pages use a clear header, a metric strip where useful, and one or two full-width floating panels. Avoid nested cards. Tables remain available where comparison is the task.

## Components

- Panels: solid tinted surfaces, subtle border, soft shadow, 12px radius.
- Buttons: rounded, icon plus Chinese label, visible hover and focus states.
- Pills: small semantic badges for action, mode, class, source, and delivery status.
- Data: key-value rows, compact lists, confidence bars, timeline steps, and message bubbles replace raw JSON dumps.
- Empty states: short Chinese sentence explaining what is missing and which system area produces it.

## Motion

Only short hover and focus transitions, 150-200ms ease-out. No decorative page-load motion.
