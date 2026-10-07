import { describe, expect, it } from 'vitest';
import { extractJsonObject } from './extractJson';

describe('extractJsonObject', () => {
  it('reads a bare object', () => {
    expect(extractJsonObject('{"ticker":"MU"}')).toEqual({ ticker: 'MU' });
  });
  it('strips a ```json fence', () => {
    expect(extractJsonObject('```json\n{"ticker":"MU"}\n```')).toEqual({ ticker: 'MU' });
  });
  it('drops chatter before and after, keeping nested braces', () => {
    expect(extractJsonObject('Here it is: {"fills":[{"shares":"5"}]} Let me know!')).toEqual({
      fills: [{ shares: '5' }],
    });
  });
  it('returns null for nothing, malformed JSON, arrays and scalars', () => {
    expect(extractJsonObject('')).toBeNull();
    expect(extractJsonObject(null)).toBeNull();
    expect(extractJsonObject('no json here')).toBeNull();
    expect(extractJsonObject('{"ticker": "MU",}')).toBeNull();
    expect(extractJsonObject('[1, 2]')).toBeNull();
    expect(extractJsonObject('} {')).toBeNull();
  });
});
