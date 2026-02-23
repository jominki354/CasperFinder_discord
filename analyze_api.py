import asyncio
import json
from playwright.async_api import async_playwright


async def run(playwright):
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = await context.new_page()

    found_api = False

    async def handle_request(request):
        nonlocal found_api
        if "product/exhibition/cars" in request.url and request.method == "POST":
            print("=" * 50)
            print(f"URL: {request.url}")
            print(f"Method: {request.method}")
            print("--- HEADERS ---")
            for k, v in request.headers.items():
                print(f"{k}: {v}")
            print("--- POST DATA ---")
            try:
                data = json.loads(request.post_data)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except:
                print(request.post_data)
            print("=" * 50)
            found_api = True

    page.on("request", handle_request)

    print("Navigating to casper.hyundai.com promotion page...")
    await page.goto(
        "https://casper.hyundai.com/vehicles/car-list/promotion",
        wait_until="networkidle",
    )

    # Wait a bit for React to load and fire API requests
    for i in range(10):
        if found_api:
            break
        await asyncio.sleep(1)

    # Optional: Click on the specific exhibition tabs to trigger the API load
    try:
        if not found_api:
            print("Clicking buttons to trigger API...")
            await page.click("text=기획전", timeout=3000)
            await asyncio.sleep(2)
    except Exception as e:
        print("Click failed:", e)

    await browser.close()


async def main():
    async with async_playwright() as playwright:
        await run(playwright)


if __name__ == "__main__":
    asyncio.run(main())
