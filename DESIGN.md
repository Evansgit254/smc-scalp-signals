---
name: Institutional Quant Terminal
colors:
  surface: '#0f131b'
  surface-dim: '#0f131b'
  surface-bright: '#353942'
  surface-container-lowest: '#0a1e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#bbc9cf'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#859398'
  outline-variant: '#3c494e'
  surface-tint: '#3cd7ff'
  primary: '#a8e8ff'
  on-primary: '#003642'
  primary-container: '#00d4ff'
  on-primary-container: '#00586b'
  inverse-primary: '#00677e'
  secondary: '#43e5b1'
  on-secondary: '#003828'
  secondary-container: '#01c896'
  on-secondary-container: '#004d38'
  tertiary: '#ffd5d5'
  on-tertiary: '#68001a'
  tertiary-container: '#ffadb1'
  on-tertiary-container: '#a3002e'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#b4ebff'
  primary-fixed-dim: '#3cd7ff'
  on-primary-fixed: '#001f27'
  on-primary-fixed-variant: '#004e5f'
  secondary-fixed: '#60fcc6'
  secondary-fixed-dim: '#3adfab'
  on-secondary-fixed: '#002116'
  on-secondary-fixed-variant: '#00513b'
  tertiary-fixed: '#ffdada'
  tertiary-fixed-dim: '#ffb3b6'
  on-tertiary-fixed: '#40000c'
  on-tertiary-fixed-variant: '#920028'
  background: '#0f131b'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-lg:
    fontFamily: JetBrains Mono
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
  data-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  data-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 8px
  margin-sm: 12px
  margin-md: 16px
  panel-padding: 12px
---

## Brand & Style

This design system is engineered for institutional high-frequency trading and quantitative analysis. The brand personality is clinical, precise, and authoritative, prioritizing information density over decorative elements. The target audience consists of professional traders and analysts who require a "heads-up display" experience that minimizes cognitive load during high-stages decision-making.

The design style is **Corporate / Modern** with a **Technical** edge. It utilizes a dark-first architecture to reduce eye strain during extended sessions. Aesthetics are driven by structural integrity: sharp lines, 1px micro-borders, and a total absence of gradients, blurs, or skeuomorphic depth. Every pixel serves a functional purpose, evoking a sense of industrial-grade reliability and mathematical accuracy.

## Colors

The palette is anchored in a triple-layered dark gray foundation to establish clear information hierarchy without relying on shadows.

- **Primary Background (#0A0C10):** The base layer for the entire application.
- **Surface (#10141C):** Used for structural navigation or background grouping.
- **Card/Panel (#161B26):** The highest layer for active data modules and interactive widgets.
- **Electric Cyan (#00D4FF):** The primary action color, used for CTA buttons, active states, and focus indicators.
- **Emerald (#00C896) / Crimson (#FF3B5C):** Functional semantic colors for "Long/Gain" and "Short/Loss" indicators.
- **Amber (#F5A623):** Reserved for warnings and execution alerts.

Text colors should strictly follow a hierarchy: White (#FFFFFF) for primary headers, Slate Gray (#94A3B8) for secondary labels, and Dark Slate (#475569) for disabled or tertiary metadata.

## Typography

This design system employs a dual-font strategy to separate qualitative labels from quantitative data.

**Inter** is the primary typeface for all UI chrome, labels, navigation, and instructional text. It provides high legibility at small sizes. Use `label-caps` for table headers and section titles to maximize vertical space.

**JetBrains Mono** is mandatory for all numerical values, price tickers, timestamps, and code-based inputs. The monospaced nature ensures that numbers do not "jump" when values update rapidly, maintaining visual alignment in data grids.

On mobile, reduce `display-lg` to 24px and increase `body-md` touch targets by ensuring line-height remains generous even if the font size is small.

## Layout & Spacing

The layout utilizes a **Fluid Grid** system optimized for multi-monitor setups and wide-screen dashboard configurations. The core spacing rhythm is based on a **4px baseline**, allowing for the extreme information density required for trading terminals.

- **Desktop:** A 12-column or 24-column grid depending on panel complexity. Gutters are kept tight at 8px to maximize data real estate.
- **Panels:** Use a standard 12px internal padding for all data containers.
- **Density:** Elements should be tightly packed. Vertical spacing between rows in data tables should not exceed 8px.
- **Breakpoints:** 
  - Mobile (<768px): Single column, stackable panels.
  - Tablet (768px - 1280px): 2-column dashboard layout.
  - Desktop (>1280px): Multi-pane workspace with adjustable split-views.

## Elevation & Depth

Depth is communicated through **Tonal Layers** and **Low-Contrast Outlines**. 

Shadows are entirely prohibited to maintain a flat, performant aesthetic. Instead, hierarchy is achieved by stepping up the background luminosity:
1. **Level 0 (Base):** #0A0C10
2. **Level 1 (Panels):** #161B26
3. **Level 2 (Popovers/Tooltips):** #1C2331

Every container must feature a **1px solid border** (#262D3D). For active or focused states, this border transitions to Electric Cyan (#00D4FF). This "micro-border" approach provides sharp definition between dense data sets without using excessive white space.

## Shapes

The shape language is strictly geometric and utilitarian. All containers, buttons, and input fields utilize a **4px corner radius**. This provides a subtle "softness" that prevents the UI from feeling aggressive while maintaining the professional, structured look of a high-end instrument. 

Status indicators (e.g., connectivity lights) may use a circular (100% radius) shape, but all structural UI elements must adhere to the 4px rule.
