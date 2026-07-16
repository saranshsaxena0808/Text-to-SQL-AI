import "@testing-library/jest-dom/vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
});

Object.defineProperty(navigator, "clipboard", {
  value: { writeText: async () => undefined }, configurable: true,
});
