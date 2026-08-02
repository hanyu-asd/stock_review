#!/usr/bin/env python3
import logging
import sys
from data_fetcher import fetch_market_data
from report_generator import generate_report
from email_sender import send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def main():
    logging.info("🚀 开始执行盘后复盘自动化任务")
    
    try:
        # 1. 采集数据
        logging.info("📊 步骤1: 采集市场数据...")
        data = fetch_market_data()
        
        # 2. 生成报告
        logging.info("📝 步骤2: 生成复盘报告...")
        wechat_html, filepath = generate_report(data)
        
        # 3. 发送邮件
        logging.info("📧 步骤3: 发送邮件...")
        subject = f"A股复盘日报 {data['date']}"
        success = send_email(wechat_html, subject)
        
        if success:
            logging.info("✅ 全流程执行成功！")
        else:
            logging.warning("⚠️ 报告已生成，但邮件发送失败")
            
    except Exception as e:
        logging.error(f"❌ 执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()