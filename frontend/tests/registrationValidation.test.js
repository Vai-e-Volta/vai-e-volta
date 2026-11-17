import { describe, expect, it } from 'vitest';
import {
  EMPTY_REGISTRATION,
  formatCep,
  formatCpf,
  formatPhone,
  isValidCep,
  isValidCpf,
  isValidEmail,
  isValidPassword,
  isValidPhone,
  isValidUsername,
  toRegistrationPayload,
  validateRegistration,
} from '../src/utils/registrationValidation';

// Dados fictícios. 529.982.247-25 é um CPF de exemplo com dígitos verificadores válidos.
const VALID = {
  full_name: 'Ana Teste',
  username: 'ana_teste',
  email: 'ana@example.com',
  password: 'Senha@123',
  cpf: '529.982.247-25',
  phone: '(53) 99999-0000',
  cep: '96200-000',
  street: 'Rua Exemplo',
  number: '100',
  complement: '',
  neighborhood: 'Centro',
  city: 'Rio Grande',
  state: 'RS',
};

describe('UT-REG-01 e-mail (RN-02)', () => {
  it.each(['ana@example.com', 'a.b+c@sub.example.com.br'])('aceita %s', (email) => {
    expect(isValidEmail(email)).toBe(true);
  });

  it.each(['', 'ana', 'ana@', 'ana@example', 'ana @example.com'])('recusa "%s"', (email) => {
    expect(isValidEmail(email)).toBe(false);
  });

  it('recusa e-mail com mais de 254 caracteres', () => {
    expect(isValidEmail(`${'a'.repeat(243)}@example.com`)).toBe(false);
  });
});

describe('UT-REG-02 CPF (RN-03)', () => {
  it.each(['529.982.247-25', '52998224725', '111.444.777-35'])('aceita %s', (cpf) => {
    expect(isValidCpf(cpf)).toBe(true);
  });

  it.each(['529.982.247-24', '111.111.111-11', '00000000000', '5299822472', '123'])(
    'recusa %s',
    (cpf) => {
      expect(isValidCpf(cpf)).toBe(false);
    },
  );
});

describe('UT-REG-03 senha (RN-04)', () => {
  it.each(['Senha@123', 'Ab1!abcd', `A1!${'a'.repeat(125)}`])('aceita senha válida', (pwd) => {
    expect(isValidPassword(pwd)).toBe(true);
  });

  it.each([
    ['curta', 'Ab1!abc'],
    ['longa', `A1!${'a'.repeat(126)}`],
    ['sem maiúscula', 'senha@123'],
    ['sem número', 'Senha@abc'],
    ['sem caractere especial', 'Senha1234'],
  ])('recusa senha %s', (_reason, pwd) => {
    expect(isValidPassword(pwd)).toBe(false);
  });
});

describe('UT-REG-04 telefone (RN-07)', () => {
  it.each(['(53) 99999-0000', '53999990000', '53 99999-0000'])('aceita %s', (phone) => {
    expect(isValidPhone(phone)).toBe(true);
  });

  it.each(['(53) 3333-0000', '5333330000', '539999900001', '(53) 89999-0000'])(
    'recusa %s',
    (phone) => {
      expect(isValidPhone(phone)).toBe(false);
    },
  );
});

describe('usuário (RN-05) e CEP (RN-08)', () => {
  it.each(['ana', 'ana_teste', 'a12', 'a'.repeat(30)])('aceita usuário %s', (username) => {
    expect(isValidUsername(username)).toBe(true);
  });

  it.each(['an', 'Ana', '1ana', '_ana', 'ana-teste', 'a'.repeat(31)])(
    'recusa usuário %s',
    (username) => {
      expect(isValidUsername(username)).toBe(false);
    },
  );

  it('confere só o formato do CEP', () => {
    expect(isValidCep('96200-000')).toBe(true);
    expect(isValidCep('9620000')).toBe(false);
  });
});

describe('máscaras', () => {
  it('formata CPF, telefone e CEP enquanto digita', () => {
    expect(formatCpf('52998224725')).toBe('529.982.247-25');
    expect(formatCpf('5299')).toBe('529.9');
    expect(formatCpf('529.982.247-251')).toBe('529.982.247-25');
    expect(formatPhone('53999990000')).toBe('(53) 99999-0000');
    expect(formatPhone('539')).toBe('(53) 9');
    expect(formatPhone('5')).toBe('(5');
    expect(formatPhone('')).toBe('');
    expect(formatCep('96200000')).toBe('96200-000');
    expect(formatCep('962')).toBe('962');
  });
});

describe('validateRegistration', () => {
  it('não aponta erros em dados válidos', () => {
    expect(validateRegistration(VALID)).toEqual({});
  });

  it('aponta todos os obrigatórios vazios, exceto o complemento', () => {
    const errors = validateRegistration(EMPTY_REGISTRATION);

    expect(Object.keys(errors).sort()).toEqual(
      Object.keys(EMPTY_REGISTRATION)
        .filter((field) => field !== 'complement')
        .sort(),
    );
    expect(errors.full_name).toBe('Campo obrigatório.');
  });

  it('confere tamanhos máximos do nome e do endereço (RN-06, RN-08)', () => {
    const errors = validateRegistration({
      ...VALID,
      full_name: 'a'.repeat(121),
      number: '1'.repeat(11),
      complement: 'a'.repeat(61),
    });

    expect(errors).toEqual({
      full_name: 'Informe no máximo 120 caracteres.',
      number: 'Informe no máximo 10 caracteres.',
      complement: 'Informe no máximo 60 caracteres.',
    });
  });

  it('aponta formatos inválidos', () => {
    const errors = validateRegistration({
      ...VALID,
      username: 'Ana',
      email: 'ana@',
      password: 'fraca',
      cpf: '111.111.111-11',
      phone: '(53) 3333-0000',
      cep: '962',
      state: 'XX',
    });

    expect(Object.keys(errors).sort()).toEqual(
      ['cep', 'cpf', 'email', 'password', 'phone', 'state', 'username'].sort(),
    );
  });
});

describe('toRegistrationPayload', () => {
  it('remove máscaras e espaços e omite complemento vazio', () => {
    expect(toRegistrationPayload({ ...VALID, full_name: '  Ana Teste ' })).toEqual({
      full_name: 'Ana Teste',
      username: 'ana_teste',
      email: 'ana@example.com',
      password: 'Senha@123',
      cpf: '52998224725',
      phone: '53999990000',
      cep: '96200000',
      street: 'Rua Exemplo',
      number: '100',
      neighborhood: 'Centro',
      city: 'Rio Grande',
      state: 'RS',
    });
  });

  it('envia o complemento quando preenchido e não altera a senha', () => {
    const payload = toRegistrationPayload({
      ...VALID,
      complement: ' apto 2 ',
      password: ' A1!aaaaa ',
    });

    expect(payload.complement).toBe('apto 2');
    expect(payload.password).toBe(' A1!aaaaa ');
  });
});
