import os
import json
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

# تابع برای دریافت خبرها از RSS
def fetch_news():
    news_items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:  # محدود به 5 خبر از هر منبع
                news_items.append({
                    "title": entry.title,
                    "content": entry.summary or entry.description,
                    "link": entry.link
                })
        except Exception as e:
            print(f"خطا در دریافت فید {feed_url}: {e}")
    return news_items

# تابع برای ارسال درخواست به جمینی
def call_gemini(prompt):
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
    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"خطا در درخواست جمینی: {response.text}")
            return None
    except Exception as e:
        print(f"خطا در تماس با جمینی: {e}")
        return None

# تابع برای فیلتر کردن خبرها با جمینی
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
def publish_to_blogger(title, content):
    try:
        # بارگذاری اطلاعات احراز هویت
        creds_info = json.loads(os.environ.get("BLOGGER_CREDS"))
        if not all(k in creds_info for k in ['token', 'refresh_token', 'client_id', 'client_secret', 'scopes']):
            raise ValueError("فایل CREDENTIALS ناقص است.")
        creds = Credentials.from_authorized_user_info(creds_info)
        
        # ایجاد سرویس بلاگر
        service = build("blogger", "v3", credentials=creds)
        
        # ایجاد پست
        post_body = {
            "kind": "blogger#post",
            "blog": {"id": BLOG_ID},
            "title": title,
            "content": content
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
    # دریافت خبرها
    news_items = fetch_news()
    if not news_items:
        print("هیچ خبری دریافت نشد.")
        return
    
    # فیلتر کردن با جمینی
    filtered_news = filter_news_with_gemini(news_items)
    if not filtered_news:
        print("هیچ خبری پس از فیلتر باقی نماند.")
        return
    
    # بازنویسی و انتشار
    for news in filtered_news:
        print(f"در حال پردازش: {news['title']}")
        rewritten_content = rewrite_with_gemini(news["content"])
        if rewritten_content:
            publish_to_blogger(news["title"], rewritten_content)
        else:
            print(f"بازنویسی برای {news['title']} ناموفق بود.")

if __name__ == "__main__":
    main()
