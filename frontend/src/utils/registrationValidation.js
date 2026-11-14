// Validação do cadastro na tela (F-04). É só auxílio: a fonte da verdade é a API.
// As regras espelham RN-02 a RN-08 (Documento Técnico, seção 4).

export const UF_OPTIONS = [
  'AC',
  'AL',
  'AP',
  'AM',
  'BA',
  'CE',
  'DF',
  'ES',
  'GO',
  'MA',
  'MT',
  'MS',
  'MG',
  'PA',
  'PB',
  'PR',
  'PE',
  'PI',
  'RJ',
  'RN',
  'RS',
  'RO',
  'RR',
  'SC',
  'SP',
  'SE',
  'TO',
];

export const onlyDigits = (value) => value.replace(/\D/g, '');

// --- Máscaras -------------------------------------------------------------

export function formatCpf(value) {
  const digits = onlyDigits(value).slice(0, 11);
  return digits
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d{1,2})$/, '.$1-$2');
}

export function formatPhone(value) {
  const digits = onlyDigits(value).slice(0, 11);
  if (digits.length <= 2) return digits.length ? `(${digits}` : '';
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

export function formatCep(value) {
  const digits = onlyDigits(value).slice(0, 8);
  return digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
}

// --- Validadores (true quando válido) --------------------------------------

/** RN-02: formato de e-mail com até 254 caracteres. */
export function isValidEmail(value) {
  return value.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/** RN-03: 11 dígitos com dígitos verificadores válidos. */
export function isValidCpf(value) {
  const digits = onlyDigits(value);
  if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false;
  const numbers = [...digits].map(Number);
  const checkDigit = (length) => {
    const sum = numbers
      .slice(0, length)
      .reduce((total, number, index) => total + number * (length + 1 - index), 0);
    const rest = sum % 11;
    return rest < 2 ? 0 : 11 - rest;
  };
  return checkDigit(9) === numbers[9] && checkDigit(10) === numbers[10];
}

/** RN-04: 8 a 128 caracteres, com maiúscula, número e caractere especial. */
export function isValidPassword(value) {
  return (
    value.length >= 8 &&
    value.length <= 128 &&
    /\p{Lu}/u.test(value) &&
    /\d/.test(value) &&
    /[^\p{L}\p{N}\s]/u.test(value)
  );
}

/** RN-05: 3 a 30 caracteres; minúsculas, números e _, começando por letra. */
export function isValidUsername(value) {
  return /^[a-z][a-z0-9_]{2,29}$/.test(value);
}

/** RN-07: celular com DDD, 11 dígitos, terceiro dígito 9. */
export function isValidPhone(value) {
  return /^\d{2}9\d{8}$/.test(onlyDigits(value));
}

/** RN-08: CEP com 8 dígitos (só o formato é conferido). */
export function isValidCep(value) {
  return onlyDigits(value).length === 8;
}

// --- Formulário ------------------------------------------------------------

export const EMPTY_REGISTRATION = {
  full_name: '',
  username: '',
  email: '',
  password: '',
  cpf: '',
  phone: '',
  cep: '',
  street: '',
  number: '',
  complement: '',
  neighborhood: '',
  city: '',
  state: '',
};

const REQUIRED = 'Campo obrigatório.';

function checkText(value, maxLength, { required = true } = {}) {
  const text = value.trim();
  if (!text) return required ? REQUIRED : null;
  if (text.length > maxLength) return `Informe no máximo ${maxLength} caracteres.`;
  return null;
}

/** Retorna { campo: mensagem } com os erros encontrados; vazio quando tudo é válido. */
export function validateRegistration(values) {
  const errors = {};
  const set = (field, message) => {
    if (message) errors[field] = message;
  };

  set('full_name', checkText(values.full_name, 120));

  const username = values.username.trim();
  set(
    'username',
    !username
      ? REQUIRED
      : !isValidUsername(username) &&
          'Use de 3 a 30 caracteres: letras minúsculas, números e _, começando por letra.',
  );

  const email = values.email.trim();
  set('email', !email ? REQUIRED : !isValidEmail(email) && 'E-mail inválido.');

  set(
    'password',
    !values.password
      ? REQUIRED
      : !isValidPassword(values.password) &&
          'Use de 8 a 128 caracteres, com maiúscula, número e símbolo.',
  );

  set('cpf', !values.cpf.trim() ? REQUIRED : !isValidCpf(values.cpf) && 'CPF inválido.');
  set(
    'phone',
    !values.phone.trim()
      ? REQUIRED
      : !isValidPhone(values.phone) && 'Informe um telefone celular com DDD.',
  );
  set(
    'cep',
    !values.cep.trim() ? REQUIRED : !isValidCep(values.cep) && 'Informe um CEP com 8 dígitos.',
  );

  set('street', checkText(values.street, 100));
  set('number', checkText(values.number, 10));
  set('complement', checkText(values.complement, 60, { required: false }));
  set('neighborhood', checkText(values.neighborhood, 100));
  set('city', checkText(values.city, 100));
  set('state', !values.state ? REQUIRED : !UF_OPTIONS.includes(values.state) && 'UF inválida.');

  return errors;
}

/** Corpo de POST /api/auth/register: sem máscaras e sem espaços nas pontas. */
export function toRegistrationPayload(values) {
  const complement = values.complement.trim();
  return {
    full_name: values.full_name.trim(),
    username: values.username.trim(),
    email: values.email.trim(),
    password: values.password,
    cpf: onlyDigits(values.cpf),
    phone: onlyDigits(values.phone),
    cep: onlyDigits(values.cep),
    street: values.street.trim(),
    number: values.number.trim(),
    ...(complement ? { complement } : {}),
    neighborhood: values.neighborhood.trim(),
    city: values.city.trim(),
    state: values.state,
  };
}
