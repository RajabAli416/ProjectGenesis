/**
 * SAMPLE PRESENTATION DATA
 *
 * Everything under src/sample/ is static fixture content authored by hand to
 * demonstrate layout, density and hierarchy. It is NOT the output of a
 * simulation, does not change over time, and must never be mistaken for a
 * research result. The interface surfaces this fact wherever the fixtures are
 * active (status bar tag, Overview notice).
 *
 * The fixtures are deliberately sparse: several sections expose their empty
 * states so the design of "no data yet" is exercised too.
 */
export const SAMPLE_DATA = {
  isSample: true,
  label: 'Sample presentation data',
  description:
    'Static fixtures bundled with the interface. No simulation engine is connected; nothing here was produced by agents.',
  authoredAt: '2026-11-02',
} as const;
