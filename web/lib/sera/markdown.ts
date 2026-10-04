/**
 * Escape-first markdown -> HTML for lab analysis text.
 *
 * Supported: # / ## / ### headings (rendered h3 / h4 / h5 so the page keeps h1–h2), paragraphs,
 * **bold**, *italic*, `code`, "- " and "1. " lists, pipe tables with a header separator, and
 * [text](http(s) url) links. Nothing else. All source text is HTML-escaped before any markup is
 * added, so raw HTML in the source always renders as text.
 */

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

const LINK = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
const HEADING = /^(#{1,3})\s+(.+)$/;
const UL = /^\s*-\s+(.*)$/;
const OL = /^\s*\d+\.\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

type Align = 'left' | 'center' | 'right' | null;
type List = { tag: 'ul' | 'ol'; items: string[] };

/** Bold and italic on already-escaped text. */
function emphasis(s: string): string {
  return s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*([^*\s][^*]*?)\*/g, '<em>$1</em>');
}

/** Links (http/https only) with emphasis inside and around them, on already-escaped text. */
function linksAndEmphasis(s: string): string {
  let out = '';
  let last = 0;
  for (const m of s.matchAll(LINK)) {
    const at = m.index ?? 0;
    out += emphasis(s.slice(last, at));
    out += `<a href="${m[2]}" rel="noopener noreferrer" target="_blank">${emphasis(m[1])}</a>`;
    last = at + m[0].length;
  }
  return out + emphasis(s.slice(last));
}

/** One line of inline markdown -> HTML. Code spans are left untouched inside. */
export function renderInline(text: string): string {
  return escapeHtml(text)
    .split(/`([^`]+)`/)
    .map((part, i) => (i % 2 === 1 ? `<code>${part}</code>` : linksAndEmphasis(part)))
    .join('');
}

function cells(row: string): string[] {
  let r = row.trim();
  if (r.startsWith('|')) r = r.slice(1);
  if (r.endsWith('|')) r = r.slice(0, -1);
  return r.split('|').map((c) => c.trim());
}

function aligns(separator: string): Align[] {
  return cells(separator).map((c) => {
    const left = c.startsWith(':');
    const right = c.endsWith(':');
    if (left && right) return 'center';
    if (right) return 'right';
    if (left) return 'left';
    return null;
  });
}

function cell(tag: 'th' | 'td', text: string, align: Align): string {
  const style = align ? ` style="text-align:${align}"` : '';
  return `<${tag}${style}>${renderInline(text)}</${tag}>`;
}

class Blocks {
  out: string[] = [];
  para: string[] = [];
  list: List | null = null;

  flushPara(): void {
    if (this.para.length > 0) {
      this.out.push(`<p>${renderInline(this.para.join(' '))}</p>`);
      this.para = [];
    }
  }

  flushList(): void {
    if (this.list) {
      const items = this.list.items.map((it) => `<li>${renderInline(it)}</li>`).join('');
      this.out.push(`<${this.list.tag}>${items}</${this.list.tag}>`);
      this.list = null;
    }
  }

  flush(): void {
    this.flushPara();
    this.flushList();
  }
}

/** Markdown source -> HTML string, safe for dangerouslySetInnerHTML. */
export function renderMarkdown(src: string): string {
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  const b = new Blocks();
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim() === '') {
      b.flush();
      continue;
    }
    const h = HEADING.exec(line);
    if (h) {
      b.flush();
      const level = h[1].length + 2;
      b.out.push(`<h${level}>${renderInline(h[2].trim())}</h${level}>`);
      continue;
    }
    const next = lines[i + 1];
    if (line.includes('|') && next !== undefined && next.includes('|') && TABLE_SEP.test(next)) {
      b.flush();
      const head = cells(line);
      const al = aligns(next);
      const body: string[][] = [];
      let j = i + 2;
      while (j < lines.length && lines[j].trim() !== '' && lines[j].includes('|')) {
        body.push(cells(lines[j]));
        j++;
      }
      i = j - 1;
      const row = (r: string[], tag: 'th' | 'td') =>
        `<tr>${head.map((_, c) => cell(tag, r[c] ?? '', al[c] ?? null)).join('')}</tr>`;
      b.out.push(`<table><thead>${row(head, 'th')}</thead><tbody>${body.map((r) => row(r, 'td')).join('')}</tbody></table>`);
      continue;
    }
    const ul = UL.exec(line);
    const ol = ul ? null : OL.exec(line);
    const item = ul ?? ol;
    if (item) {
      b.flushPara();
      const tag = ul ? 'ul' : 'ol';
      if (b.list && b.list.tag !== tag) b.flushList();
      if (!b.list) b.list = { tag, items: [] };
      b.list.items.push(item[1]);
      continue;
    }
    if (b.list && /^\s{2,}\S/.test(line)) {
      b.list.items[b.list.items.length - 1] += ' ' + line.trim();
      continue;
    }
    b.flushList();
    b.para.push(line.trim());
  }
  b.flush();
  return b.out.join('\n');
}
