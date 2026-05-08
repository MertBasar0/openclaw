#!/usr/bin/env python3
import argparse, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    d = json.loads(Path(args.input).read_text(encoding='utf-8'))
    cats = {}
    for o in d['objects']:
        cat = o.get('customProperties', {}).get('ceviz_category', 'uncategorized')
        cats[cat] = cats.get(cat, 0) + 1
    lines = [
        '# Blender/Bonsai PoC Scene Report',
        '',
        f"- Source: {d['source']['tool']} {d['source']['version']}",
        f"- Mesh objects: {d['scene']['meshObjectCount']}",
        f"- Materials: {d['scene']['materialCount']}",
        f"- Collections: {', '.join(d['collections']) or 'none'}",
        f"- Bounds size: {d['scene']['bounds']['size'] if d['scene']['bounds'] else 'n/a'}",
        '',
        '## Semantic categories',
    ]
    for k, v in sorted(cats.items()):
        lines.append(f'- {k}: {v}')
    lines += ['', '## Initial observations']
    if cats.get('wall', 0) >= 4 and cats.get('slab', 0) >= 1:
        lines.append('- Basic enclosed-room structure is present.')
    if cats.get('window', 0) == 0:
        lines.append('- No window semantic object detected.')
    if d['diagnostics']:
        lines.append('- Diagnostics present; inspect JSON for object-level notes.')
    else:
        lines.append('- No object-level warnings in the first-pass extractor.')
    Path(args.output).write_text('\n'.join(lines) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
