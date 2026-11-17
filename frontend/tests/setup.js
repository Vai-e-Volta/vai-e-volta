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
