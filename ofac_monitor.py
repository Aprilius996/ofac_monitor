import re
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import smtplib
import os
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+ 原生支持

CHINA_PATTERN = re.compile(r"(中国|中國|香港|china|hong kong|hk)", re.I)

def fetch_today_china_related_link():
    """检查 OFAC 是否在今天（美国东部时间）发布更新，且内容涉及中国/香港"""
    base_url = "https://ofac.treasury.gov"
    index_url = base_url + "/recent-actions"
    today_str = "20250616"
    target_link = None

    try:
        resp = requests.get(index_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ 无法加载主页面：{e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    anchors = soup.find_all("a", href=True)

    for a in anchors:
        href = a["href"]
        if href.startswith(f"/recent-actions/{today_str}"):
            target_link = base_url + href
            break

    if not target_link:
        print("📭 今天没有发布新名单。")
        return None

    try:
        r = requests.get(target_link, timeout=30)
        r.raise_for_status()
        content = r.text
        if CHINA_PATTERN.search(content):
            return target_link
        else:
            print("📄 今天有更新，但与中国/香港无关。")
            return None
    except Exception as e:
        print(f"⚠️ 无法访问今日链接 {target_link}：{e}")
        return None

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

def already_notified_today(log_file="ofac_sent.log"):
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            if today in f.read():
                return True
    return False

def mark_notified_today(log_file="ofac_sent.log"):
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    with open(log_file, "a") as f:
        f.write(today + "\n")





# ===== 请完整复制下面的所有代码 =====
if __name__ == "__main__":
    print("🚀 检查 OFAC 是否于今日发布与中国/香港相关更新...")
    if os.getenv("RESET_NOTIFICATION") == "1":
        if os.path.exists("ofac_sent.log"):
            os.remove("ofac_sent.log")
            print("🧹 清除通知记录日志 ofac_sent.log")

    matched_url = fetch_today_china_related_link()

    if matched_url:
        if not already_notified_today():
            subject = "【OFAC提醒】今日新增与中国/香港相关制裁更新"
            body = f"OFAC 今日发布更新，内容涉及中国/香港：\n\n{matched_url}"

            from_addr = os.getenv("FROM_ADDR")
            to_addr = os.getenv("TO_ADDR")
            smtp_server = os.getenv("SMTP_SERVER", "smtp.qq.com")
            smtp_port = int(os.getenv("SMTP_PORT", 465))
            password = os.getenv("SMTP_PASSWORD")

            if from_addr and to_addr and password:
                send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password)
                mark_notified_today()
            else:
                print("❌ 缺少邮箱配置环境变量，未发送邮件")
        else:
            print("ℹ️ 今日已发送过涉华更新提醒，不再重复发送。")
    else:
        print("✅ 今日无与中国/香港相关的新更新。")
