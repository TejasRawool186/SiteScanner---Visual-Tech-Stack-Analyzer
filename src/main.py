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
        
        html_content_rendered = None
        response_headers = {}
        scripts = []
        stylesheets = []
        meta_tags = []
        inline_scripts = []
        network_requests = []
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Collect network requests for deeper analysis
                async def handle_request(request):
                    network_requests.append(request.url)
                
                page.on("request", handle_request)
                
                # Navigate and wait for network to be idle
                response = await page.goto(url, wait_until='networkidle', timeout=45000)
                
                # Wait a bit more for dynamic content
                await page.wait_for_timeout(2000)
                
                # Get rendered HTML and headers
                html_content_rendered = await page.content()
                response_headers = response.headers if response else {}
                
                # Get all external scripts
                scripts = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
                }''')
                
                # Get all stylesheets
                stylesheets = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href);
                }''')
                
                # Get inline script content for analysis
                inline_scripts = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('script:not([src])')).map(s => s.textContent).slice(0, 10);
                }''')
                
                # Get meta tags
                meta_tags = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('meta')).map(m => ({
                        name: m.getAttribute('name') || '',
                        content: m.getAttribute('content') || '',
                        property: m.getAttribute('property') || '',
                        httpEquiv: m.getAttribute('http-equiv') || ''
                    }));
                }''')
                
                # Get generator meta tag
                generator = await page.evaluate('''() => {
                    const gen = document.querySelector('meta[name="generator"]');
                    return gen ? gen.getAttribute('content') : '';
                }''')
                
                # Get data attributes that might reveal frameworks
                data_attrs = await page.evaluate('''() => {
                    const attrs = [];
                    document.querySelectorAll('*').forEach(el => {
                        Array.from(el.attributes).forEach(attr => {
                            if (attr.name.startsWith('data-') || attr.name.startsWith('ng-') || 
                                attr.name.startsWith('v-') || attr.name.startsWith('x-')) {
                                attrs.push(attr.name);
                            }
                        });
                    });
                    return [...new Set(attrs)].slice(0, 50);
                }''')
                
                await browser.close()
                
            print(f"✅ Browser scan complete (captured {len(network_requests)} network requests)")
            
        except Exception as e:
            print(f"⚠️ Browser scan failed, falling back to basic scan: {e}")

        # 3. Run Wappalyzer analysis
        try:
            wappalyzer = Wappalyzer.latest()
            
            if html_content_rendered:
                webpage = WebPage(url, html_content_rendered, response_headers)
            else:
                webpage = WebPage.new_from_url(url)
            
            raw_techs = wappalyzer.analyze(webpage)
            
            # Additional pattern-based detection
            additional_techs = detect_technologies(
                scripts=scripts,
                stylesheets=stylesheets,
                inline_scripts=inline_scripts,
                html=html_content_rendered or "",
                headers=response_headers,
                meta_tags=meta_tags,
                network_requests=network_requests
            )
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
        enriched_stack.sort(key=lambda x: (x['category'], x['name']))

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
            "technologies_count": len(raw_techs),
            "categories": list(set([t['category'] for t in enriched_stack]))
        })
        
        print("🚀 Actor completed successfully! Check the Output tab for your dashboard.")


def detect_technologies(scripts: list, stylesheets: list, inline_scripts: list, 
                        html: str, headers: dict, meta_tags: list, network_requests: list) -> set:
    """Comprehensive technology detection using multiple signals"""
    detected = set()
    
    # Combine all sources for pattern matching
    all_scripts = " ".join(scripts).lower()
    all_styles = " ".join(stylesheets).lower()
    all_inline = " ".join(inline_scripts).lower()
    all_network = " ".join(network_requests).lower()
    html_lower = html.lower()
    headers_str = str(headers).lower()
    
    combined = f"{all_scripts} {all_styles} {all_inline} {all_network} {html_lower}"
    
    # ========== FRONTEND FRAMEWORKS ==========
    patterns = {
        # JavaScript Frameworks
        'React': [r'react\.', r'react-dom', r'_react', r'reactid', r'data-reactroot', r'__react'],
        'Next.js': [r'/_next/', r'__next', r'next\.js', r'nextjs', r'next-route-announcer'],
        'Vue.js': [r'vue\.js', r'vue\.min', r'__vue__', r'vue@', r'data-v-', r'v-cloak'],
        'Nuxt.js': [r'/_nuxt/', r'__nuxt', r'nuxt\.js', r'nuxt\.config'],
        'Angular': [r'angular\.', r'ng-version', r'ng-app', r'\[ngif\]', r'\(click\)', r'ng-reflect'],
        'Svelte': [r'svelte', r'__svelte', r'svelte-'],
        'Solid': [r'solid-js', r'solidjs', r'solid\.'],
        'Preact': [r'preact', r'/preact/'],
        'Ember.js': [r'ember\.js', r'ember-', r'data-ember'],
        'Backbone.js': [r'backbone\.js', r'backbone-'],
        'Alpine.js': [r'alpine\.js', r'alpinejs', r'x-data=', r'x-bind:', r'x-on:'],
        'HTMX': [r'htmx\.', r'hx-get', r'hx-post', r'hx-trigger'],
        'Stimulus': [r'stimulus', r'data-controller='],
        'Turbo': [r'@hotwired/turbo', r'turbo-frame', r'turbo-stream'],
        
        # Meta-frameworks
        'Gatsby': [r'gatsby', r'/gatsby-', r'___gatsby'],
        'Remix': [r'remix\.run', r'__remix', r'remix-'],
        'Astro': [r'astro', r'/astro/', r'astro-'],
        'Qwik': [r'qwik', r'/qwik/'],
        'SvelteKit': [r'sveltekit', r'__sveltekit'],
        
        # CSS Frameworks
        'Tailwind CSS': [r'tailwind', r'tailwindcss', r'tw-'],
        'Bootstrap': [r'bootstrap\.min', r'bootstrap\.css', r'bootstrap\.js', r'bootstrap\.bundle'],
        'Bulma': [r'bulma\.css', r'bulma\.min', r'/bulma/'],
        'Foundation': [r'foundation\.css', r'foundation\.min'],
        'Material-UI': [r'@mui/', r'material-ui', r'mui-'],
        'Chakra UI': [r'chakra-ui', r'@chakra-ui'],
        'Ant Design': [r'antd', r'ant-design'],
        'Semantic UI': [r'semantic\.min', r'semantic-ui'],
        
        # Build Tools
        'Webpack': [r'webpack', r'__webpack', r'webpackjsonp'],
        'Vite': [r'@vite', r'/vite/', r'vite\.config', r'import\.meta\.hot'],
        'Parcel': [r'parcel', r'/parcel/'],
        'Rollup': [r'rollup'],
        'esbuild': [r'esbuild'],
        'Turbopack': [r'turbopack'],
        
        # State Management
        'Redux': [r'redux', r'__redux'],
        'MobX': [r'mobx'],
        'Zustand': [r'zustand'],
        'Recoil': [r'recoil'],
        'Jotai': [r'jotai'],
        'XState': [r'xstate'],
        
        # Animation Libraries
        'Framer Motion': [r'framer-motion', r'framer\.com/motion'],
        'GSAP': [r'gsap', r'greensock', r'tweenmax', r'tweenlite'],
        'Anime.js': [r'anime\.min', r'animejs'],
        'Lottie': [r'lottie', r'lottie-web'],
        'AOS': [r'aos\.js', r'aos\.css', r'data-aos'],
        
        # 3D/Graphics
        'Three.js': [r'three\.js', r'three\.min', r'/three/', r'threejs'],
        'Babylon.js': [r'babylon\.js', r'babylonjs'],
        'PixiJS': [r'pixi\.js', r'pixijs'],
        'Paper.js': [r'paper\.js', r'paperjs'],
        'Fabric.js': [r'fabric\.js', r'fabricjs'],
        
        # Charts/Visualization
        'D3.js': [r'd3\.js', r'd3\.min', r'/d3/'],
        'Chart.js': [r'chart\.js', r'chartjs'],
        'Highcharts': [r'highcharts'],
        'ApexCharts': [r'apexcharts'],
        'Recharts': [r'recharts'],
        'Victory': [r'victory-'],
        'Plotly': [r'plotly'],
        'ECharts': [r'echarts'],
        
        # Utilities
        'jQuery': [r'jquery', r'jquery\.min'],
        'Lodash': [r'lodash'],
        'Underscore.js': [r'underscore\.js', r'underscore\.min'],
        'Axios': [r'axios'],
        'Moment.js': [r'moment\.js', r'moment\.min'],
        'Day.js': [r'dayjs'],
        'date-fns': [r'date-fns'],
        'Luxon': [r'luxon'],
        'RxJS': [r'rxjs'],
        'Immutable.js': [r'immutable\.js', r'immutable\.min'],
        
        # TypeScript
        'TypeScript': [r'typescript', r'\.tsx', r'\.ts"'],
        
        # ========== BACKEND / SERVER ==========
        'Node.js': [r'node\.js', r'express', r'x-powered-by.*node'],
        'Express': [r'express'],
        'Fastify': [r'fastify'],
        'NestJS': [r'nestjs', r'nest-'],
        'Koa': [r'/koa/', r'koa-'],
        'Hapi': [r'@hapi/'],
        
        'Django': [r'django', r'csrfmiddlewaretoken'],
        'Flask': [r'flask', r'werkzeug'],
        'FastAPI': [r'fastapi'],
        
        'Ruby on Rails': [r'rails', r'ruby on rails', r'turbolinks'],
        'Laravel': [r'laravel', r'x-powered-by.*laravel'],
        'Symfony': [r'symfony'],
        'CodeIgniter': [r'codeigniter'],
        
        'Spring': [r'spring', r'x-powered-by.*spring'],
        'ASP.NET': [r'asp\.net', r'x-aspnet', r'__viewstate', r'aspnetcore'],
        
        'GraphQL': [r'graphql', r'/graphql', r'__graphql'],
        'Apollo': [r'apollo', r'apollographql'],
        
        # ========== CMS PLATFORMS ==========
        'WordPress': [r'wp-content', r'wp-includes', r'wordpress', r'wp-json'],
        'Drupal': [r'drupal', r'/sites/default/'],
        'Joomla': [r'joomla', r'/components/com_'],
        'Ghost': [r'ghost\.io', r'ghost-'],
        'Strapi': [r'strapi'],
        'Contentful': [r'contentful', r'cdn\.contentful'],
        'Sanity': [r'sanity\.io', r'sanity-'],
        'Prismic': [r'prismic\.io', r'prismic-'],
        'DatoCMS': [r'datocms'],
        'Storyblok': [r'storyblok'],
        'Hygraph': [r'hygraph', r'graphcms'],
        
        # Website Builders
        'Webflow': [r'webflow\.', r'\.webflow\.io'],
        'Wix': [r'wix\.com', r'wixstatic', r'wix-'],
        'Squarespace': [r'squarespace', r'sqsp\.'],
        'Weebly': [r'weebly'],
        'Carrd': [r'carrd\.co'],
        'Framer': [r'framer\.website', r'framer\.app'],
        
        # Static Site Generators
        'Hugo': [r'/hugo/', r'hugo-'],
        'Jekyll': [r'jekyll'],
        'Eleventy': [r'eleventy', r'11ty'],
        'Hexo': [r'hexo'],
        'Docusaurus': [r'docusaurus'],
        'VuePress': [r'vuepress'],
        'Nextra': [r'nextra'],
        
        # ========== E-COMMERCE ==========
        'Shopify': [r'shopify', r'myshopify\.com', r'cdn\.shopify'],
        'WooCommerce': [r'woocommerce', r'wc-'],
        'Magento': [r'magento', r'mage/'],
        'BigCommerce': [r'bigcommerce'],
        'PrestaShop': [r'prestashop'],
        'OpenCart': [r'opencart'],
        'Saleor': [r'saleor'],
        'Medusa': [r'medusajs'],
        
        # Payments
        'Stripe': [r'stripe\.js', r'js\.stripe\.com', r'stripe-'],
        'PayPal': [r'paypal', r'paypalobjects'],
        'Square': [r'square\.com', r'squareup'],
        'Braintree': [r'braintree'],
        'Klarna': [r'klarna'],
        'Affirm': [r'affirm\.com'],
        
        # ========== ANALYTICS & MARKETING ==========
        'Google Analytics': [r'google-analytics', r'gtag', r'ga\.js', r'analytics\.js', r'googleanalytics'],
        'Google Tag Manager': [r'googletagmanager', r'gtm\.js', r'/gtm\.js'],
        'Facebook Pixel': [r'facebook\.net', r'fbq\(', r'facebook-jssdk'],
        'Mixpanel': [r'mixpanel', r'mxpnl'],
        'Amplitude': [r'amplitude\.com', r'amplitude-'],
        'Segment': [r'segment\.io', r'segment\.com', r'analytics\.js'],
        'Heap': [r'heap\.io', r'heapanalytics'],
        'Hotjar': [r'hotjar', r'hj\('],
        'FullStory': [r'fullstory', r'fs\.js'],
        'LogRocket': [r'logrocket'],
        'Pendo': [r'pendo\.io'],
        'PostHog': [r'posthog'],
        'Plausible': [r'plausible\.io'],
        'Fathom': [r'usefathom'],
        'Clarity': [r'clarity\.ms'],
        'Mouseflow': [r'mouseflow'],
        
        # Marketing Tools
        'HubSpot': [r'hubspot', r'hs-scripts', r'hstc'],
        'Mailchimp': [r'mailchimp', r'list-manage'],
        'Klaviyo': [r'klaviyo'],
        'Intercom': [r'intercom', r'intercomcdn'],
        'Drift': [r'drift\.com', r'driftt'],
        'Crisp': [r'crisp\.chat'],
        'Zendesk': [r'zendesk', r'zdassets'],
        'Freshdesk': [r'freshdesk'],
        'Tawk.to': [r'tawk\.to'],
        'LiveChat': [r'livechatinc'],
        'Olark': [r'olark'],
        
        # A/B Testing
        'Optimizely': [r'optimizely'],
        'VWO': [r'visualwebsiteoptimizer', r'vwo\.'],
        'LaunchDarkly': [r'launchdarkly'],
        'Split': [r'split\.io'],
        
        # ========== INFRASTRUCTURE ==========
        'Vercel': [r'vercel\.', r'\.vercel\.app', r'vercel-insights', r'_vercel'],
        'Netlify': [r'netlify', r'\.netlify\.app'],
        'Cloudflare': [r'cloudflare', r'cf-ray', r'cfr\-ray', r'__cf'],
        'AWS': [r'amazonaws', r'aws-sdk', r'cloudfront\.net', r'\.s3\.'],
        'Google Cloud': [r'googleapis', r'googleusercontent', r'gstatic'],
        'Azure': [r'azure', r'\.azurewebsites', r'\.azureedge'],
        'DigitalOcean': [r'digitalocean', r'\.digitaloceanspaces'],
        'Heroku': [r'heroku', r'\.herokuapp'],
        'Railway': [r'railway\.app'],
        'Render': [r'render\.com', r'\.onrender\.com'],
        'Fly.io': [r'fly\.io', r'\.fly\.dev'],
        
        # CDN
        'Fastly': [r'fastly', r'fastly\.net'],
        'Akamai': [r'akamai', r'\.akamaized'],
        'KeyCDN': [r'keycdn'],
        'Bunny CDN': [r'bunny\.net', r'b-cdn'],
        'jsDelivr': [r'jsdelivr\.net'],
        'unpkg': [r'unpkg\.com'],
        'cdnjs': [r'cdnjs\.cloudflare'],
        
        # ========== DATABASES ==========
        'Supabase': [r'supabase', r'\.supabase\.'],
        'Firebase': [r'firebase', r'firebaseapp', r'firebaseio'],
        'MongoDB': [r'mongodb', r'\.mongodb\.'],
        'PlanetScale': [r'planetscale'],
        'Neon': [r'neon\.tech'],
        'Upstash': [r'upstash'],
        'Fauna': [r'fauna\.com', r'faunadb'],
        'CockroachDB': [r'cockroachlabs'],
        'Prisma': [r'prisma\.io', r'prisma-'],
        
        # ========== AUTH ==========
        'Auth0': [r'auth0'],
        'Okta': [r'okta\.com'],
        'Clerk': [r'clerk\.', r'clerk-'],
        'NextAuth': [r'next-auth'],
        'Firebase Auth': [r'firebaseauth'],
        'Supabase Auth': [r'supabase.*auth'],
        
        # ========== MONITORING ==========
        'Sentry': [r'sentry\.io', r'@sentry', r'sentry-'],
        'Datadog': [r'datadoghq', r'datadog'],
        'New Relic': [r'newrelic'],
        'Bugsnag': [r'bugsnag'],
        'Raygun': [r'raygun'],
        'Rollbar': [r'rollbar'],
        'LogDNA': [r'logdna'],
        
        # ========== FONTS & ICONS ==========
        'Google Fonts': [r'fonts\.googleapis', r'fonts\.gstatic'],
        'Font Awesome': [r'fontawesome', r'font-awesome', r'fa-'],
        'Adobe Fonts': [r'typekit', r'use\.typekit'],
        'Material Icons': [r'material-icons', r'material-design-icons'],
        'Ionicons': [r'ionicons'],
        'Feather Icons': [r'feather-icons', r'feathericons'],
        'Heroicons': [r'heroicons'],
        'Lucide': [r'lucide'],
        
        # ========== MISC ==========
        'reCAPTCHA': [r'recaptcha', r'grecaptcha'],
        'hCaptcha': [r'hcaptcha'],
        'Turnstile': [r'turnstile', r'challenges\.cloudflare'],
        'Cookie Consent': [r'cookieconsent', r'cookie-consent'],
        'OneTrust': [r'onetrust'],
        'CookieBot': [r'cookiebot'],
        'GDPR': [r'gdpr'],
        
        # Schema/SEO
        'JSON-LD': [r'application/ld\+json'],
        'Open Graph': [r'og:title', r'og:description', r'og:image'],
        'Twitter Cards': [r'twitter:card', r'twitter:title'],
        
        # PWA
        'PWA': [r'serviceworker', r'manifest\.json', r'workbox'],
        'Workbox': [r'workbox'],
    }
    
    # Check all patterns
    for tech, tech_patterns in patterns.items():
        for pattern in tech_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                detected.add(tech)
                break
    
    # Check HTTP headers for server info
    server_header = headers.get('server', '').lower()
    x_powered = headers.get('x-powered-by', '').lower()
    
    header_techs = {
        'Nginx': ['nginx'],
        'Apache': ['apache'],
        'Cloudflare': ['cloudflare'],
        'Vercel': ['vercel'],
        'Netlify': ['netlify'],
        'Express': ['express'],
        'PHP': ['php'],
        'ASP.NET': ['asp.net', 'aspnetcore'],
        'Kestrel': ['kestrel'],
    }
    
    for tech, keywords in header_techs.items():
        for keyword in keywords:
            if keyword in server_header or keyword in x_powered or keyword in headers_str:
                detected.add(tech)
                break
    
    # Check meta tags for generators
    for meta in meta_tags:
        name = meta.get('name', '').lower()
        content = meta.get('content', '').lower()
        
        if name == 'generator':
            generator_techs = {
                'WordPress': ['wordpress'],
                'Drupal': ['drupal'],
                'Joomla': ['joomla'],
                'Ghost': ['ghost'],
                'Hugo': ['hugo'],
                'Jekyll': ['jekyll'],
                'Gatsby': ['gatsby'],
                'Next.js': ['next.js'],
                'Nuxt': ['nuxt'],
                'Docusaurus': ['docusaurus'],
                'VuePress': ['vuepress'],
            }
            for tech, keywords in generator_techs.items():
                for keyword in keywords:
                    if keyword in content:
                        detected.add(tech)
    
    return detected


if __name__ == '__main__':
    asyncio.run(main())
