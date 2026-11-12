const { chromium } = require('playwright');
const [,, lang, mode, out] = process.argv; // mode: 'test' or 'all'
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await p.goto('file://' + __dirname + '/video.html?lang=' + lang);
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(300);
  const fs = require('fs'); fs.mkdirSync(out, { recursive: true });
  const times = mode === 'test' ? [2, 4.5, 9, 13.5, 16.5, 22, 28, 34, 38.5] : Array.from({ length: 40 * 30 }, (_, i) => i / 30);
  let i = 0;
  for (const t of times) {
    await p.evaluate((t) => window.render(t), t);
    await p.screenshot({ path: `${out}/f${String(i).padStart(5, '0')}.${mode === 'test' ? 'png' : 'jpg'}`, ...(mode === 'test' ? {} : { type: 'jpeg', quality: 92 }) });
    i++;
  }
  await b.close();
})();
