import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()
        
        logs = []
        
        def on_console(msg):
            log_text = msg.text
            if '[AMap]' in log_text or '[SharedTrack]' in log_text or '[Region]' in log_text:
                logs.append(log_text)
                print(f'[LOG] {log_text}')
        
        page.on('console', on_console)
        
        print('Navigating to http://localhost:5173/s/YPKRXL0P')
        await page.goto('http://localhost:5173/s/YPKRXL0P', wait_until='domcontentloaded')
        
        # Wait longer for dynamic content
        print('Waiting 8 seconds for page to fully load...')
        await asyncio.sleep(8)
        
        print('\n=== Checking page content ===')
        # Check what elements exist
        page_content = await page.evaluate('''() => {
            return {
                hasTree: !!document.querySelector('.region-tree-container'),
                hasMap: !!document.querySelector('.map-container'),
                treeVisible: document.querySelector('.region-tree-container') ? 
                    window.getComputedStyle(document.querySelector('.region-tree-container')).display : 'N/A',
                allClasses: Array.from(document.body.classList).join(' ')
            };
        }''')
        print(f'Page info: {page_content}')
        
        # Get page title and text content to understand what's displayed
        title = await page.evaluate('''() => document.title''')
        print(f'Page title: {title}')
        
        # Check if there's any error message
        errors = await page.evaluate('''() => {
            const errorElements = document.querySelectorAll('[class*="error"], [class*="Error"]');
            return Array.from(errorElements).map(el => el.textContent);
        }''')
        if errors:
            print(f'Errors found: {errors}')
        
        # Get all text content to debug
        all_text = await page.evaluate('''() => document.body.innerText''')
        print(f'\n=== First 500 chars of page text ===')
        print(all_text[:500])
        
        print('\n=== All logs collected ===')
        for log in logs:
            print(f'  {log}')
        
        # Take a screenshot for debugging
        await page.screenshot(path='d:/code/vibe_route/screenshot.png')
        print('\nScreenshot saved to d:/code/vibe_route/screenshot.png')
        
        print('\n=== Keeping browser open for 5 seconds ===')
        await asyncio.sleep(5)
        
        await browser.close()

asyncio.run(main())
