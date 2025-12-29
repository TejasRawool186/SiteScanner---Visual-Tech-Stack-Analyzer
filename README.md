# 🕵️ SiteScanner - Visual Tech Stack Analyzer

**Uncover any website's technology stack in seconds with a premium, enterprise-grade visual report.**

## 🎯 What It Does

SiteScanner is a powerful sales intelligence tool that scans any website URL and generates a stunning, dark-mode HTML dashboard revealing all the technologies used:

- **CMS Platforms** (WordPress, Webflow, Shopify)
- **Frontend Frameworks** (React, Vue.js, Next.js)
- **Backend Technologies** (Node.js, Python, PHP)
- **Analytics Tools** (Google Analytics, Mixpanel, Hotjar)
- **Payment Systems** (Stripe, PayPal)
- **Infrastructure** (Cloudflare, AWS, Vercel)
- **And 80+ more technologies...**

## ✨ Key Features

- **🚀 Zero-API Architecture**: Uses `python-Wappalyzer` for local detection—no external API costs
- **🎨 Premium Dashboard**: Enterprise dark-mode design with glassmorphism and smooth animations
- **📊 Enriched Data**: Each technology includes descriptions, logos, and category classifications
- **🔗 Instant Sharing**: Generates a public URL for your report that you can share with anyone

## 📸 Output Preview

The generated report features:
- Deep charcoal background (`#0F1115`) with soft sage accents (`#6EE7B7`)
- Responsive grid layout with hover animations
- Technology cards with logos, descriptions, and category pills
- Professional typography using Inter font

## 🛠️ How to Use

### Input

| Field | Description | Example |
|-------|-------------|---------|
| `websiteUrl` | The website to analyze | `https://stripe.com` |

### Output

The Actor produces:
1. **Dataset Record**: JSON with target URL, detected tech stack, and report URL
2. **Key-Value Store**: The full HTML dashboard accessible via public URL

```json
{
    "target_url": "https://stripe.com",
    "tech_stack": ["React", "Cloudflare", "Stripe", "..."],
    "report_url": "https://api.apify.com/v2/key-value-stores/.../records/OUTPUT_DASHBOARD"
}
```

## 🏗️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Detection Engine | `python-Wappalyzer` |
| Template Engine | `Jinja2` |
| Runtime | Python 3.11 |
| Platform | Apify Actor |

## 💡 Use Cases

- **Sales Teams**: Research prospects' technology investments before outreach
- **Competitive Analysis**: Understand what tools competitors are using
- **Developer Research**: Quickly audit a site's tech stack for integration planning
- **Agency Pitches**: Generate professional reports to showcase in proposals

## 🔒 Privacy & Compliance

SiteScanner only analyzes publicly visible technology signatures. It does not:
- Access any private or authenticated content
- Store any personal data
- Make any changes to the target website

## 📝 License

MIT License - Free for personal and commercial use.

---

**Built with ❤️ for the Apify community**
