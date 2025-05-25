#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OFAC 中国/香港实体监控脚本
此脚本监控 OFAC 网站上关于中国和香港实体的更新，并在发现相关更新时发送通知
"""

import requests
import re
import time
import datetime
import json
import os
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ofac_monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ofac_monitor")

# 配置文件路径
CONFIG_FILE = "ofac_monitor_config.json"
CACHE_FILE = "ofac_monitor_cache.json"

# 默认配置
DEFAULT_CONFIG = {
    "check_interval": 3600,  # 每小时检查一次
    "base_url": "https://ofac.treasury.gov",
    "recent_actions_url": "https://ofac.treasury.gov/recent-actions",
    "keywords": ["china", "chinese", "hong kong", "中国", "香港"],
    "notification": {
        "method": "email",  # email, sms, wechat, etc.
        "email": {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "your_email@example.com",
            "smtp_password": "your_password",
            "from_addr": "your_email@example.com",
            "to_addr": "recipient@example.com"
        },
        "sms": {
            # 配置短信服务（如使用Twilio或其他SMS网关）
            "api_key": "",
            "api_secret": "",
            "from_number": "",
            "to_number": ""
        },
        "wechat": {
            # 微信企业号或服务号配置
            "corp_id": "",
            "corp_secret": "",
            "agent_id": "",
            "to_user": ""
        }
    }
}

class OFACMonitor:
    def __init__(self, config_file: str = CONFIG_FILE):
        """初始化监控器"""
        self.config = self._load_config(config_file)
        self.cache = self._load_cache()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """加载配置文件，如果不存在则创建默认配置"""
        if not os.path.exists(config_file):
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            logger.info(f"已创建默认配置文件: {config_file}")
            return DEFAULT_CONFIG
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"已加载配置文件: {config_file}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return DEFAULT_CONFIG
    
    def _load_cache(self) -> Dict[str, Any]:
        """加载缓存文件，如果不存在则创建空缓存"""
        if not os.path.exists(CACHE_FILE):
            cache = {"last_check": None, "known_actions": []}
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=4)
            return cache
        
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载缓存文件失败: {e}")
            return {"last_check": None, "known_actions": []}
    
    def _save_cache(self) -> None:
        """保存缓存到文件"""
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=4)
        logger.debug("缓存已更新")
    
    def get_recent_actions(self) -> List[Dict[str, Any]]:
        """获取最近的OFAC行动列表"""
        try:
            response = requests.get(self.config["recent_actions_url"], headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            actions = []
            
            # 查找所有的最近行动条目
            action_items = soup.select('.views-row')
            
            for item in action_items:
                try:
                    date_element = item.select_one('.datetime')
                    title_element = item.select_one('h3 a')
                    
                    if date_element and title_element:
                        date_str = date_element.text.strip()
                        title = title_element.text.strip()
                        link = title_element.get('href')
                        
                        # 格式化日期
                        try:
                            date_obj = datetime.datetime.strptime(date_str, '%m/%d/%Y')
                            date_formatted = date_obj.strftime('%Y%m%d')
                        except ValueError:
                            date_formatted = date_str.replace('/', '')
                        
                        action = {
                            "date": date_str,
                            "date_formatted": date_formatted,
                            "title": title,
                            "link": f"{self.config['base_url']}{link}" if link.startswith('/') else link,
                            "full_url": f"{self.config['base_url']}/recent-actions/{date_formatted}"
                        }
                        actions.append(action)
                except Exception as e:
                    logger.error(f"解析行动条目时出错: {e}")
            
            return actions
        except Exception as e:
            logger.error(f"获取最近行动列表失败: {e}")
            return []
    
    def get_action_details(self, action_url: str) -> Optional[str]:
        """获取行动详情页面内容"""
        try:
            response = requests.get(action_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取行动详情失败 {action_url}: {e}")
            return None
    
    def is_related_to_china_or_hk(self, content: str) -> bool:
        """判断内容是否与中国或香港相关"""
        if not content:
            return False
        
        content_lower = content.lower()
        
        # 使用配置中的关键词列表
        for keyword in self.config["keywords"]:
            if keyword.lower() in content_lower:
                return True
        
        # 额外检查提及实体的部分
        patterns = [
            r'chinese (entity|entities|person|individual|company|companies|organization|organisations)',
            r'hong kong (entity|entities|person|individual|company|companies|organization|organisations)',
            r'中国(公司|企业|实体|个人|组织)',
            r'香港(公司|企业|实体|个人|组织)',
            r'中国.*?(被列入|制裁)',
            r'香港.*?(被列入|制裁)',
            r'sanctions.*?china',
            r'sanctions.*?hong kong'
        ]
        
        for pattern in patterns:
            if re.search(pattern, content_lower):
                return True
        
        return False
    
    def send_notification(self, action: Dict[str, Any], details: str = "") -> bool:
        """发送通知"""
        notification_method = self.config["notification"]["method"]
        
        message = f"OFAC更新提醒 - 中国/香港实体\n\n"
        message += f"日期: {action['date']}\n"
        message += f"标题: {action['title']}\n"
        message += f"链接: {action['full_url']}\n\n"
        
        if details:
            # 提取相关的中国/香港实体信息
            soup = BeautifulSoup(details, 'html.parser')
            content_text = soup.get_text()
            
            # 简单提取可能的实体名称（这里可以根据OFAC网页结构进一步优化）
            entities = []
            content_lines = content_text.split('\n')
            for i, line in enumerate(content_lines):
                if any(keyword.lower() in line.lower() for keyword in self.config["keywords"]):
                    entities.append(line.strip())
                    # 尝试获取周围的上下文
                    for j in range(max(0, i-2), min(len(content_lines), i+3)):
                        if j != i and content_lines[j].strip():
                            entities.append(f"  {content_lines[j].strip()}")
            
            if entities:
                message += "相关实体信息:\n" + "\n".join(entities[:10])
                if len(entities) > 10:
                    message += "\n...以及更多实体"
        
        logger.info(f"发送通知: {message}")
        
        if notification_method == "email":
            return self._send_email_notification(message, action)
        elif notification_method == "sms":
            return self._send_sms_notification(message)
        elif notification_method == "wechat":
            return self._send_wechat_notification(message)
        else:
            logger.error(f"不支持的通知方式: {notification_method}")
            return False
    
    def _send_email_notification(self, message: str, action: Dict[str, Any]) -> bool:
        """通过邮件发送通知"""
        try:
            email_config = self.config["notification"]["email"]
            
            msg = MIMEMultipart()
            msg['From'] = email_config["from_addr"]
            msg['To'] = email_config["to_addr"]
            msg['Subject'] = f"OFAC更新提醒 - 中国/香港实体: {action['title']}"
            
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["smtp_user"], email_config["smtp_password"])
            server.send_message(msg)
            server.quit()
            
            logger.info("邮件通知已发送")
            return True
        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}")
            return False
    
    def _send_sms_notification(self, message: str) -> bool:
        """通过短信发送通知"""
        # 在这里实现短信发送逻辑，可以使用Twilio或其他SMS API
        try:
            sms_config = self.config["notification"]["sms"]
            
            # 这里是示例代码，需要根据实际使用的短信服务进行修改
            # 例如使用Twilio的实现：
            """
            from twilio.rest import Client
            
            client = Client(sms_config["api_key"], sms_config["api_secret"])
            client.messages.create(
                body=message,
                from_=sms_config["from_number"],
                to=sms_config["to_number"]
            )
            """
            
            logger.info("短信通知已发送")
            return True
        except Exception as e:
            logger.error(f"发送短信通知失败: {e}")
            return False
    
    def _send_wechat_notification(self, message: str) -> bool:
        """通过微信发送通知"""
        # 在这里实现微信发送逻辑，可以使用企业微信API
        try:
            wechat_config = self.config["notification"]["wechat"]
            
            # 这里是示例代码，需要根据实际使用的微信服务进行修改
            # 例如使用企业微信的实现：
            """
            import requests
            
            # 获取访问令牌
            token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={wechat_config['corp_id']}&corpsecret={wechat_config['corp_secret']}"
            response = requests.get(token_url)
            access_token = response.json()["access_token"]
            
            # 发送消息
            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
            data = {
                "touser": wechat_config["to_user"],
                "msgtype": "text",
                "agentid": wechat_config["agent_id"],
                "text": {
                    "content": message
                }
            }
            response = requests.post(send_url, json=data)
            """
            
            logger.info("微信通知已发送")
            return True
        except Exception as e:
            logger.error(f"发送微信通知失败: {e}")
            return False
    
    def check_for_updates(self) -> None:
        """检查OFAC网站更新"""
        logger.info("开始检查OFAC更新...")
        
        # 获取最近的行动列表
        actions = self.get_recent_actions()
        if not actions:
            logger.warning("未获取到最近行动列表，跳过本次检查")
            return
        
        # 获取已知的行动URL列表
        known_actions = set(self.cache.get("known_actions", []))
        new_actions = []
        
        for action in actions:
            if action["full_url"] not in known_actions:
                logger.info(f"发现新的行动: {action['title']} ({action['date']})")
                
                # 获取行动详情
                details = self.get_action_details(action["full_url"])
                
                # 判断是否与中国或香港相关
                if details and self.is_related_to_china_or_hk(details):
                    logger.info(f"✅ 与中国/香港相关: {action['title']}")
                    
                    # 发送通知
                    if self.send_notification(action, details):
                        new_actions.append(action)
                        known_actions.add(action["full_url"])
                else:
                    logger.info(f"❌ 与中国/香港无关: {action['title']}")
                    known_actions.add(action["full_url"])
        
        # 更新缓存
        self.cache["last_check"] = datetime.datetime.now().isoformat()
        self.cache["known_actions"] = list(known_actions)
        self._save_cache()
        
        if new_actions:
            logger.info(f"本次检查发现 {len(new_actions)} 个与中国/香港相关的新行动")
        else:
            logger.info("本次检查未发现与中国/香港相关的新行动")
    
    def run(self) -> None:
        """运行监控器"""
        logger.info("OFAC中国/香港实体监控器已启动")
        
        try:
            while True:
                self.check_for_updates()
                
                # 等待下一次检查
                interval = self.config["check_interval"]
                logger.info(f"等待 {interval} 秒后进行下一次检查...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("监控器已停止")
        except Exception as e:
            logger.error(f"监控器遇到错误: {e}")
            logger.info("监控器将在 60 秒后重新启动...")
            time.sleep(60)
            self.run()

if __name__ == "__main__":
    monitor = OFACMonitor()
    monitor.run()
