import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        await page.goto("https://www.amazon.com", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.goto("https://www.amazon.com/dp/B07PFB72NL", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        content = await page.content()
        print("Size:", len(content))
        title = await page.title()
        print("Title:", title)
        await browser.close()

asyncio.run(test())
