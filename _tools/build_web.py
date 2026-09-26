#!/usr/bin/env python3
"""Build the public WEB version (YouTube-only, no audio files) of the chord-grid player.

  python3 build_web.py --src /workspace/chord-player --out /workspace/chord-player-web

--src  a built collection: any folder whose sub-folders each contain index.html (the player,
       with `const SONG = {...};` embedded) + song.json + the chart image(s) listed in SONG.screens.
       Works for the 3-song pilot (/workspace/chord-player-pilot) and the full collection
       (/workspace/chord-player). The source is only READ.
--out  the site root. `songs/`, `index.html`, `songs.json` are regenerated each run
       (`_tools/` is left alone). Songs go to songs/<title-slug>-<videoId>/.

Every song page is the source player page with a few text patches (each one is checked; a page whose
template doesn't match is skipped and reported): local audio removed (SONG.audio = [] -> the
player picks YouTube mode by itself), the Local/YouTube switch hidden, YouTube player at least
356x200 px, credit strip + About note + link back to the list. Chart images are copied
byte-for-byte (optionally re-encoded LOSSLESSLY with --optimize-png, pixel-identical check).
Size limits (GitHub Pages): --max-file-mb 50 per file, --max-total-mb 900 total -> exit code 2
if exceeded.
"""
import argparse, csv, html, json, os, re, shutil, subprocess, sys, unicodedata

CHANNEL = 'https://www.youtube.com/@guitareimprovisation'
SITE = 'https://www.guitare-improvisation.com'
LICENCE = 'https://creativecommons.org/licenses/by-nc-nd/4.0/'
ABOUT = ('A free, non-commercial practice tool. It plays the <b>original YouTube videos</b> from Martin Gioani\'s channel '
         '(no audio or video is re-hosted here) next to his <b>original, unmodified</b> chord charts, with a marker that moves to '
         'each chord 1 s before it is played. Not affiliated with or endorsed by guitare-improvisation.com; all credit for the '
         'backing tracks and charts goes to Martin Gioani. If you like them, subscribe to the channel and visit the website.')

def slugify(s, vid):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()[:60].strip('-')
    return (s or 'song') + '-' + vid

def esc(s): return html.escape(str(s), quote=True)

def credit_html(song):
    return (f'<div class="credit">Backing tracks and charts by <b>Martin Gioani</b> — '
            f'<a href="{SITE}" target="_blank" rel="noopener">guitare-improvisation.com</a> '
            f'(<a href="{LICENCE}" target="_blank" rel="noopener">CC BY-NC-ND</a>) · '
            f'<a href="{CHANNEL}" target="_blank" rel="noopener">YouTube channel</a> · '
            f'Original video: <a href="{esc(song["url"])}" target="_blank" rel="noopener">{esc(song.get("videoTitle") or song["title"])}</a></div>')

CSS_ADD = '''.credit{background:#15120a;border-bottom:1px solid #3a3018;color:#e8d9b0;font-size:13px;padding:5px 12px;text-align:center}
.credit a{color:#ffc83c} .back{color:#ffc83c!important;text-decoration:none;font-size:13px;border:1px solid #3a3018;border-radius:5px;padding:3px 8px}
.about{max-width:900px;margin:4px auto 0;color:#7d7d7d;font-size:11px;line-height:1.45}
'''

def patch_page(src_html, song, stage_margin):
    """Return the web page or raise ValueError(reason)."""
    h = src_html
    def sub(pat, rep, flags=0, count=1, literal=False, optional=False):
        nonlocal h
        if literal:
            n = h.count(pat)
            if n != count:
                if optional and n == 0: return
                raise ValueError(f'patch target found {n}x (expected {count}): {pat[:60]!r}')
            h = h.replace(pat, rep)
        else:
            new, n = re.subn(pat, rep, h, flags=flags)
            if n != count:
                if optional and n == 0: return
                raise ValueError(f'patch regex matched {n}x (expected {count}): {pat[:60]!r}')
            h = new
    # data: the page's own SONG, without local audio
    m = re.search(r'^const SONG = (\{.*\});\s*$', h, flags=re.M)
    if not m: raise ValueError('SONG line not found')
    data = json.loads(m.group(1)); data['audio'] = []
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    h = h[:m.start()] + 'const SONG = ' + js + ';' + h[m.end():]
    title = data['title']
    sub(r'<title>.*?</title>', lambda _: f'<title>{esc(title)} — chord-chart play-along (backing track by Martin Gioani)</title>')
    sub(r'(<meta name="viewport"[^>]*>)', lambda mm: mm.group(1) + '\n<meta name="referrer" content="strict-origin-when-cross-origin">\n<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22%3E%3Crect x=%221%22 y=%224%22 width=%2214%22 height=%228%22 rx=%221%22 fill=%22%23ffc83c%22/%3E%3C/svg%3E">'
        f'\n<meta name="description" content="{esc(title)}: play along with Martin Gioani\'s backing track (guitare-improvisation.com) — the original YouTube video with the chord chart, a moving bar marker, click-to-jump, loop and slow-down.">')
    sub('#ytwrap{width:200px;height:113px;transition:all .2s}', '#ytwrap{width:356px;height:200px;transition:all .2s}', literal=True)
    sub('#ytbox.big #ytwrap{width:320px;height:180px}', '#ytbox.big #ytwrap{width:480px;height:270px}', literal=True)
    sub(r'100vh - \d+px', f'100vh - {stage_margin}px')
    sub('</style>', CSS_ADD + '</style>', literal=True)
    sub(r'<header>\s*<h1>', '<header>\n  <a class="back" href="../../index.html" title="All songs">← All songs</a>\n  <h1>')
    sub(r'<span class="lbl">Audio source</span>\s*<span class="seg" id="modeSeg">(.*?)</span>\s*</header>',
        lambda mm: '<span class="lbl">Audio: original YouTube video</span>\n  <span class="seg" id="modeSeg" style="display:none">' + mm.group(1) + '</span>\n</header>\n' + credit_html(data), flags=re.S)
    sub('<span>YouTube player</span>', '<span>Original video (YouTube)</span>', literal=True)
    sub(r'<footer>.*?</footer>', lambda _: (
        '<footer>Backing track and chart by Martin Gioani — '
        f'<a href="{SITE}" target="_blank" rel="noopener">guitare-improvisation.com</a> '
        f'(<a href="{LICENCE}" target="_blank" rel="noopener">CC BY-NC-ND 4.0</a>) · <a id="vlink" target="_blank" rel="noopener">original video</a> · '
        f'<a href="{CHANNEL}" target="_blank" rel="noopener">channel</a> · <span id="tsrc"></span>'
        f'<div class="about"><b>About:</b> {ABOUT} <a href="../../index.html#about">More</a></div></footer>'), flags=re.S)
    sub('<audio id="audio" preload="auto"></audio>', '<audio id="audio" preload="none"></audio>', literal=True)
    sub("'Could not load the YouTube player (offline?). Use Local audio.'", "'Could not load the YouTube player (offline, or blocked by an extension?).'", literal=True, optional=True)
    sub("'Note: YouTube mode usually needs this page served over http(s) (see README).'", "'Note: the YouTube player needs this page opened from a web server (http/https), not as a local file.'", literal=True, optional=True)
    # sanity: things the script relies on
    for must in ('SONG.audio', "setMode('yt', true)", 'id="vlink"', 'id="tsrc"', 'id="mLocal"', 'id="yt"'):
        if must not in h: raise ValueError(f'expected {must!r} in page')
    return h, data

def make_thumb(src_png, dst_jpg):
    try:
        from PIL import Image
        im = Image.open(src_png).convert('RGB'); w = 320
        im.resize((w, round(w * im.height / im.width)), Image.LANCZOS).save(dst_jpg, quality=72)
    except ImportError:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src_png, '-vf', 'scale=320:-2', '-q:v', '5', dst_jpg], check=True)

def optimize_png_lossless(path):
    """Re-encode a PNG losslessly (max zlib); keep only if smaller AND pixel-identical. Returns bytes saved."""
    from PIL import Image
    import numpy as np, io
    im = Image.open(path); im.load(); a = np.asarray(im)
    buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
    b = np.asarray(Image.open(io.BytesIO(buf.getvalue())))
    old = os.path.getsize(path)
    if buf.tell() < old and a.shape == b.shape and (a == b).all():
        open(path, 'wb').write(buf.getvalue()); return old - buf.tell()
    return 0

def load_flags(src):
    f = os.path.join(src, '_report', 'flagged.csv'); out = {}
    if os.path.exists(f):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            reasons = [x for x in (r.get('reasons') or '').split(' | ') if x and 'auto-fixed' not in x and 'estimated' not in x]
            if reasons: out[r.get('folder')] = reasons
    return out

def fmt_dur(d):
    if not d: return ''
    d = int(round(d)); return f'{d // 60}:{d % 60:02d}'

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--optimize-png', action='store_true', help='lossless PNG re-encode (pixel-identical) to save space')
    ap.add_argument('--max-total-mb', type=float, default=900); ap.add_argument('--max-file-mb', type=float, default=50)
    ap.add_argument('--stage-margin', type=int, default=300, help='px of viewport height reserved for header/controls')
    ap.add_argument('--title', default='Play-along chord charts')
    a = ap.parse_args()
    src, out = os.path.abspath(a.src), os.path.abspath(a.out)
    if out == src or out.startswith(src + os.sep): sys.exit('--out must not be inside --src')
    here = os.path.dirname(os.path.abspath(__file__))
    flags = load_flags(src)
    songs_dir = os.path.join(out, 'songs'); tmp_dir = songs_dir + '.tmp'
    shutil.rmtree(tmp_dir, ignore_errors=True); os.makedirs(tmp_dir)
    entries, skipped, seen = [], [], {}
    for folder in sorted(os.listdir(src)):
        fp = os.path.join(src, folder)
        if folder.startswith(('_', '.')) or not os.path.isdir(fp): continue
        if not (os.path.exists(f'{fp}/index.html') and os.path.exists(f'{fp}/song.json')):
            skipped.append((folder, 'no index.html/song.json')); continue
        try:
            page, song = patch_page(open(f'{fp}/index.html', encoding='utf-8').read(), None, a.stage_margin)
            imgs = [s['image'] for s in song['screens']]
            missing = [i for i in imgs if i.startswith('data:') or not os.path.exists(os.path.join(fp, i))]
            if missing: raise ValueError(f'missing chart image(s) {missing[:2]}')
        except Exception as e:
            skipped.append((folder, str(e))); continue
        slug = slugify(song['title'], song['videoId'])
        if slug in seen: skipped.append((folder, f'duplicate of {seen[slug]}')); continue
        seen[slug] = folder
        d = os.path.join(tmp_dir, slug); os.makedirs(d)
        for i in dict.fromkeys(imgs):
            os.makedirs(os.path.dirname(os.path.join(d, i)) or d, exist_ok=True)
            shutil.copyfile(os.path.join(fp, i), os.path.join(d, i))
        if os.path.exists(f'{fp}/thumb.jpg'): shutil.copyfile(f'{fp}/thumb.jpg', f'{d}/thumb.jpg')
        else: make_thumb(os.path.join(fp, imgs[0]), f'{d}/thumb.jpg')
        open(f'{d}/index.html', 'w', encoding='utf-8').write(page)
        entries.append(dict(slug=slug, t=song['title'], v=song.get('videoTitle') or '', y=song['videoId'], k=song.get('key') or '',
                            b=song.get('bpm'), d=round(song.get('duration') or 0), e=bool(song.get('estimated')), n=len(song['screens']),
                            f='; '.join(flags.get(folder, []))[:200], src=folder))
    saved = 0
    if a.optimize_png:
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                if f.endswith('.png'): saved += optimize_png_lossless(os.path.join(root, f))
    shutil.rmtree(songs_dir, ignore_errors=True); os.rename(tmp_dir, songs_dir)
    entries.sort(key=lambda s: (s['t'].lower(), s['v'].lower()))
    manifest = [dict(slug=e['slug'], title=e['t'], videoTitle=e['v'], videoId=e['y'], url=f'https://www.youtube.com/watch?v={e["y"]}',
                     key=e['k'], bpm=e['b'], duration=e['d'], estimated=e['e'], screens=e['n'], page=f'songs/{e["slug"]}/index.html') for e in entries]
    json.dump(manifest, open(os.path.join(out, 'songs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    tpl = open(os.path.join(here, 'index_template.html'), encoding='utf-8').read()
    lst = [dict(s=e['slug'], t=e['t'], v=e['v'], y=e['y'], k=e['k'], b=e['b'] and int(float(e['b'])), d=fmt_dur(e['d']), e=e['e'], n=e['n'], f=e['f']) for e in entries]
    keys = sorted({e['k'] for e in entries if e['k']})
    page = (tpl.replace('/*__SONGS__*/[]', json.dumps(lst, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
               .replace('/*__KEYS__*/[]', json.dumps(keys, ensure_ascii=False)).replace('__COUNT__', str(len(entries)))
               .replace('__TITLE__', esc(a.title)).replace('__ABOUT__', ABOUT))
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(page)
    # size report (published files only: skip _tools and dot-files)
    total, big = 0, []
    for root, dirs, files in os.walk(out):
        rel = os.path.relpath(root, out)
        if rel.split(os.sep)[0].startswith(('_', '.')) and rel != '.': continue
        for f in files:
            if f.startswith('.') and rel == '.': continue
            s = os.path.getsize(os.path.join(root, f)); total += s
            if s > a.max_file_mb * 1e6: big.append((os.path.join(rel, f), s))
    print(f'songs built: {len(entries)}   skipped: {len(skipped)}   published size: {total / 1e6:.1f} MB'
          + (f'   (lossless PNG optimisation saved {saved / 1e6:.1f} MB)' if a.optimize_png else ''))
    for f, r in skipped[:50]: print('  SKIP', f, '-', r)
    if len(skipped) > 50: print(f'  ... {len(skipped) - 50} more skipped')
    json.dump(dict(built=len(entries), skipped=[dict(folder=f, reason=r) for f, r in skipped], published_bytes=total,
                   files_over_limit=big, src=src), open(os.path.join(here, 'last_build.json'), 'w'), indent=1, ensure_ascii=False)
    bad = False
    if big: print('FILES OVER', a.max_file_mb, 'MB:', big); bad = True
    if total > a.max_total_mb * 1e6: print(f'TOTAL {total/1e6:.0f} MB > {a.max_total_mb} MB (try --optimize-png)'); bad = True
    sys.exit(2 if bad else 0)

if __name__ == '__main__':
    main()
