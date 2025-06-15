import os
import asyncio
import re
from playwright.async_api import async_playwright
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import smtplib


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
    pattern = re.compile(r'(中国|香港)', re.I)
    return [url for url, title in links_dict.items() if pattern.search(title) or pattern.search(url)]


def send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password):
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['From'] = formataddr(("OFAC监控脚本", from_addr))
    msg['To'] = formataddr(("收件人", to_addr))
    msg['Subject'] = Header(subject, 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_server, int(smtp_port))
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        print("📬 邮件发送成功")
    except Exception as e:
        print("❌ 邮件发送失败：", str(e))


async def main():
    print("开始抓取 OFAC 最近更新链接...")
    all_links = await fetch_recent_action_links()
    # 模拟 OFAC 返回数据（测试用）
    all_links = {
        "https://ofac.treasury.gov/recent-actions/2025-06-15-china": "新增对中国某企业制裁",
        "https://ofac.treasury.gov/recent-actions/2025-06-15-iran": "新增对伊朗某组织制裁",
        "https://ofac.treasury.gov/recent-actions/2025-06-15-hk": "香港某金融机构新增制裁",
    }
    print(f"共提取 {len(all_links)} 条更新链接")

    china_links = filter_china_links(all_links)
    print(f"共找到 {len(china_links)} 条与中国/香港相关的链接：")
    for link in china_links:
        print(link)

    if china_links:
        subject = f"【OFAC提醒】发现 {len(china_links)} 条涉及中国/香港的新更新"
        body = "以下链接与中国/香港相关：\n\n" + "\n".join(china_links)

        # 从环境变量读取邮件信息
        from_addr = os.getenv("FROM_ADDR")
        to_addr = os.getenv("TO_ADDR")
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = os.getenv("SMTP_PORT")
        password = os.getenv("SMTP_PASSWORD")

        send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password)
    else:
        print("❌ 无与中国/香港相关的新更新，无需发送邮件")


if __name__ == "__main__":
    asyncio.run(main())
