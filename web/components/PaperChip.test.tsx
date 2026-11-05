import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PaperChip } from './PaperChip';

describe('PaperChip', () => {
  it('reads Paper with the default tooltip', () => {
    const html = renderToStaticMarkup(<PaperChip size="sm" />);
    expect(html).toContain('>Paper</span>');
    expect(html).toContain('data-tip="Paper trade: simulated, no real money"');
    // The flask is decoration; the word carries the meaning.
    expect(html).toContain('aria-hidden="true"');
  });
  it('carries a caller tooltip instead, and still reads Paper', () => {
    const html = renderToStaticMarkup(<PaperChip size="sm" tip="Claude twin of F4" />);
    expect(html).toContain('data-tip="Claude twin of F4"');
    expect(html).toContain('>Paper</span>');
  });
});
