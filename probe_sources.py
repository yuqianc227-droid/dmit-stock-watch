"""Print safe, credential-free diagnostics for public stock source HTML."""
import re
import requests
from bs4 import BeautifulSoup

SOURCES = {
    "vpsrestock": "https://vpsrestock.com/dmit/",
    "dmit_checkout": "https://www.dmit.io/cart.php?a=add&pid=253",
}
for name, url in SOURCES.items():
    try:
        response = requests.get(url, timeout=(8, 20), headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        text = BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)
        # Only non-sensitive indicators; no URL tokens, cookies, or unredacted page text.
        indicators = {
            "contains_plan": bool(re.search(r"LAX\\s*\\.\\s*AS3\\s*\\.\\s*Pro\\s*\\.\\s*TINY", text, re.I)),
            "html_has_plan": "LAX.AS3.Pro.TINY" in response.text,
            "contains_out_of_stock": any(s in text for s in ("缺货", "Out of Stock", "Sold Out")),
            "contains_price": "$10.90" in text,
            "contains_captcha": any(s.lower() in text.lower() for s in ("captcha", "cloudflare", "just a moment", "enable javascript")),
        }
        print(name, "HTTP", response.status_code, "html_bytes", len(response.content),
              "text_chars", len(text), "indicators", indicators)

        if name == "vpsrestock":
            import html as html_lib
            raw = response.text
            matches = list(re.finditer(r"LAX(?:\\\\u002e|\\\\u002E|\\.|\\\\\\/|[.])AS3", raw, re.I))
            print("vpsrestock raw match count:", len(matches))
            for idx, match in enumerate(matches[:5]):
                context = raw[max(0, match.start() - 350):match.start() + 650]
                context = re.sub(r"[\\r\\n]+", " ", context)
                print(f"vpsrestock context {idx}:", context[:1000])
    except requests.RequestException as exc:
        print(name, "FAILED", type(exc).__name__)
