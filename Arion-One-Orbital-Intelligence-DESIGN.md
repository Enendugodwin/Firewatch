---
version: "alpha"
name: "Arion One — Orbital Intelligence"
description: "Arion One Login Section is designed for authenticating users through a focused access flow. Key features include reusable structure, responsive behavior, and production-ready presentation. It is suitable for authentication screens in web products."
colors:
  primary: "#60D58B"
  secondary: "#72A5F9"
  tertiary: "#62D5DD"
  neutral: "#131315"
  background: "#131315"
  surface: "#0B101D"
  text-primary: "#8C9099"
  text-secondary: "#FFFFFF"
  border: "#FFFFFF"
  accent: "#60D58B"
typography:
  display-lg:
    fontFamily: "Newsreader"
    fontSize: "60px"
    fontWeight: 400
    lineHeight: "63px"
    letterSpacing: "-0.025em"
  body-md:
    fontFamily: "Inter"
    fontSize: "14px"
    fontWeight: 300
    lineHeight: "22.4px"
  label-md:
    fontFamily: "Inter"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: "16px"
rounded:
  md: "0px"
  full: "9999px"
spacing:
  base: "6px"
  sm: "1px"
  md: "6px"
  lg: "8px"
  xl: "12px"
  gap: "8px"
  card-padding: "9px"
  section-padding: "28px"
components:
  button-primary:
    backgroundColor: "#FAFAFA"
    textColor: "#05070F"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: "8px"
  button-link:
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "0px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "11px"
    padding: "28px"
---

## Overview

- **Composition cues:**
  - Layout: Grid
  - Content Width: Full Bleed
  - Framing: Glassy
  - Grid: Strong

## Colors

The color system uses dark mode with #60D58B as the main accent and #131315 as the neutral foundation.

- **Primary (#60D58B):** Main accent and emphasis color.
- **Secondary (#72A5F9):** Supporting accent for secondary emphasis.
- **Tertiary (#62D5DD):** Reserved accent for supporting contrast moments.
- **Neutral (#131315):** Neutral foundation for backgrounds, surfaces, and supporting chrome.

- **Usage:** Background: #131315; Surface: #0B101D; Text Primary: #8C9099; Text Secondary: #FFFFFF; Border: #FFFFFF; Accent: #60D58B

- **Gradients:** bg-gradient-to-t from-[#05070f] to-transparent

## Typography

Typography pairs Newsreader for display hierarchy with Inter for supporting content and interface copy.

- **Display (`display-lg`):** Newsreader, 60px, weight 400, line-height 63px, letter-spacing -0.025em.
- **Body (`body-md`):** Inter, 14px, weight 300, line-height 22.4px.
- **Labels (`label-md`):** Inter, 12px, weight 500, line-height 16px.

## Layout

Layout follows a grid composition with reusable spacing tokens. Preserve the grid, full bleed structural frame before changing ornament or component styling. Use 6px as the base rhythm and let larger gaps step up from that cadence instead of introducing unrelated spacing values.

Treat the page as a grid / full bleed composition, and keep that framing stable when adding or remixing sections.

- **Layout type:** Grid
- **Content width:** Full Bleed
- **Base unit:** 6px
- **Scale:** 1px, 6px, 8px, 12px, 16px, 20px, 24px, 28px
- **Section padding:** 28px, 56px, 112px
- **Card padding:** 9px, 22px, 28px
- **Gaps:** 8px, 10px, 12px, 20px

## Elevation & Depth

Depth is communicated through glass, border contrast, and reusable shadow or blur treatments. Keep those recipes consistent across hero panels, cards, and controls so the page reads as one material system.

Surfaces should read as glass first, with borders, shadows, and blur only reinforcing that material choice.

- **Surface style:** Glass
- **Borders:** 0.8px #FFFFFF
- **Shadows:** rgba(255, 255, 255, 0.25) 0px 0px 18px 0px; rgb(59, 130, 246) 0px 0px 8px 0px; rgba(255, 255, 255, 0.25) 0px 0px 24px 0px
- **Blur:** 14px

### Techniques
- **Gradient border shell:** Use a thin gradient border shell around the main card. Wrap the surface in an outer shell with 1px padding and a 12px radius. Drive the shell with linear-gradient(to right bottom, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.03), rgba(0, 0, 0, 0)) so the edge reads like premium depth instead of a flat stroke. Keep the actual stroke understated so the gradient shell remains the hero edge treatment. Inset the real content surface inside the wrapper with a slightly smaller radius so the gradient only appears as a hairline frame.

## Shapes

Shapes rely on a tight radius system anchored by 7px and scaled across cards, buttons, and supporting surfaces. Icon geometry should stay compatible with that soft-to-controlled silhouette.

Use the radius family intentionally: larger surfaces can open up, but controls and badges should stay within the same rounded DNA instead of inventing sharper or pill-only exceptions.

- **Corner radii:** 7px, 8px, 11px, 12px, 9999px
- **Icon treatment:** Linear
- **Icon sets:** Solar

## Components

Anchor interactions to the detected button styles. Reuse the existing card surface recipe for content blocks.

### Buttons
- **Primary:** background #FAFAFA, text #05070F, radius 9999px, padding 8px, border 0px solid rgb(229, 231, 235).
- **Links:** text #8C9099, radius 0px, padding 0px, border 0px solid rgb(229, 231, 235).

### Cards and Surfaces
- **Card surface:** background #0B101D, border 0px solid rgb(229, 231, 235), radius 11px, padding 28px, shadow none.

### Iconography
- **Treatment:** Linear.
- **Sets:** Solar.

## Do's and Don'ts

Use these constraints to keep future generations aligned with the current system instead of drifting into adjacent styles.

### Do
- Do use the primary palette as the main accent for emphasis and action states.
- Do keep spacing aligned to the detected 6px rhythm.
- Do reuse the Glass surface treatment consistently across cards and controls.
- Do keep corner radii within the detected 7px, 8px, 11px, 12px, 9999px family.

### Don't
- Don't introduce extra accent colors outside the core palette roles unless the page needs a new semantic state.
- Don't mix unrelated shadow or blur recipes that break the current depth system.
- Don't exceed the detected minimal motion intensity without a deliberate reason.

## Motion

Motion stays restrained and interface-led across text, layout, and scroll transitions. Timing clusters around 150ms and 1000ms. Easing favors ease and 0. Hover behavior focuses on text changes.

**Motion Level:** minimal

**Durations:** 150ms, 1000ms

**Easings:** ease, 0, 0.2, 1), cubic-bezier(0.4, cubic-bezier(0

**Hover Patterns:** text

## WebGL

Reconstruct the graphics as a full-bleed background field using webgl, renderer, alpha, antialias, dpr clamp, custom shaders. The effect should read as retro-futurist, technical, and meditative: perspective grid field with green on black and sparse spacing. Build it from grid lines + depth fade so the effect reads clearly. Animate it as slow breathing pulse. Interaction can react to the pointer, but only as a subtle drift. Preserve dom fallback.

**Id:** webgl

**Label:** WebGL

**Stack:** ThreeJS, WebGL

**Insights:**
  - **Scene:**
    - **Value:** Full-bleed background field
  - **Effect:**
    - **Value:** Perspective grid field
  - **Primitives:**
    - **Value:** Grid lines + depth fade
  - **Motion:**
    - **Value:** Slow breathing pulse
  - **Interaction:**
    - **Value:** Pointer-reactive drift
  - **Render:**
    - **Value:** WebGL, Renderer, alpha, antialias, DPR clamp, custom shaders

**Techniques:** Perspective grid, Breathing pulse, Pointer parallax, Shader gradients, DOM fallback

**Code Evidence:**
  - **HTML reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <!-- 3D Earth canvas -->
      <canvas id="earth-canvas" style="position:absolute; inset:0; width:100%; height:100%; z-index:0; display:block; pointer-events:none;"></canvas>

      <!-- Bottom gradient to fuse into next section -->
      ```
  - **JS reference:**
    - **Language:** js
    - **Snippet:**
      ```
      (function () {
        const canvas = document.getElementById('earth-canvas');
        if (!window.THREE) return;

        const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);
      …
      ```

## ThreeJS

Reconstruct the Three.js layer as a full-bleed background field with layered spatial depth that feels retro-futurist, volumetric, and technical. Use alpha, antialias, dpr clamp renderer settings, perspective, ~45deg fov, sphere + custom buffer geometry geometry, meshstandardmaterial + shadermaterial materials, and ambient + directional + point lighting. Motion should read as slow orbital drift, with poster frame + dom fallback.

**Id:** threejs

**Label:** ThreeJS

**Stack:** ThreeJS, WebGL

**Insights:**
  - **Scene:**
    - **Value:** Full-bleed background field with layered spatial depth
  - **Render:**
    - **Value:** alpha, antialias, DPR clamp
  - **Camera:**
    - **Value:** Perspective, ~45deg FOV
  - **Lighting:**
    - **Value:** ambient + directional + point
  - **Materials:**
    - **Value:** MeshStandardMaterial + ShaderMaterial
  - **Geometry:**
    - **Value:** sphere + custom buffer geometry
  - **Motion:**
    - **Value:** Slow orbital drift

**Techniques:** PBR shading, Shader materials, Particle depth, Timeline beats, alpha, antialias, DPR clamp

**Code Evidence:**
  - **HTML reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <!-- 3D Earth canvas -->
      <canvas id="earth-canvas" style="position:absolute; inset:0; width:100%; height:100%; z-index:0; display:block; pointer-events:none;"></canvas>

      <!-- Bottom gradient to fuse into next section -->
      ```
  - **JS reference:**
    - **Language:** js
    - **Snippet:**
      ```
      (function () {
        const canvas = document.getElementById('earth-canvas');
        if (!window.THREE) return;

        const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);
      …
      ```
