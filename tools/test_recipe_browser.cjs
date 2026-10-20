// Run through test_recipe_workflow.py with RECIPE_BROWSER_TEST=1.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),crypto=require('crypto');
const config=JSON.parse(fs.readFileSync('work/recipe-browser.json','utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1500,height:1000}});const page=await context.newPage();const errors=[];const batchRequests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/components/'))batchRequests.push(r.url())});
  await page.goto(config.base+'/login');await page.locator('#login-form [name=email]').fill(config.email);await page.locator('#login-form [name=password]').fill(config.password);await page.locator('#login-form button').click();await page.waitForSelector('#workspace:not([hidden])');
  const route=`${config.base}/buildings/${config.building}/documents/${config.document}/review?revision=${config.revision}`;
  const start=Date.now();await page.goto(route);await page.waitForFunction(()=>document.querySelector('#status')?.textContent.includes('30404 components'),{timeout:120000});const loadMs=Date.now()-start;
  const canvas=page.locator('canvas').first();await canvas.scrollIntoViewIfNeeded();await page.waitForTimeout(1000);const a=await canvas.screenshot();const bounds=await canvas.boundingBox();
  await page.mouse.move(bounds.x+bounds.width*.5,bounds.y+bounds.height*.5);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width*.7,bounds.y+bounds.height*.6,{steps:8});await page.mouse.up();await page.waitForTimeout(500);const b=await canvas.screenshot();
  const hash=x=>crypto.createHash('sha256').update(x).digest('hex');if(hash(a)===hash(b))throw Error('Orbit did not alter rendered image');
  await page.locator('#fit').click();await page.mouse.move(bounds.x+bounds.width*.5,bounds.y+bounds.height*.5);await page.mouse.wheel(0,-200);await page.waitForTimeout(300);
  await canvas.click({position:{x:bounds.width*.5,y:bounds.height*.55}});await page.waitForFunction(()=>document.querySelector('#picked')?.textContent!=='Select a component');
  await page.getByLabel('Filter components',{exact:true}).fill('C/level0front/bay0');const targets=page.getByLabel('Components and groups',{exact:true});
  const option=await targets.locator('option').first().getAttribute('value');if(!option)throw Error('No logical group');await targets.selectOption(option);await targets.dispatchEvent('change');
  await page.getByRole('button',{name:'Save component type',exact:true}).click();await page.waitForTimeout(750);
  if(batchRequests.length!==1||!batchRequests[0].endsWith('/components/batch'))throw Error('Group type must use one bounded batch request');
  await page.locator('#model-inspector textarea[name=text]').fill('Browser persistent IQ assembly note');await page.getByRole('button',{name:'Save note on selected model/component/group',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#status')?.textContent==='Note saved.');
  await page.reload();await page.waitForFunction(()=>document.querySelector('#status')?.textContent.includes('30404 components'),{timeout:120000});await page.getByLabel('Filter components',{exact:true}).fill('C/level0front/bay0');await targets.selectOption(option);await targets.dispatchEvent('change');await page.getByText('Browser persistent IQ assembly note',{exact:false}).waitFor();
  await page.screenshot({path:'work/iq-recipe-viewer.png',fullPage:true});
  await page.goto(route.replace(config.revision,config.correctedRevision));await page.waitForFunction(()=>document.querySelector('#status')?.textContent.includes('30404 components'),{timeout:120000});
  await page.getByLabel('Filter components',{exact:true}).fill(config.windowId);const options=await targets.locator('option').all();let selected;
  for(const o of options){const text=await o.textContent();if(text.startsWith(config.windowId+' ·')){selected=await o.getAttribute('value');break}}
  if(!selected)throw Error('Corrected glass component missing');await targets.selectOption(selected);await targets.dispatchEvent('change');await page.getByText('Parent revision reference (identity mapped; recheck): Check window width',{exact:false}).waitFor();
  if(errors.length)throw Error(errors.join('\n'));
  if(!await page.locator('#recipe-controls').evaluate(e=>e.open))await page.locator('#recipe-controls > summary').click();if(await page.locator('#legacy-pdf-assessment').evaluate(e=>e.open)||await page.locator('#pdf-geometry-draft').count())throw Error('Legacy assessment must be opt-in');const correction=page.locator('#recipe-controls details').first();await correction.locator('summary').click();await correction.getByLabel('Recipe window',{exact:true}).selectOption(config.windowId);await correction.getByLabel('Window width in metres',{exact:true}).fill('1.16');
  const responsePromise=page.waitForResponse(r=>r.url().endsWith(`/windows/${config.windowId}/width`)&&r.request().method()==='POST');await correction.getByRole('button',{name:'Save corrected revision',exact:true}).click();const response=await responsePromise;if(!response.ok())throw Error(await response.text());const job=await response.json();await page.close();
  let completed;for(let i=0;i<120;i++){const r=await context.request.get(`${config.base}/api/recipe-builds/${job.id}`);completed=await r.json();if(completed.status==='Completed'||completed.status==='Failed')break;await new Promise(resolve=>setTimeout(resolve,500));}
  if(completed?.status!=='Completed'||completed.revisionId===config.correctedRevision)throw Error('UI correction did not finish as a new revision after closing page');
  fs.writeFileSync('evidence/recipe-browser-test.json',JSON.stringify({passed:true,components:30404,loadMs,orbitImageChanged:true,scenePicking:true,groupBatchRequests:batchRequests.length,persistentNote:true,correctedRevisionHistoricalNote:true,uiCorrectionCompletedAfterPageClosed:true,browser:'Chrome headless with SwiftShader'},null,2));
  console.log(`PASS browser: ${loadMs} ms load; rendered orbit/fit/zoom, group selection, one batch, persistent note, corrected revision and historical reference; no page errors.`);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
