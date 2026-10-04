import { describe, expect, it } from 'vitest';
import { escapeHtml, renderInline, renderMarkdown } from './markdown';

describe('escaping', () => {
  it('never passes raw HTML through', () => {
    expect(renderMarkdown('<script>alert(1)</script>')).toBe('<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>');
    expect(renderMarkdown('**<b>x</b>**')).toBe('<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>');
    expect(renderMarkdown('# <img src=x onerror=alert(1)>')).toBe('<h3>&lt;img src=x onerror=alert(1)&gt;</h3>');
    expect(escapeHtml(`&<>"'`)).toBe('&amp;&lt;&gt;&quot;&#39;');
  });

  it('links http(s) only, escaped, opening in a new tab', () => {
    expect(renderInline('[SSRN](https://papers.ssrn.com/a?b=1&c=2)')).toBe(
      '<a href="https://papers.ssrn.com/a?b=1&amp;c=2" rel="noopener noreferrer" target="_blank">SSRN</a>',
    );
    expect(renderInline('[x](javascript:alert(1))')).toBe('[x](javascript:alert(1))');
    expect(renderInline('[x](data:text/html,hi)')).toBe('[x](data:text/html,hi)');
    const sneaky = renderInline('[x](https://a.com/"onmouseover=alert(1))');
    expect(sneaky).toContain('&quot;onmouseover');
    expect(sneaky).not.toMatch(/href="[^"]*"onmouseover/);
  });
});

describe('inline', () => {
  it('renders bold, italic and code, leaving code contents alone', () => {
    expect(renderInline('**bold** and *it*')).toBe('<strong>bold</strong> and <em>it</em>');
    expect(renderInline('use `a*b*c` here')).toBe('use <code>a*b*c</code> here');
    expect(renderInline('2 * 3 * 4')).toBe('2 * 3 * 4');
  });
});

describe('blocks', () => {
  it('shifts headings down two levels and only knows three', () => {
    expect(renderMarkdown('# A\n## B\n### 2026-10-04\nText')).toBe(
      '<h3>A</h3>\n<h4>B</h4>\n<h5>2026-10-04</h5>\n<p>Text</p>',
    );
    expect(renderMarkdown('#### x')).toBe('<p>#### x</p>');
  });

  it('joins paragraph lines and splits on blank lines', () => {
    expect(renderMarkdown('a\nb\n\nc')).toBe('<p>a b</p>\n<p>c</p>');
    expect(renderMarkdown('a\r\nb')).toBe('<p>a b</p>');
  });

  it('renders bullet and numbered lists, with indented continuations', () => {
    expect(renderMarkdown('- a\n- b\n\n1. x\n2. y')).toBe('<ul><li>a</li><li>b</li></ul>\n<ol><li>x</li><li>y</li></ol>');
    expect(renderMarkdown('- a\n  more\n- b\nafter')).toBe('<ul><li>a more</li><li>b</li></ul>\n<p>after</p>');
  });

  it('renders pipe tables with alignment and inline markup', () => {
    const md = '| Variant | CAGR |\n|---|---:|\n| V1 | 7.6% |\n| V2 | **8%** |';
    expect(renderMarkdown(md)).toBe(
      '<table><thead><tr><th>Variant</th><th style="text-align:right">CAGR</th></tr></thead>' +
        '<tbody><tr><td>V1</td><td style="text-align:right">7.6%</td></tr>' +
        '<tr><td>V2</td><td style="text-align:right"><strong>8%</strong></td></tr></tbody></table>',
    );
  });

  it('pads short rows, ends a table at a blank line, and leaves a lone pipe as text', () => {
    expect(renderMarkdown('| a | b |\n| --- | --- |\n| 1 |\n\nnext')).toBe(
      '<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td></td></tr></tbody></table>\n<p>next</p>',
    );
    expect(renderMarkdown('a | b')).toBe('<p>a | b</p>');
  });

  it('escapes table cells', () => {
    expect(renderMarkdown('| <i>x</i> |\n|---|\n| y |')).toContain('<th>&lt;i&gt;x&lt;/i&gt;</th>');
  });
});
