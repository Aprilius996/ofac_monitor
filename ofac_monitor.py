import re
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from playwright.async_api import async_playwright
from datetime import datetime, timedelta, timezone

# 你的异步抓取函数
async def fetch_recent_action_links():
    links = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://ofac.treasury.gov/recent-actions", timeout=60000)
        await page.wait_for_selector('a[href*="/recent-actions/202"]', timeout=10000)

        elements = await page.query_selector_all('a[href*="/recent-actions/202"]')
        for elem in elements:
            href = await elem.get_attribute("href")
            text = (await elem.inner_text()).strip()
            if href and text:
                if href.startswith("/"):
                    href = "https://ofac.treasury.gov" + href
                links[href] = text

        await browser.close()
    return links

def filter_china_links(links_dict):
    china_links = []
    pattern = re.compile(r'(中国|香港)', re.I)
    for url, title in links_dict.items():
        if pattern.search(title) or pattern.search(url):
            china_links.append(url)
    return china_links

def send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password):
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = formataddr(("OFAC监控脚本", from_addr))
    msg['To'] = formataddr(("收件人", to_addr))
    msg['Subject'] = Header(subject, 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        print("📬 邮件发送成功")
    except Exception as e:
        print("❌ 邮件发送失败：", str(e))

# 你的主要业务逻辑
async def run_task():
    print(f"[{datetime.now()}] 开始抓取 OFAC 最近更新链接...")
    all_links = await fetch_recent_action_links()
    print(f"共提取 {len(all_links)} 条更新链接")

    china_links = filter_china_links(all_links)
    print(f"共找到 {len(china_links)} 条与中国/香港相关的链接：")
    for link in china_links:
        print(link)

    if china_links:
        subject = f"【OFAC提醒】发现 {len(china_links)} 条涉及中国/香港的新更新"
        body = "以下链接与中国/香港相关：\n\n" + "\n".join(china_links)

        from_addr = "stanmarsh_1996@qq.com"
        to_addr = "1049022953@qq.com"
        smtp_server = "smtp.qq.com"
        smtp_port = 465
        password = "你的授权码"  # 记得替换

        send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password)
    else:
        print("❌ 无与中国/香港相关的新更新，无需发送邮件")

# 计算到下一个整点的秒数（北京时间，UTC+8）
def seconds_until_next_run():
    tz = timezone(timedelta(hours=8))  # 北京时间
    now = datetime.now(tz)
    if now.hour < 8:
        # 如果早于8点，直接等待到8点整
        next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
    elif now.hour >= 20:
        # 晚于20点，等到第二天8点
        next_run = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        # 8点-19点之间，等到下一个整点
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    return (next_run - now).total_seconds()

async def scheduler():
    while True:
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        if 8 <= now.hour <= 20:
            await run_task()
        else:
            print(f"[{now}] 非执行时间段，等待到早上8点...")

        wait_seconds = seconds_until_next_run()
        print(f"等待 {int(wait_seconds)} 秒后开始下一次执行...\n")
        await asyncio.sleep(wait_seconds)

if __name__ == "__main__":
    asyncio.run(scheduler())
