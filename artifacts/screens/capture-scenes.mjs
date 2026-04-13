import { chromium } from 'playwright';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clickNav(page, label){
  await page.evaluate((lab)=>{
    const el = [...document.querySelectorAll('.nl')].find((n)=>String(n.textContent || '').trim().toLowerCase() === String(lab).toLowerCase());
    if(el) el.click();
  }, label);
  await sleep(1300);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
const page = await context.newPage();

await page.goto('https://retrovault.zombi3king24.workers.dev/app', { waitUntil: 'domcontentloaded' });
await sleep(3500);
await page.screenshot({ path: '/workspace/artifacts/screens/current-home-1600x900.png' });

await clickNav(page, 'Scraper');
await sleep(1500);
await page.screenshot({ path: '/workspace/artifacts/screens/current-scraper-1600x900.png' });

await clickNav(page, 'Settings');
await sleep(1500);
await page.screenshot({ path: '/workspace/artifacts/screens/current-settings-1600x900.png' });

await page.evaluate(()=>{
  const btn = document.getElementById('rvUsersNavBtn');
  if(btn) btn.click();
});
await sleep(900);
await page.screenshot({ path: '/workspace/artifacts/screens/current-userspicker-1600x900.png' });

await browser.close();
