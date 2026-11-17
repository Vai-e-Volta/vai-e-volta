// Regras do anúncio na tela (F-38, RN-53 a RN-59). São auxílio visual: a API decide.

import { todayIso } from './format';
import { UF_OPTIONS, formatCep, isValidCep, onlyDigits } from './registrationValidation';

export const MAX_TITLE = 80;
export const MAX_DESCRIPTION = 1000;
export const MIN_PRICE = 1;
export const MAX_PRICE = 5000;
export const MAX_TAGS = 5;
export const MAX_TAG_LENGTH = 30;
export const MAX_PHOTOS = 5;
export const MAX_PHOTO_MB = 5;
export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

// Nomes dos campos de lista no multipart, como no Documento Técnico (seção 10).
export const TAGS_FIELD = 'tags[]';
export const PHOTOS_FIELD = 'photos[]';

export const PICKUP_FIELDS = [
  'pickup_cep',
  'pickup_street',
  'pickup_number',
  'pickup_complement',
  'pickup_neighborhood',
  'pickup_city',
  'pickup_state',
];

/** Ordem dos campos na tela, usada para focar o primeiro erro. */
export const LISTING_FIELD_ORDER = [
  'photos',
  'title',
  'description',
  'category_id',
  'tags',
  'daily_price',
  'max_days',
  'available_from',
  'available_until',
  ...PICKUP_FIELDS,
];

export const EMPTY_LISTING = {
  title: '',
  description: '',
  category_id: '',
  tags: [],
  daily_price: '',
  max_days: '',
  available_from: '',
  available_until: '',
  pickup_cep: '',
  pickup_street: '',
  pickup_number: '',
  pickup_complement: '',
  pickup_neighborhood: '',
  pickup_city: '',
  pickup_state: '',
};

/** Local de retirada inicial: o endereço do cadastro (RN-59). */
export function pickupFromUser(user) {
  const text = (value) => (value === null || value === undefined ? '' : String(value));
  return {
    pickup_cep: formatCep(text(user?.cep)),
    pickup_street: text(user?.street),
    pickup_number: text(user?.number),
    pickup_complement: text(user?.complement),
    pickup_neighborhood: text(user?.neighborhood),
    pickup_city: text(user?.city),
    pickup_state: text(user?.state),
  };
}

/** Tags que diferem só em maiúsculas ou acentos são a mesma (RN-57). */
export function normalizeTag(tag) {
  return tag.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
}

/**
 * Valor por dia digitado ("45", "45,5", "R$ 1.234,56") → "45.00"; null se não for um
 * número com até 2 casas decimais.
 */
export function parsePrice(value) {
  let text = String(value).replace(/R\$/g, '').replace(/\s/g, '');
  if (text.includes(',')) text = text.replace(/\./g, '').replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
  return Number(text).toFixed(2);
}

/** Dias da janela, contando início e fim (AAAA-MM-DD). */
export function windowDays(from, until) {
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = Date.parse(`${until}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.round((end - start) / 86_400_000) + 1;
}

/** Erro de um arquivo de foto (tipo e tamanho), ou null. */
export function photoFileError(file) {
  if (!PHOTO_TYPES.includes(file.type)) return `${file.name}: use JPEG, PNG ou WebP.`;
  if (file.size > MAX_PHOTO_MB * 1024 * 1024) {
    return `${file.name}: a foto passa de ${MAX_PHOTO_MB} MB.`;
  }
  return null;
}

const REQUIRED = 'Campo obrigatório.';

/** Retorna { campo: mensagem }; vazio quando tudo é válido. */
export function validateListing(values, photoCount, { today = todayIso() } = {}) {
  const errors = {};
  const set = (field, message) => {
    if (message) errors[field] = message;
  };

  set('photos', photoCount < 1 && 'Adicione ao menos 1 foto.');
  set('photos', photoCount > MAX_PHOTOS && `Use no máximo ${MAX_PHOTOS} fotos.`);

  const title = values.title.trim();
  set('title', !title ? REQUIRED : title.length > MAX_TITLE && `Use até ${MAX_TITLE} caracteres.`);
  const description = values.description.trim();
  set(
    'description',
    !description
      ? REQUIRED
      : description.length > MAX_DESCRIPTION && `Use até ${MAX_DESCRIPTION} caracteres.`,
  );
  set('category_id', !values.category_id && 'Escolha uma categoria.');
  set('tags', values.tags.length > MAX_TAGS && `Use no máximo ${MAX_TAGS} tags.`);

  if (!values.daily_price.trim()) {
    set('daily_price', REQUIRED);
  } else {
    const price = parsePrice(values.daily_price);
    set(
      'daily_price',
      price === null
        ? 'Informe um valor como 25,00.'
        : (Number(price) < MIN_PRICE || Number(price) > MAX_PRICE) &&
            'O valor por dia vai de R$ 1,00 a R$ 5.000,00.',
    );
  }

  set('available_from', !values.available_from && REQUIRED);
  if (!values.available_until) set('available_until', REQUIRED);
  else if (values.available_from && values.available_until < values.available_from) {
    set('available_until', 'O fim da janela deve ser igual ou depois do início.');
  } else if (values.available_until < today) {
    set('available_until', 'O fim da janela não pode estar no passado.');
  }

  const maxDays = String(values.max_days).trim();
  if (!maxDays) set('max_days', REQUIRED);
  else if (!/^\d+$/.test(maxDays) || Number(maxDays) < 1) {
    set('max_days', 'Informe um número inteiro de 1 ou mais.');
  } else if (!errors.available_from && !errors.available_until) {
    const days = windowDays(values.available_from, values.available_until);
    if (days !== null && Number(maxDays) > days) {
      set('max_days', `O máximo de dias não pode passar do tamanho da janela (${days} dias).`);
    }
  }

  set(
    'pickup_cep',
    !values.pickup_cep.trim()
      ? REQUIRED
      : !isValidCep(values.pickup_cep) && 'Informe um CEP com 8 dígitos.',
  );
  for (const field of ['pickup_street', 'pickup_number', 'pickup_neighborhood', 'pickup_city']) {
    set(field, !values[field].trim() && REQUIRED);
  }
  set(
    'pickup_state',
    !values.pickup_state ? REQUIRED : !UF_OPTIONS.includes(values.pickup_state) && 'UF inválida.',
  );

  return errors;
}

/**
 * Corpo multipart de POST /api/listings. `photos` são os arquivos na ordem escolhida;
 * o primeiro é a capa (RN-56).
 */
export function toListingFormData(values, photos) {
  const data = new FormData();
  data.append('title', values.title.trim());
  data.append('description', values.description.trim());
  data.append('category_id', String(values.category_id));
  data.append('daily_price', parsePrice(values.daily_price));
  data.append('max_days', String(Number(values.max_days)));
  data.append('available_from', values.available_from);
  data.append('available_until', values.available_until);
  for (const tag of values.tags) data.append(TAGS_FIELD, tag);
  for (const field of PICKUP_FIELDS) {
    const value = field === 'pickup_cep' ? onlyDigits(values[field]) : values[field].trim();
    if (value) data.append(field, value);
  }
  for (const photo of photos) data.append(PHOTOS_FIELD, photo);
  return data;
}

/** Erros por campo vindos da API; chaves de foto (photos, photos[], photos.2) viram "photos". */
export function listingServerErrors(error) {
  const errors = {};
  for (const [field, message] of Object.entries(error.fields ?? {})) {
    const key = field.startsWith('photos') ? 'photos' : field.startsWith('tags') ? 'tags' : field;
    if (LISTING_FIELD_ORDER.includes(key)) errors[key] = errors[key] ?? message;
  }
  if (!errors.photos && (error.code === 'FILE_TOO_LARGE' || error.code === 'UNSUPPORTED_MEDIA')) {
    errors.photos = error.message;
  }
  return errors;
}

export const KEEP_PHOTOS_FIELD = 'keep_photo_ids[]';

/** Foto salva vinda da API → item do PhotoUploader. */
function savedPhoto(photo) {
  return {
    key: `saved-${photo.id}`,
    id: photo.id,
    url: photo.url ?? `/uploads/${photo.filename}`,
  };
}

/**
 * Anúncio de GET /api/listings/{id} (visão do dono) → valores do formulário e fotos.
 * Aceita a categoria como `category_id` ou `category: {id}` e tags como texto ou `{name}`.
 */
export function listingToForm(listing) {
  const text = (value) => (value === null || value === undefined ? '' : String(value));
  const values = {
    title: text(listing.title),
    description: text(listing.description),
    category_id: text(listing.category_id ?? listing.category?.id),
    tags: (listing.tags ?? []).map((tag) => (typeof tag === 'string' ? tag : tag.name)),
    daily_price: listing.daily_price ? text(listing.daily_price).replace('.', ',') : '',
    max_days: text(listing.max_days),
    available_from: text(listing.available_from),
    available_until: text(listing.available_until),
    pickup_cep: formatCep(text(listing.pickup_cep)),
    pickup_street: text(listing.pickup_street),
    pickup_number: text(listing.pickup_number),
    pickup_complement: text(listing.pickup_complement),
    pickup_neighborhood: text(listing.pickup_neighborhood),
    pickup_city: text(listing.pickup_city),
    pickup_state: text(listing.pickup_state),
  };
  return { values, photos: (listing.photos ?? []).map(savedPhoto) };
}

const SCALAR_FIELDS = [
  'title',
  'description',
  'category_id',
  'daily_price',
  'max_days',
  'available_from',
  'available_until',
];

/**
 * Corpo multipart de PATCH /api/listings/{id}: só o que mudou (seção 10). Tags e local
 * de retirada, quando enviados, substituem os atuais; fotos vão como keep_photo_ids[]
 * (salvas, na ordem) e photos[] (novas, ao final). Retorna null se nada mudou.
 */
export function toListingUpdateFormData(values, initial, photos, initialPhotos) {
  const next = toListingFormData(values, []);
  const before = toListingFormData(initial, []);
  const data = new FormData();
  let changed = false;

  for (const field of SCALAR_FIELDS) {
    if (next.get(field) !== before.get(field)) {
      data.append(field, next.get(field));
      changed = true;
    }
  }

  const tags = next.getAll(TAGS_FIELD);
  if (tags.join('\n') !== before.getAll(TAGS_FIELD).join('\n')) {
    for (const tag of tags) data.append(TAGS_FIELD, tag);
    changed = true;
  }

  if (PICKUP_FIELDS.some((field) => next.get(field) !== before.get(field))) {
    for (const field of PICKUP_FIELDS) if (next.has(field)) data.append(field, next.get(field));
    changed = true;
  }

  const photoKeys = photos.map((photo) => photo.key).join('\n');
  if (photoKeys !== initialPhotos.map((photo) => photo.key).join('\n')) {
    for (const photo of photos) {
      if (photo.file) data.append(PHOTOS_FIELD, photo.file);
      else data.append(KEEP_PHOTOS_FIELD, String(photo.id));
    }
    changed = true;
  }

  return changed ? data : null;
}
