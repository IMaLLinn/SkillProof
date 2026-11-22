import { describe, expect, test } from 'vitest'
import { validateEmail, validateName, validatePassword } from '../src/authValidation'

describe('validateEmail', () => {
  test('accepts an address with a local part and a dotted domain', () => {
    expect(validateEmail('Learner+notes@example.org')).toBe('')
  })

  test('rejects missing parts, multiple at signs, and whitespace', () => {
    for (const address of ['', 'learner', '@example.org', 'learner@', 'learner@example',
      'learner@example.', 'learner@@example.org', 'learner @example.org', ' learner@example.org']) {
      expect(validateEmail(address), address).toBe('请输入有效的电子邮箱地址')
    }
  })

  test('accepts consecutive dots and long local parts under the frontend rule', () => {
    expect(validateEmail('learner..notes@example.org')).toBe('')
    expect(validateEmail(`learner@example..org`)).toBe('')
    expect(validateEmail(`${'a'.repeat(65)}@example.org`)).toBe('')
  })
})

describe('validateName', () => {
  test('accepts visible Unicode characters and counts code points', () => {
    for (const name of ['林', '林 小雨', '2', '·', '🧩'.repeat(50)]) {
      expect(validateName(name), name).toBe('')
    }
  })

  test('rejects names outside the 1 to 50 character range', () => {
    expect(validateName('')).toBe('姓名需为 1–50 个字符')
    expect(validateName('🧩'.repeat(51))).toBe('姓名需为 1–50 个字符')
  })

  test('rejects control and invisible formatting characters', () => {
    for (const character of ['\t', '\u200b', '\u2028', '\u2029']) {
      expect(validateName(`林${character}小雨`)).toBe('姓名不能包含控制字符或不可显示字符')
    }
  })

  test('requires at least one visible letter, number, punctuation mark, or symbol', () => {
    expect(validateName('   ')).toBe('姓名需包含可显示字符')
    expect(validateName('\u0301')).toBe('姓名需包含可显示字符')
  })
})

describe('validatePassword', () => {
  test('accepts 15 and 128 code points including multibyte characters', () => {
    expect(validatePassword('🧩'.repeat(15))).toBe('')
    expect(validatePassword('🧩'.repeat(128))).toBe('')
  })

  test('rejects 14 and 129 code points', () => {
    expect(validatePassword('🧩'.repeat(14))).toBe('密码需为 15–128 个字符')
    expect(validatePassword('🧩'.repeat(129))).toBe('密码需为 15–128 个字符')
  })

  test('rejects all-whitespace passwords and allows spaces around visible content', () => {
    expect(validatePassword(' \t\n'.repeat(5))).toBe('密码不能全部为空白')
    expect(validatePassword(`${' '.repeat(13)}字 `)).toBe('')
  })
})
