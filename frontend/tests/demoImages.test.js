import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import demoImages from '../src/services/demoImages.json';
import { uploadUrl } from '../src/services/listings';

describe('imagens de demonstração', () => {
  it('serve as imagens fixas pelo frontend e mantém uploads de usuários no servidor', () => {
    expect(demoImages).toHaveLength(15);
    for (const name of demoImages) {
      expect(existsSync(join(process.cwd(), 'public', 'demo', name))).toBe(true);
      expect(uploadUrl(name)).toBe(`/demo/${name}`);
    }
    expect(uploadUrl('foto enviada.webp')).toBe('/uploads/foto%20enviada.webp');
    expect(uploadUrl(null)).toBeNull();
  });
});
