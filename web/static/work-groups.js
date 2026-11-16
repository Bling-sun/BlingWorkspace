/* Pure library grouping and search; conversations remain owned by their original material. */
(function (root) {
  'use strict';
  function entries(papers, groups) {
    const bySlug = new Map(papers.map(p => [p.slug, p]));
    const hidden = new Set();
    const works = [];
    for (const group of groups || []) {
      const members = group.members.map(m => bySlug.get(m.slug)).filter(Boolean);
      if (!members.length) continue;
      const primary = bySlug.get(group.primary_slug) || members[0];
      members.forEach(m => hidden.add(m.slug));
      works.push({ ...primary, kind: 'work', title: group.title, slug: primary.slug, work_id: group.id, group, members,
        mtime: Math.max(...members.map(m => m.mtime || 0)),
        progress: { ...primary.progress, messages: members.reduce((n, m) => n + (m.progress?.messages || 0), 0) } });
    }
    return [...works, ...papers.filter(p => !hidden.has(p.slug))].sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
  }
  function matches(entry, query, filter) {
    const members = entry.members || [entry];
    if (filter !== 'all' && !members.some(p => filter === 'paper' ? !['repo', 'knowledge'].includes(p.kind) : p.kind === filter)) return false;
    const q = (query || '').trim().toLowerCase();
    if (!q) return true;
    return [entry.title, ...members.flatMap(p => [p.title, p.arxiv_id, p.source_url, p.local_path, p.summary,
      ...(p.authors || []), ...(p.languages || []).map(l => l.name), ...(p.topics || [])])].join(' ').toLowerCase().includes(q);
  }
  root.BlingWorks = { entries, matches };
})(globalThis);
