import { chromium } from 'playwright';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clickNav(page, label){
  await page.evaluate((lab)=>{
    const el = [...document.querySelectorAll('.nl')].find((n)=>String(n.textContent || '').trim().toLowerCase() === String(lab).toLowerCase());
    if(el) el.click();
  }, label);
  await sleep(1400);
}

async function closeProfilePickerIfOpen(page){
  await page.evaluate(()=>{
    const overlay = document.getElementById('rvProfilePicker');
    if(overlay && overlay.classList.contains('show')){
      const closeBtn = document.getElementById('rvProfileCloseBtn');
      if(closeBtn) closeBtn.click();
    }
  });
  await sleep(600);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
const page = await context.newPage();

await page.goto('https://retrovault.zombi3king24.workers.dev/app', { waitUntil: 'domcontentloaded' });
await sleep(3600);
await closeProfilePickerIfOpen(page);
await page.screenshot({ path: '/workspace/artifacts/screens/current-home-clean-1600x900.png' });

await clickNav(page, 'Scraper');
await closeProfilePickerIfOpen(page);
await sleep(1200);
await page.screenshot({ path: '/workspace/artifacts/screens/current-scraper-clean-1600x900.png' });

await clickNav(page, 'Settings');
await closeProfilePickerIfOpen(page);
await sleep(1200);
await page.screenshot({ path: '/workspace/artifacts/screens/current-settings-clean-1600x900.png' });

await page.evaluate(()=>{
  const btn = document.getElementById('rvUsersNavBtn');
  if(btn) btn.click();
});
await sleep(900);
await page.screenshot({ path: '/workspace/artifacts/screens/current-userspicker-clean-1600x900.png' });

await browser.close();
