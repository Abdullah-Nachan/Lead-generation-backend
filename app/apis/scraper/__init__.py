from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import io
import csv
from app.auth import AuthorizedUser
from pydantic import BaseModel
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import random

# placeholder for models, will be replaced with actual db models
# from app.libs.models import Lead, Search

router = APIRouter(prefix="/scraper", tags=["Scraping"])

class ScrapeRequest(BaseModel):
    location: str
    keywords: str
    radius: int

class ScrapeResponse(BaseModel):
    message: str
    search_id: int | None = None
    results_found: int | None = None


import databutton as db
import asyncpg
from pydantic import BaseModel

class VerificationUpdate(BaseModel):
    is_verified: bool

@router.put("/leads/{lead_id}/verify")
async def update_lead_verification(lead_id: int, update: VerificationUpdate, user: AuthorizedUser):
    conn = await asyncpg.connect(db.secrets.get("DATABASE_URL_DEV"))
    try:
        result = await conn.execute(
            "UPDATE leads SET is_verified = $1 WHERE id = $2",
            update.is_verified, lead_id
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Lead not found")
        return {"message": "Lead verification status updated successfully."}
    finally:
        await conn.close()

@router.get("/export/csv", tags=["stream"])
async def export_verified_leads_to_csv(user: AuthorizedUser):
    """
    Exports all verified leads to a CSV file.
    """
    conn = await asyncpg.connect(db.secrets.get("DATABASE_URL_DEV"))
    try:
        leads = await conn.fetch("SELECT business_name, owner_name, phone, address, website, email, source_platform, created_at FROM leads WHERE is_verified = TRUE ORDER BY created_at DESC")
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["Business Name", "Owner Name", "Phone", "Address", "Website", "Email", "Source", "Date Scraped"])
        
        # Write data
        for lead in leads:
            writer.writerow(lead.values())
        
        output.seek(0)
        
        return StreamingResponse(
            io.StringIO(output.getvalue()), 
            media_type="text/csv", 
            headers={"Content-Disposition": "attachment; filename=verified_leads.csv"}
        )
    finally:
        await conn.close()


@router.post("/search", response_model=ScrapeResponse)
async def search_leads(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Accepts search criteria and starts the scraping process in the background.
    """
    print(f"Received search request: {request}")

    background_tasks.add_task(scrape_and_store, request)

    return {"message": f"Scraping job started for keywords '{request.keywords}' in '{request.location}'."}

async def scrape_and_store(request: ScrapeRequest):
    """
    This function will contain the core scraping, geocoding, filtering,
    and database storage logic.
    """
    print("Background task started...")
    try:
        scraped_data = await scrape_indiamart(request.keywords, request.location)
        print(f"Scraped {len(scraped_data)} leads from IndiaMART.")
        # Next steps:
        # 1. Scrape JustDial
        # 2. Geocode addresses
        # 3. Filter by radius
        # 4. Store in DB
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        print("Background task finished.")

async def scrape_indiamart(keywords: str, location: str):
    """
    Scrapes business listings from IndiaMART using Playwright and BeautifulSoup.
    """
    search_url = f"https://dir.indiamart.com/search.mp?ss={keywords.replace(' ', '+')}&cq={location.replace(' ', '+')}"
    print(f"Scraping IndiaMART URL: {search_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page()
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(".box-result", timeout=30000)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            listings = soup.select(".box-result")
            results = []

            for listing in listings[:10]: # Limiting to 10 for now
                name = listing.select_one('h2.r-cl-h.dn-h').get_text(strip=True) if listing.select_one('h2.r-cl-h.dn-h') else None
                phone = listing.select_one('.pns_h.g-call.l-f17').get('data-slno') if listing.select_one('.pns_h.g-call.l-f17') else None
                address_tag = listing.find('p', class_='r-cl-l pa')
                address = address_tag.get_text(strip=True) if address_tag else None
                website_tag = listing.find('a', class_='ws-ic.cp.ws.g-call.l-f17.p-l15')
                website = website_tag['href'] if website_tag else None

                if name:
                    results.append({
                        "business_name": name,
                        "phone": phone,
                        "address": address,
                        "website": website,
                        "source_platform": "IndiaMART"
                    })
                
                # Add a random delay to be a good citizen
                await asyncio.sleep(random.uniform(0.5, 1.5))

            print(f"Successfully scraped {len(results)} listings from IndiaMART.")
            return results

        except Exception as e:
            print(f"Error scraping IndiaMART: {e}")
            await page.screenshot(path="indiamart_error.png")
            return []
        finally:
            await browser.close()
