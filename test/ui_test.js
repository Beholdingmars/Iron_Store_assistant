const { chromium } = require('playwright');
const fs = require('fs');
// Needs: npm i playwright axe-core, and the fake server on port 8765
const OUT = process.env.SHOTS || require('path').join(__dirname, 'shots') + '/';
fs.mkdirSync(OUT, { recursive: true });
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const URL = 'http://localhost:8765/';

async function axe(page, tag) {
  await page.addScriptTag({ content: AXE });
  const r = await page.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'] })).violations
    .map(v => `${v.impact} ${v.id}: ${v.nodes.length} → ${v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | ')}`));
  console.log(`AXE ${tag}:`, r.length ? '\n  ' + r.join('\n  ') : 'no violations');
}
async function ask(page, text) {
  await page.fill('#question', text);
  await page.keyboard.press('Enter');
}
(async () => {
  const browser = await chromium.launch();
  const errors = [];
  for (const scheme of ['light', 'dark']) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
    const page = await ctx.newPage();
    page.on('console', m => m.type() === 'error' && errors.push(m.text()));
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(URL); await page.waitForTimeout(1800);
    await page.screenshot({ path: OUT + `home_${scheme}.png` });
    await page.hover('.chip >> nth=1'); await page.waitForTimeout(300);
    await page.screenshot({ path: OUT + `home_hover_${scheme}.png`, clip: { x: 0, y: 450, width: 1440, height: 450 } });
    await page.screenshot({ path: OUT + `home_full_${scheme}.png`, fullPage: true });
    await axe(page, `home ${scheme}`);
    // keyboard: "/" focuses the box
    await page.mouse.click(5, 300);
    await page.keyboard.press('/');
    console.log('slash focuses textarea:', await page.evaluate(() => document.activeElement.id));
    await page.click('.chip >> nth=1');                       // refund
    await page.waitForTimeout(900);
    await page.screenshot({ path: OUT + `progress_${scheme}.png` });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: OUT + `streaming_${scheme}.png` });
    await page.waitForSelector('.receipt', { timeout: 15000 }); await page.waitForTimeout(800);
    await page.screenshot({ path: OUT + `conflict_${scheme}.png` });
    await page.hover('.fn >> nth=1'); await page.waitForTimeout(250);
    await page.screenshot({ path: OUT + `conflict_link_${scheme}.png`, fullPage: true });
    if (scheme === 'light') {
      await ask(page, 'What is the price and availability of the Veltro VKT-1800 glass kettle?');
      await page.waitForFunction(() => document.querySelectorAll('.turn .receipt').length >= 4, null, { timeout: 15000 });
      await ask(page, 'How many days of annual leave do employees get?');
      await page.waitForFunction(() => document.querySelectorAll('.turn').length === 3 && !document.querySelector('.progress'), null, { timeout: 15000 });
      await ask(page, 'Does IronStore accept crypto payments?');
      await page.waitForFunction(() => document.querySelectorAll('.turn').length === 4 && !document.querySelector('.progress'), null, { timeout: 15000 });
      await ask(page, 'please explode');
      await page.waitForFunction(() => document.querySelectorAll('.turn').length === 5 && !document.querySelector('.progress'), null, { timeout: 15000 });
      await page.waitForTimeout(600);
      await page.screenshot({ path: OUT + `thread_full_light.png`, fullPage: true });
      await axe(page, 'thread light');
      // stop button
      await ask(page, 'kettle again');
      await page.waitForTimeout(500);
      console.log('send while busy label:', await page.getAttribute('#send', 'aria-label'));
      await page.click('#send'); await page.waitForTimeout(500);
      console.log('after stop tag:', await page.textContent('.turn:last-child .turn-meta'));
      // viewer
      await page.click('.receipt .pill >> nth=0');
      await page.waitForTimeout(1500);
      await page.screenshot({ path: OUT + `viewer_light.png` });
      await axe(page, 'viewer');
      await page.keyboard.press('Escape'); await page.waitForTimeout(500);
      console.log('focus back after viewer:', await page.evaluate(() => document.activeElement.className + ' ' + document.activeElement.textContent));
      // reload keeps answers
      await page.reload(); await page.waitForTimeout(800);
      console.log('restored turns:', await page.locator('.turn').count());
      // new question resets
      await page.click('#newChat'); await page.waitForTimeout(1500);
      console.log('home visible after reset:', await page.isVisible('#home'));
    } else {
      await axe(page, 'thread dark');
    }
    await ctx.close();
  }
  // mobile
  const m = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const mp = await m.newPage();
  mp.on('pageerror', e => errors.push(e.message));
  await mp.goto(URL); await mp.waitForTimeout(1800);
  await mp.screenshot({ path: OUT + 'mobile_home.png' });
  await mp.screenshot({ path: OUT + 'mobile_home_full.png', fullPage: true });
  await mp.tap('.chip >> nth=1');
  await mp.waitForSelector('.receipt', { timeout: 15000 }); await mp.waitForTimeout(800);
  await mp.screenshot({ path: OUT + 'mobile_conflict.png', fullPage: true });
  const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log('mobile horizontal overflow px:', overflow);
  await m.close();
  // reduced motion
  const r = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  const rp = await r.newPage(); rp.on('pageerror', e => errors.push(e.message));
  await rp.goto(URL); await rp.waitForTimeout(400);
  await rp.screenshot({ path: OUT + 'reduced_home.png' });
  await r.close();
  console.log('ERRORS:', errors.length ? errors : 'none');
  await browser.close();
})();
