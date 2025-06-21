import re
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import smtplib
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess


CHINA_PATTERN = re.compile(r"中国|China|香港|hong kong|hk", re.I)

def fetch_ofac_china_related_link():
    base_url = "https://ofac.treasury.gov/recent-actions"
    today_url = f"{base_url}/{datetime.now(ZoneInfo("America/New_York").strftime("%Y%m%d")}"
    target_url = f"{base_url}/{today_url}"
    
    try:
        resp = requests.get(target_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"无法加载页面:{e}")
        return None
    
    soup = BeautifulSoup(resp.text, "html.parser")
    h4_tags = soup.find_all("h4")

    for h4 in h4_tags:
        sibling = h4.find_next_sibling()
        while sibling and sibling.name != "h4":
            if sibling.name != "h4":
                text = sibling.get_text(separator=" ", strip=True)
                if CHINA_PATTERN.search(text):
                    return target_url           
            sibling = sibling.find_next_sibling()



def send_email(subject, body, from_addr, to_addr, smtp_server, smtp_port, password):
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = formataddr(("OFAC监控脚本", from_addr))
    msg["To"] = formataddr(("收件人", to_addr))
    msg["Subject"] = Header(subject, "utf-8")
    
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_addr], msg.as_string())
        server.quit()
        print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败:{e}")
        
        


if __name__ == "__main__":
    sent_file = "sent_urls.txt"
    sent_urls = set()
    if os.path.exists(sent_file):
        with open(sent_file, "r") as f:
            sent_urls = set(line.strip() for line in f)
            
            
    ofac_link = fetch_ofac_china_related_link()
    if ofac_link and ofac_link not in sent_urls:
        print(f"发现与中国相关的OFAC链接: {ofac_link}")
        # 发送邮件通知
        send_email(
            subject="OFAC监控通知",
            body=f"发现与中国相关的OFAC链接: {ofac_link}",
            from_addr = os.getenv("FROM_ADDR"),      # 修改为你的发件邮箱
            to_addr = os.getenv("TO_ADDR"),         # 修改为收件人邮箱
            smtp_server = os.getenv("SMTP_SERVER", "smtp.qq.com"),
            smtp_port = 465,
            password = os.getenv("SMTP_PASSWORD")
        )
        
        with open(sent_file, "a") as f:
            f.write(ofac_link + "\n")
            
        subprocess.run(['git', 'add', sent_file])
        subprocess.run(['git', 'commit', '-m', 'Update sent URLs'])
        subprocess.run(['git', 'push'])
    else:
        print("没有发现与中国相关的OFAC链接")
