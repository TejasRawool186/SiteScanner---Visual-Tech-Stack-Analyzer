import asyncio
from apify import Actor
from Wappalyzer import Wappalyzer, WebPage
from jinja2 import Environment, FileSystemLoader
from .knowledge_base import get_tech_details
import warnings
import re

warnings.filterwarnings("ignore")

async def main():
    async with Actor:
        # 1. Get Input
        input_data = await Actor.get_input() or {}
        url = input_data.get('websiteUrl', 'https://example.com')
        
        if not url.startswith('http'):
            url = 'https://' + url

        print(f"🕵️‍♂️ Initializing SiteScanner for: {url}")

        # 2. Use Playwright for JavaScript rendering (better detection)
        print("🌐 Launching browser for deep scan...")
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Navigate and wait for network to be idle
                response = await page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Get rendered HTML and headers
                html_content_rendered = await page.content()
                response_headers = response.headers if response else {}
                
                # Get all scripts for additional detection
                scripts = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
                }''')
                
                # Get meta tags
                meta_tags = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('meta')).map(m => ({
                        name: m.getAttribute('name'),
                        content: m.getAttribute('content'),
                        property: m.getAttribute('property')
                    }));
                }''')
                
                await browser.close()
                
            print("✅ Browser scan complete")
            
        except Exception as e:
            print(f"⚠️ Browser scan failed, falling back to basic scan: {e}")
            html_content_rendered = None
            response_headers = {}
            scripts = []
            meta_tags = []

        # 3. Run Wappalyzer analysis
        try:
            wappalyzer = Wappalyzer.latest()
            
            if html_content_rendered:
                # Use rendered HTML for better detection
                webpage = WebPage(url, html_content_rendered, response_headers)
            else:
                # Fallback to basic HTTP request
                webpage = WebPage.new_from_url(url)
            
            raw_techs = wappalyzer.analyze(webpage)
            
            # Additional pattern-based detection from scripts
            additional_techs = detect_from_scripts(scripts, html_content_rendered or "")
            raw_techs = raw_techs.union(additional_techs)
            
            print(f"✅ Detection Complete. Found {len(raw_techs)} technologies.")
            
        except Exception as e:
            await Actor.fail(f"Scan failed. Error: {e}")
            return

        # 4. Enrich Data
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

        # 5. Generate Premium Dashboard
        print("🎨 Generating Premium UI Report...")
        env = Environment(loader=FileSystemLoader('src/templates'))
        template = env.get_template('dashboard.html')
        
        dashboard_html = template.render(
            url=url,
            count=len(enriched_stack),
            techs=enriched_stack
        )

        # 6. Save Dashboard to Key-Value Store
        await Actor.set_value('OUTPUT_DASHBOARD', dashboard_html, content_type='text/html')
        print("✅ Dashboard saved to Key-Value Store")

        # 7. Push raw data to Dataset
        await Actor.push_data({
            "target_url": url,
            "tech_stack": list(raw_techs),
            "technologies_count": len(raw_techs)
        })
        
        print("🚀 Actor completed successfully! Check the Output tab for your dashboard.")


def detect_from_scripts(scripts: list, html: str) -> set:
    """Additional pattern-based detection for common technologies"""
    detected = set()
    
    # Combine scripts and HTML for pattern matching
    combined = " ".join(scripts).lower() + " " + html.lower()
    
    patterns = {
        'React': [r'react', r'_react', r'__NEXT_DATA__', r'reactDOM'],
        'Next.js': [r'next\.js', r'_next/', r'__NEXT_DATA__', r'nextjs'],
        'Vue.js': [r'vue\.js', r'vue\.min\.js', r'__VUE__', r'vue@'],
        'Nuxt.js': [r'nuxt', r'_nuxt/', r'__NUXT__'],
        'Angular': [r'angular', r'ng-version', r'ng-app'],
        'Svelte': [r'svelte', r'__svelte'],
        'Tailwind CSS': [r'tailwind', r'tailwindcss'],
        'Bootstrap': [r'bootstrap\.min', r'bootstrap\.css', r'bootstrap\.js'],
        'jQuery': [r'jquery', r'jquery\.min\.js'],
        'Webpack': [r'webpack', r'__webpack'],
        'Vite': [r'vite', r'@vite'],
        'TypeScript': [r'typescript', r'\.ts"'],
        'Node.js': [r'node\.js', r'nodejs'],
        'Express': [r'express'],
        'Vercel': [r'vercel', r'\.vercel\.app', r'vercel-insights'],
        'Netlify': [r'netlify'],
        'AWS': [r'amazonaws', r'aws-sdk', r'cloudfront'],
        'Google Analytics': [r'google-analytics', r'gtag', r'ga\.js', r'analytics\.js'],
        'Google Tag Manager': [r'googletagmanager', r'gtm\.js'],
        'Stripe': [r'stripe\.js', r'js\.stripe'],
        'Firebase': [r'firebase', r'firebaseapp'],
        'Supabase': [r'supabase'],
        'MongoDB': [r'mongodb'],
        'PostgreSQL': [r'postgresql', r'postgres'],
        'Redis': [r'redis'],
        'Docker': [r'docker'],
        'Nginx': [r'nginx'],
        'Apache': [r'apache'],
        'Framer Motion': [r'framer-motion', r'framer\.com'],
        'GSAP': [r'gsap', r'greensock'],
        'Three.js': [r'three\.js', r'threejs'],
        'D3.js': [r'd3\.js', r'd3\.min'],
        'Chart.js': [r'chart\.js', r'chartjs'],
        'Lodash': [r'lodash'],
        'Axios': [r'axios'],
        'Moment.js': [r'moment\.js', r'moment\.min'],
        'Day.js': [r'dayjs'],
        'Sentry': [r'sentry\.io', r'@sentry'],
        'Hotjar': [r'hotjar'],
        'Intercom': [r'intercom'],
        'Segment': [r'segment\.io', r'segment\.com'],
        'Mixpanel': [r'mixpanel'],
        'Amplitude': [r'amplitude'],
        'Prismic': [r'prismic'],
        'Contentful': [r'contentful'],
        'Sanity': [r'sanity\.io'],
        'Shopify': [r'shopify', r'myshopify'],
        'WooCommerce': [r'woocommerce'],
        'Magento': [r'magento'],
        'WordPress': [r'wp-content', r'wp-includes', r'wordpress'],
        'Webflow': [r'webflow'],
        'Wix': [r'wix\.com', r'wixstatic'],
        'Squarespace': [r'squarespace'],
        'Ghost': [r'ghost\.io'],
        'Gatsby': [r'gatsby'],
        'Hugo': [r'hugo'],
        'Jekyll': [r'jekyll'],
        'Astro': [r'astro'],
        'Remix': [r'remix\.run', r'__remix'],
        'SolidJS': [r'solid-js', r'solidjs'],
        'Qwik': [r'qwik'],
        'Preact': [r'preact'],
        'Alpine.js': [r'alpine\.js', r'alpinejs', r'x-data'],
        'HTMX': [r'htmx\.org', r'htmx\.js'],
        'Turbo': [r'turbo\.js', r'@hotwired/turbo'],
        'Stimulus': [r'stimulus'],
    }
    
    for tech, tech_patterns in patterns.items():
        for pattern in tech_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                detected.add(tech)
                break
    
    return detected


if __name__ == '__main__':
    asyncio.run(main())
