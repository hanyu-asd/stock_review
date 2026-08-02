import os
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import logging
from config import REPORT_DIR, TEMPLATE_DIR

def generate_report(data):
    """生成公众号兼容版HTML（无html/head/body包裹）"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("review_template_wechat.html")
    wechat_html = template.render(data=data)
    
    filename = f"wechat_{datetime.now().strftime('%Y%m%d')}.html"
    filepath = os.path.join(REPORT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(wechat_html)
    
    logging.info(f"✅ 报告已生成: {filepath}")
    return wechat_html, filepath