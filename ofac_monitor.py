import re
from playwright.sync_api import sync_playwright
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import smtplib

CHINA_PATTERN = re.compile(r"(中国|香港)", re.I)

def fetch_china_related_links():
    """同步抓取 OFAC 最近更新中正文包含‘中国/香港’的链接"""
    matching_links = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://ofac.treasury.gov/recent-actions", timeout=60000)
        page.wait_for_selector('a[href*="/recent-actions/202"]', timeout=10000)

        elements = page.query_selector_all('a[href*="/recent-actions/202"]')
        hrefs = {
            "https://ofac.treasury.gov/recent-actions/20250606"
        }
        """
        for elem in elements:
            href = elem.get_attribute("href")
            if href and href.startswith("/recent-actions/202"):
                hrefs.add("https://ofac.treasury.gov" + href)
        """
        for url in hrefs:
            try:
                detail_page = browser.new_page()
                detail_page.goto(url, timeout=60000)
                detail_page.wait_for_selector("main", timeout=10000)

                content = detail_page.inner_text("main")
                if CHINA_PATTERN.search(content):
                    matching_links.append(url)

                detail_page.close()
            except Exception as e:
                print(f"⚠️ 读取 {url} 失败：{e}")

        browser.close()
    return matching_links


def send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password):
    """发送邮件通知"""
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


if __name__ == "__main__":
    print("🚀 开始检查 OFAC 最近更新是否涉及中国/香港...")

    china_links = fetch_china_related_links()
    print(f"✅ 共找到 {len(china_links)} 条与中国/香港相关的链接：")
    for link in china_links:
        print(link)

    if china_links:
        subject = f"【OFAC提醒】发现 {len(china_links)} 条涉及中国/香港的新更新"
        body = "以下链接与中国/香港相关：\n\n" + "\n".join(china_links)

        from_addr = "your_email@qq.com"      # 修改为你的发件邮箱
        to_addr = "receiver@qq.com"          # 修改为收件人邮箱
        smtp_server = "smtp.qq.com"
        smtp_port = 465
        password = "your_smtp_auth_code"     # QQ邮箱授权码

        send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password)
    else:
        print("❌ 无与中国/香港相关的新更新，无需发送邮件")
