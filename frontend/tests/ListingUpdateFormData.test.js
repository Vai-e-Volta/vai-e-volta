import { describe, expect, it } from 'vitest';
import { listingToForm, toListingUpdateFormData } from '../src/utils/listingValidation';

describe('dados parciais da edição', () => {
  it('envia lista vazia de tags e permite limpar complemento de retirada', () => {
    const { values, photos } = listingToForm({
      title: 'Item',
      description: 'Descrição',
      category_id: 1,
      tags: ['obra'],
      daily_price: '25.00',
      max_days: 5,
      available_from: '2099-01-01',
      available_until: '2099-01-31',
      pickup_cep: '96200000',
      pickup_street: 'Rua',
      pickup_number: '1',
      pickup_complement: 'Sala',
      pickup_neighborhood: 'Centro',
      pickup_city: 'Rio Grande',
      pickup_state: 'RS',
      photos: [{ id: 1, filename: 'foto.png' }],
    });
    const updated = { ...values, tags: [], pickup_complement: '' };
    const form = toListingUpdateFormData(updated, values, photos, photos);
    expect(form.getAll('tags[]')).toEqual(['']);
    expect(form.get('pickup_complement')).toBe('');
    expect(form.get('pickup_street')).toBe('Rua');
  });
});
