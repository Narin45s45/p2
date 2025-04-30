import os
import json
import time
import feedparser
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# تنظیمات اولیه
GEMINI_API_KEY = os.environ.get("GEMAPI")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
BLOG_ID = "764765195397447456"
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://newsbtc.com/feed/"
]

# تابع برای دریافت آخرین خبر از RSS
def fetch_latest_news():
    news_items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if feed.entries:
                entry = feed.entries[0]  # فقط اولین (جدیدترین) خبر
                # استخراج تصویر (از media:content یا enclosure)
                image_url = None
                if hasattr(entry, 'media_content') and entry.media_content:
                    image_url = entry.media_content[0].get('url')
                elif hasattr(entry, 'enclosure') and entry.enclosure:
                    image_url = entry.enclosure[0].get('url')
                
                # استخراج سرفصل (subtitle یا description کوتاه)
                subtitle = entry.get('subtitle', entry.get('description', '')[:200])
                
                news_items.append({
                    "title": entry.title,
                    "subtitle": subtitle,
                    "content": entry.summary or entry.description,
                    "link": entry.link,
                    "image_url": image_url,
                    "published": entry.get("published", "")
                })
        except Exception as e:
            print(f"خطا در دریافت فید {feed_url}: {e}")
    
    # مرتب‌سازی بر اساس زمان انتشار و انتخاب جدیدترین
    if news_items:
        latest_news = sorted(news_items, key=lambda x: x["published"], reverse=True)[0]
        return [latest_news]
    return []

# تابع برای ارسال درخواست به جمینی با مدیریت خطای 429
def call_gemini(prompt, retries=3, delay=60):
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                return result["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code == 429:
                print(f"خطای 429: محدودیت quota. منتظر {delay} ثانیه...")
                time.sleep(delay)
                continue
            else:
                print(f"خطا در درخواست جمینی: {response.text}")
                return None
        except Exception as e:
            print(f"خطا در تماس با جمینی: {e}")
            return None
    print("تلاش‌ها برای درخواست جمینی ناموفق بود.")
    return None

# تابع برای فیلتر کردن خبر با جمینی
def filter_news_with_gemini(news_items):
    filtered_news = []
    for item in news_items:
        prompt = f"""
        متن زیر را تحلیل کن و تشخیص بده آیا به کشورهایی غیر از آمریکا و چین اشاره دارد یا نه.
        اگر به کشورهای دیگر (مثل ایران، روسیه، هند و غیره) اشاره دارد، پاسخ بده: "فیلتر شده"
        در غیر این صورت پاسخ بده: "مجاز"
        متن: {item['title']} - {item['content']}
        """
        response = call_gemini(prompt)
        time.sleep(5)  # تأخیر 5 ثانیه برای جلوگیری از خطای 429
        if response and response.strip() == "مجاز":
            filtered_news.append(item)
        else:
            print(f"خبر فیلتر شد: {item['title']}")
    return filtered_news

# تابع برای بازنویسی محتوا با جمینی
def rewrite_with_gemini(content):
    prompt = f"""
    متن زیر را به فارسی روان و ساده بازنویسی کن تا برای خوانندگان عمومی قابل فهم باشد.
    از کلمات پیچیده استفاده نکن و مفهوم اصلی را حفظ کن:
    {content}
    """
    return call_gemini(prompt)

# تابع برای انتشار پست در بلاگر
def publish_to_blogger(news):
    try:
        # بررسی متغیر محیطی
        credentials = os.environ.get("CREDENTIALS")
        if not credentials:
            raise ValueError("متغیر محیطی CREDENTIALS تنظیم نشده است.")
        
        # بارگذاری اطلاعات احراز هویت
        creds_info = json.loads(credentials)
        if not all(k in creds_info for k in ['token', 'refresh_token', 'client_id', 'client_secret', 'scopes']):
            raise ValueError("فایل CREDENTIALS ناقص است. کلیدهای لازم: token, refresh_token, client_id, client_secret, scopes")
        creds = Credentials.from_authorized_user_info(creds_info)
        
        # ایجاد سرویس بلاگر
        service = build("blogger", "v3", credentials=creds)
        
        # بازنویسی متن
        rewritten_content = rewrite_with_gemini(news["content"])
        if not rewritten_content:
            print(f"بازنویسی برای {news['title']} ناموفق بود.")
            return None
        
        # قالب‌بندی محتوا به‌صورت HTML
        content_html = f"""
        <h1>{news['title']}</h1>
        """
        if news['subtitle']:
            content_html += f"<h2>{news['subtitle']}</h2>"
        if news['image_url']:
            content_html += f'<img src="{news["image_url"]}" alt="{news["title"]}" style="max-width:100%;height:auto;"><br>'
        else:
            print(f"هشدار: تصویر برای {news['title']} یافت نشد.")
        content_html += f"""
        <p>{rewritten_content}</p>
        <p><a href="{news['link']}" target="_blank">منبع</a></p>
        """
        
        # ایجاد پست
        post_body = {
            "kind": "blogger#post",
            "blog": {"id": BLOG_ID},
            "title": news["title"],
            "content": content_html
        }
        posts = service.posts()
        request = posts.insert(blogId=BLOG_ID, body=post_body)
        response = request.execute()
        print(f"پست منتشر شد: {response['url']}")
        return response
    except HttpError as error:
        print(f"خطا در انتشار پست: {error}")
        return None
    except Exception as e:
        print(f"خطا در انتشار: {e}")
        return None

# تابع اصلی
def main():
    # بررسی کلید API جمینی
    if not GEMINI_API_KEY:
        print("کلید API جمینی (GEMAPI) تنظیم نشده است.")
        return
    
    # دریافت آخرین خبر
    news_items = fetch_latest_news()
    if not news_items:
        print("هیچ خبری دریافت نشد.")
        return
    
    # فیلتر کردن با جمینی
    filtered_news = filter_news_with_gemini(news_items)
    if not filtered_news:
        print("خبر فیلتر شد و هیچ موردی برای انتشار باقی نماند.")
        return
    
    # انتشار خبر
    for news in filtered_news:
        print(f"در حال پردازش: {news['title']}")
        publish_to_blogger(news)
        time.sleep(5)  # تأخیر 5 ثانیه برای جلوگیری از خطای 429

if __name__ == "__main__":
    main()
