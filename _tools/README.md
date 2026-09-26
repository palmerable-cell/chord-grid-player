# Web version (YouTube-only) of the chord-grid player — build & hosting notes

The site root is `/workspace/chord-player-web/` : `index.html` (song list + About), `songs.json` (manifest),
`songs/<title-slug>-<videoId>/` with `index.html` (player), `chart.png` (+ any extra chart screens, copied
byte-for-byte = unmodified) and `thumb.jpg` (list thumbnail). **No audio files**: every page plays the original
YouTube video through the IFrame Player API. Credit strip (Martin Gioani — guitare-improvisation.com, CC BY-NC-ND,
channel link, link to the original video) on every page, About note in every footer and on the list page.
This `_tools/` folder is NOT part of the published site (GitHub Pages/Jekyll skips folders starting with `_`;
if you deploy another way, just don't upload `_tools/`).

## Rebuild
    # 3-song pilot (current contents)
    python3 build_web.py --src /workspace/chord-player-pilot --out /workspace/chord-player-web
    # full collection, once /workspace/chord-player/ is finished
    python3 build_web.py --src /workspace/chord-player --out /workspace/chord-player-web
    #   add --optimize-png if the total goes over 900 MB (lossless re-encode, pixels verified identical)
The script only reads `--src`; it regenerates `songs/`, `index.html`, `songs.json` (songs that failed or are still
being processed are skipped and listed; `last_build.json` has the details). It needs Python 3 (+ Pillow only for
thumbnails missing in the source; otherwise ffmpeg is used). Exit code 2 = a file > 50 MB or total > 900 MB.
A trial run against the half-finished collection (397 songs) gave 210.6 MB, i.e. ~0.53 MB/song →
about 640 MB for all ~1,205 songs (largest single file so far: 5.6 MB).

## Test locally
    python3 serve.py 8811        # serves the site root (parent of _tools) at http://127.0.0.1:8811/
    python3 test_web.py          # headless Chrome (needs playwright): list, YouTube mode, play, marker, jump, loop, 75 %
YouTube refuses to play from `file://` (error 153), so always test over http.

## Hosting (nothing has been published)
GitHub Pages (free for public repos, HTTPS, fine for this size: site < 1 GB, files < 100 MB hard limit / 50 MB warning,
soft 100 GB/month bandwidth). Steps, once someone is logged in:
1. `gh auth login` (currently: not logged in on the box) — or create the repo in the browser as palmerable-cell.
2. `gh repo create palmerable-cell/chord-charts --public` ; in the site folder: `git init`, add everything except
   `_tools/` (or keep it, Jekyll will skip it), commit, push to `main`.
3. Repo Settings → Pages → Deploy from branch `main` / root. URL: https://palmerable-cell.github.io/chord-charts/
(The GitHub connector available to the assistant has no create-repository / push-files tools, so it can't do this.)
Alternatives with a drag-and-drop upload of the folder: Netlify, Cloudflare Pages (25 MiB/file, 20,000 files), Vercel.
