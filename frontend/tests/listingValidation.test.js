import { describe, expect, it } from 'vitest';
import {
  EMPTY_LISTING,
  listingServerErrors,
  normalizeTag,
  parsePrice,
  photoFileError,
  toListingFormData,
  validateListing,
  windowDays,
} from '../src/utils/listingValidation';
import { todayIso } from '../src/utils/format';

const VALID = {
  ...EMPTY_LISTING,
  title: 'Furadeira de impacto',
  description: 'Acompanha maleta e brocas.',
  category_id: '1',
  tags: ['Ferramenta'],
  daily_price: '25,00',
  max_days: '7',
  available_from: '2026-11-20',
  available_until: '2026-12-20',
  pickup_cep: '96200-000',
  pickup_street: 'Rua das Flores',
  pickup_number: '100',
  pickup_neighborhood: 'Centro',
  pickup_city: 'Rio Grande',
  pickup_state: 'RS',
};
const TODAY = { today: '2026-11-15' };

describe('regras do anúncio (F-38)', () => {
  it('aceita um anúncio completo', () => {
    expect(validateListing(VALID, 1, TODAY)).toEqual({});
  });

  it('RN-53: campos obrigatórios e ao menos 1 foto', () => {
    const errors = validateListing(EMPTY_LISTING, 0, TODAY);
    for (const field of [
      'photos',
      'title',
      'description',
      'category_id',
      'daily_price',
      'max_days',
      'available_from',
      'available_until',
      'pickup_cep',
      'pickup_state',
    ]) {
      expect(errors).toHaveProperty(field);
    }
    expect(errors).not.toHaveProperty('pickup_complement');
    expect(errors).not.toHaveProperty('tags');
  });

  it('RN-53: nome até 80 e descrição até 1.000 caracteres', () => {
    const errors = validateListing(
      { ...VALID, title: 'a'.repeat(81), description: 'b'.repeat(1001) },
      1,
      TODAY,
    );
    expect(errors.title).toMatch('80');
    expect(errors.description).toMatch('1000');
  });

  it('RN-32: valor por dia entre R$ 1,00 e R$ 5.000,00', () => {
    expect(parsePrice('25')).toBe('25.00');
    expect(parsePrice('25,5')).toBe('25.50');
    expect(parsePrice('R$ 1.234,56')).toBe('1234.56');
    expect(parsePrice('12.5')).toBe('12.50');
    expect(parsePrice('abc')).toBeNull();
    expect(parsePrice('1,234')).toBeNull();
    expect(validateListing({ ...VALID, daily_price: '0,99' }, 1, TODAY).daily_price).toMatch(
      'R$ 1,00',
    );
    expect(validateListing({ ...VALID, daily_price: '5000,01' }, 1, TODAY)).toHaveProperty(
      'daily_price',
    );
    expect(validateListing({ ...VALID, daily_price: '5000' }, 1, TODAY)).toEqual({});
  });

  it('janela com início ≤ fim e fim não no passado (RN-54)', () => {
    expect(
      validateListing({ ...VALID, available_until: '2026-11-19' }, 1, TODAY).available_until,
    ).toMatch('depois do início');
    expect(
      validateListing(
        { ...VALID, available_from: '2026-11-01', available_until: '2026-11-14' },
        1,
        TODAY,
      ).available_until,
    ).toMatch('passado');
    expect(
      validateListing(
        { ...VALID, available_from: '2026-11-01', available_until: '2026-11-15', max_days: '1' },
        1,
        TODAY,
      ),
    ).toEqual({});
  });

  it('RN-55: máximo de dias não passa do tamanho da janela, sem ajustar', () => {
    expect(windowDays('2026-11-20', '2026-11-26')).toBe(7);
    expect(validateListing({ ...VALID, available_until: '2026-11-26' }, 1, TODAY)).toEqual({});
    expect(validateListing({ ...VALID, available_until: '2026-11-25' }, 1, TODAY).max_days).toMatch(
      '6 dias',
    );
    expect(validateListing({ ...VALID, max_days: '0' }, 1, TODAY)).toHaveProperty('max_days');
    expect(validateListing({ ...VALID, max_days: '1.5' }, 1, TODAY)).toHaveProperty('max_days');
  });

  it('RN-56: até 5 fotos JPEG, PNG ou WebP de até 5 MB', () => {
    expect(validateListing(VALID, 6, TODAY).photos).toMatch('5 fotos');
    const file = (type, size) => ({ name: 'foto', type, size });
    expect(photoFileError(file('image/jpeg', 1024))).toBeNull();
    expect(photoFileError(file('image/webp', 5 * 1024 * 1024))).toBeNull();
    expect(photoFileError(file('image/gif', 1024))).toMatch('JPEG, PNG ou WebP');
    expect(photoFileError(file('image/png', 5 * 1024 * 1024 + 1))).toMatch('5 MB');
  });

  it('RN-57: tags iguais sem maiúsculas e acentos e no máximo 5', () => {
    expect(normalizeTag('  Ferramentá ')).toBe('ferramenta');
    expect(
      validateListing({ ...VALID, tags: ['a', 'b', 'c', 'd', 'e', 'f'] }, 1, TODAY),
    ).toHaveProperty('tags');
  });

  it('monta o multipart com valores sem máscara, tags e fotos na ordem', () => {
    const photos = [new File(['1'], 'capa.jpg'), new File(['2'], 'lado.jpg')];
    const data = toListingFormData({ ...VALID, tags: ['Ferramenta', 'Obra'] }, photos);

    expect(data.get('daily_price')).toBe('25.00');
    expect(data.get('max_days')).toBe('7');
    expect(data.get('category_id')).toBe('1');
    expect(data.get('pickup_cep')).toBe('96200000');
    expect(data.has('pickup_complement')).toBe(false);
    expect(data.getAll('tags[]')).toEqual(['Ferramenta', 'Obra']);
    expect(data.getAll('photos[]').map((file) => file.name)).toEqual(['capa.jpg', 'lado.jpg']);
  });

  it('erros da API de foto e de tag caem nos campos photos e tags', () => {
    expect(
      listingServerErrors({
        code: 'VALIDATION_ERROR',
        fields: { 'photos.2': 'Inválida.', 'tags[0]': 'Longa.', title: 'Curto.', x: '?' },
      }),
    ).toEqual({ photos: 'Inválida.', tags: 'Longa.', title: 'Curto.' });
    expect(
      listingServerErrors({ code: 'FILE_TOO_LARGE', message: 'Foto acima de 5 MB.', fields: {} }),
    ).toEqual({ photos: 'Foto acima de 5 MB.' });
  });

  it('RN-69: hoje é calculado no fuso America/Sao_Paulo', () => {
    // 02h UTC de 16/11 ainda é 15/11 em São Paulo.
    expect(todayIso(new Date('2026-11-16T02:00:00Z'))).toBe('2026-11-15');
  });
});
