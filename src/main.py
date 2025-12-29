import asyncio
from apify import Actor
from Wappalyzer import Wappalyzer, WebPage
from jinja2 import Environment, FileSystemLoader
from .knowledge_base import get_tech_details
import warnings
import os

warnings.filterwarnings("ignore")

async def main():
    async with Actor:
        # 1. Get Input
        input_data = await Actor.get_input() or {}
        url = input_data.get('websiteUrl', 'https://example.com')
        
        if not url.startswith('http'):
            url = 'https://' + url

        print(f"🕵️‍♂️ Initializing SiteScanner for: {url}")

        # 2. Run Wappalyzer (Zero-API Detection)
        try:
            wappalyzer = Wappalyzer.latest()
            webpage = WebPage.new_from_url(url)
            raw_techs = wappalyzer.analyze(webpage)
            print(f"✅ Detection Complete. Found {len(raw_techs)} technologies.")
        except Exception as e:
            await Actor.fail(f"Scan failed. Error: {e}")
            return

        # 3. Enrich Data
        enriched_stack = []
        for tech_name in raw_techs:
            details = get_tech_details(tech_name)
            enriched_stack.append({
                "name": tech_name,
                "description": details['desc'],
                "logo": details['logo'],
                "category": details['category']
            })

        # Sort by category for better visuals
        enriched_stack.sort(key=lambda x: x['category'])

        # 4. Generate Premium Dashboard
        print("🎨 Generating Premium UI Report...")
        env = Environment(loader=FileSystemLoader('src/templates'))
        template = env.get_template('dashboard.html')
        
        html_content = template.render(
            url=url,
            count=len(enriched_stack),
            techs=enriched_stack
        )

        # 5. Save Dashboard to Key-Value Store
        await Actor.set_value('OUTPUT_DASHBOARD', html_content, content_type='text/html')
        print("✅ Dashboard saved to Key-Value Store")

        # 6. Push raw data to Dataset
        await Actor.push_data({
            "target_url": url,
            "tech_stack": list(raw_techs),
            "technologies_count": len(raw_techs)
        })
        
        print("🚀 Actor completed successfully! Check the Output tab for your dashboard.")

if __name__ == '__main__':
    asyncio.run(main())
