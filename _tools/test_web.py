"""Headless Chrome test of the web (YouTube-only) version.  Needs:  python3 serve.py 8811  (site root)."""
import asyncio, json, sys
from playwright.async_api import async_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8811/'
SHOTS = '/workspace/chord-player-web/_tools/test_shots/'
R = {}
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True,
                                    args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context(viewport={'width': 1440, 'height': 820})
        pg = await ctx.new_page()
        logs = []; pg.on('pageerror', lambda e: logs.append('PAGEERROR ' + str(e))); pg.on('console', lambda m: logs.append(m.type + ': ' + m.text))
        await pg.goto(BASE + 'index.html'); await pg.wait_for_timeout(800)
        R['index_count'] = await pg.inner_text('#count')
        R['index_credit'] = await pg.inner_text('.credit')
        await pg.screenshot(path=SHOTS + 'index.png', full_page=True)
        await pg.fill('#q', 'autumn'); await pg.wait_for_timeout(200)
        R['search_autumn'] = await pg.inner_text('#count')
        await pg.click('.card'); await pg.wait_for_load_state('load')
        R['song_url'] = pg.url
        await pg.wait_for_timeout(1500)
        R['mode_auto'] = await pg.evaluate('__player.T && __player.T.name')
        R['mode_switch_visible'] = await pg.is_visible('#modeSeg')
        R['credit'] = await pg.inner_text('.credit')
        try:
            await pg.wait_for_function('__player.ytReady', timeout=30000); R['ytReady'] = True
        except Exception as e: R['ytReady'] = False; R['note'] = await pg.inner_text('#note')
        R['speed_options'] = await pg.evaluate('[...document.getElementById("speed").options].map(o=>o.value)')
        R['yt_iframe_src'] = await pg.evaluate('(document.querySelector("#yt")||{}).src || null')
        R['yt_box_px'] = await pg.evaluate('(r=>[Math.round(r.width),Math.round(r.height)])(document.getElementById("ytwrap").getBoundingClientRect())')
        await pg.screenshot(path=SHOTS + 'song_ready.png')
        # PLAY
        await pg.click('#play'); await pg.wait_for_timeout(6000)
        st = await pg.evaluate('({state: __player.ytReady ? document.querySelector("#yt").contentWindow && 0 : null, playing: __player.T.playing(), t: __player.T.time()})')
        R['after_play_6s'] = st
        R['yt_state'] = await pg.evaluate('(()=>{try{return document.querySelector("#yt") && window.YT && __player.T.playing()}catch(e){return String(e)}})()')
        c1 = await pg.inner_text('#counter'); t1 = await pg.evaluate('__player.T.time()')
        await pg.wait_for_timeout(4000)
        c2 = await pg.inner_text('#counter'); t2 = await pg.evaluate('__player.T.time()')
        R['marker_moves'] = dict(t1=round(t1, 2), c1=c1, t2=round(t2, 2), c2=c2, advanced_s=round(t2 - t1, 2))
        await pg.screenshot(path=SHOTS + 'song_playing.png')
        # CLICK-TO-JUMP: cell 16 (chorus bar 17)
        cells = await pg.query_selector_all('.cell')
        await cells[16].click(); await pg.wait_for_timeout(2500)
        exp = await pg.evaluate('''(()=>{const E=__player.E; const cand=E.filter((e,i)=>e[2]===16 && !(i>0&&E[i-1][2]===16)).map(e=>e[0]); return cand;})()''')
        tj = await pg.evaluate('__player.T.time()')
        R['click_cell16'] = dict(yt_time_2_5s_after_click=round(tj, 2), counter=await pg.inner_text('#counter'), cell16_downbeats=exp[:3],
                                 expected_start='downbeat - 1.0 s (lead)')
        await pg.screenshot(path=SHOTS + 'song_clickjump.png')
        # LOOP: cells 20..21 via Loop cells…
        await pg.click('#loopCells'); await cells[20].click(); await cells[21].click(); await pg.wait_for_timeout(300)
        lp = await pg.evaluate('({a:__player.loop.a,b:__player.loop.b,on:__player.loop.on})'); R['loop'] = lp
        # Let it play across the loop end (loop is 2 bars ≈ 3.2 s at 150 bpm); sample times
        samples = []
        for _ in range(16):
            await pg.wait_for_timeout(500); samples.append(round(await pg.evaluate('__player.T.time()'), 2))
        R['loop_time_samples'] = samples
        R['loop_wrapped'] = any(samples[i+1] < samples[i] - 1 for i in range(len(samples) - 1)) and all(lp['a'] - 1.2 <= s <= lp['b'] + 0.6 for s in samples[4:])
        await pg.screenshot(path=SHOTS + 'song_loop.png')
        # SPEED 75 %
        await pg.click('#loopClr')
        await pg.select_option('#speed', '0.75'); await pg.wait_for_timeout(1500)
        ta = await pg.evaluate('__player.T.time()'); await pg.wait_for_timeout(4000); tb = await pg.evaluate('__player.T.time()')
        R['speed75_advance_in_4s'] = round(tb - ta, 2)
        R['yt_rate'] = await pg.evaluate('document.getElementById("speed").value')
        # marker lead slider default
        R['offset_default'] = await pg.evaluate('__player.offset'); R['offs_label'] = await pg.inner_text('#offsv')
        R['errors'] = [l for l in logs if 'PAGEERROR' in l or l.startswith('error')][:10]
        # other pages load without errors
        for s in ['estate-Ezhj9YqBY0w', 'misty-RFqSx8v8eUk']:
            p2 = await ctx.new_page(); errs = []; p2.on('pageerror', lambda e: errs.append(str(e)))
            await p2.goto(BASE + f'songs/{s}/index.html'); await p2.wait_for_timeout(2500)
            R['load_' + s] = dict(mode=await p2.evaluate('__player.T && __player.T.name'), cells=await p2.evaluate('document.querySelectorAll(".cell").length'), errors=errs)
            await p2.close()
        await b.close()
    print(json.dumps(R, indent=1, ensure_ascii=False))
asyncio.run(main())
