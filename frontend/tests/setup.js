import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom não implementa prévias de arquivo (usadas pelo PhotoUploader).
if (!URL.createObjectURL) URL.createObjectURL = () => 'blob:previa';
if (!URL.revokeObjectURL) URL.revokeObjectURL = () => {};

// jsdom não implementa IntersectionObserver (rolagem infinita do feed). Os testes
// disparam a interseção com `intersectAll()`.
const observers = new Set();
class MockIntersectionObserver {
  constructor(callback) {
    this.callback = callback;
    this.targets = new Set();
  }
  observe(target) {
    this.targets.add(target);
    observers.add(this);
  }
  unobserve(target) {
    this.targets.delete(target);
  }
  disconnect() {
    this.targets.clear();
    observers.delete(this);
  }
}
globalThis.IntersectionObserver = MockIntersectionObserver;
globalThis.intersectAll = () => {
  for (const observer of [...observers]) {
    observer.callback([...observer.targets].map((target) => ({ target, isIntersecting: true })));
  }
};
afterEach(() => observers.clear());
