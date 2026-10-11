const path = require('path');
const { createRequire } = require('module');
const root = path.resolve(__dirname, '../..');
const tools = createRequire(path.join(root, '.cache/browser/package.json'));
const { chromium: playwright } = tools('playwright');
const imported = tools('@sparticuz/chromium');
const chromium = imported.default || imported;
const fs = require('fs');
const base = process.env.QA_BASE_URL || 'http://127.0.0.1:8000/';
process.chdir(root);
(async () => {
  const browser = await playwright.launch({executablePath: await chromium.executablePath(), args: chromium.args, headless: true});
  const page = await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('console',msg=>{if(msg.type()==='error') errors.push(msg.text());});
  page.on('requestfailed',r=>errors.push(r.url()+': '+r.failure().errorText));
  page.on('response',r=>{if(r.status()>=400) errors.push(r.status()+': '+r.url());});
  const results=[];
  for (const path of ['index.html','executive-summary.html','research.html','sources.html','audit.html']) {
    const response=await page.goto(base+path,{waitUntil:'networkidle'});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
    const tifLinks=await page.locator('a[href$=".tif"],a[href$=".zip"]').count();
    results.push({path,status:response.status(),desktopOverflow:overflow,tifLinks,h1Count:await page.locator('h1').count(),disabledDownload:!['index.html','executive-summary.html'].includes(path)||await page.locator('button[disabled]').count()===1});
  }
  await page.goto(base+'sources.html',{waitUntil:'networkidle'});
  await page.locator('#repo-filter').fill('GEMSDOE32');
  results.push({sourceFilterVisibleRows:await page.locator('tr[data-search]:visible').count(),filterStatus:await page.locator('[data-result-count]').innerText(),feed:await page.locator('[data-feed-status]').innerText()});
  await page.goto(base+'index.html',{waitUntil:'networkidle'});
  await page.screenshot({path:'.cache/browser/desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  for (const path of ['index.html','executive-summary.html','research.html','sources.html','audit.html']) {
    await page.goto(base+path,{waitUntil:'networkidle'});
    results.push({path,mobileOverflow:await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)});
  }
  await page.goto(base+'index.html',{waitUntil:'networkidle'});
  await page.screenshot({path:'.cache/browser/mobile.png',fullPage:true});
  fs.writeFileSync('evidence/browser_checks.json',JSON.stringify({checked_at:new Date().toISOString(),engine:'Chromium via Playwright',viewports:[{width:1440,height:1000},{width:390,height:844}],results,errors,passed:errors.length===0&&results.every(r=>r.status===undefined||r.status===200)&&results.every(r=>!r.desktopOverflow&&!r.mobileOverflow&&!r.tifLinks&&r.disabledDownload!==false)&&results.some(r=>r.sourceFilterVisibleRows===1)},null,2)+'\n');
  console.log(fs.readFileSync('evidence/browser_checks.json','utf8'));
  await browser.close();
  const report=JSON.parse(fs.readFileSync('evidence/browser_checks.json','utf8'));
  if (!report.passed || !results.some(r=>r.sourceFilterVisibleRows===1)) process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
