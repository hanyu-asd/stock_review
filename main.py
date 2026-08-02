#!/usr/bin/env python3
import logging
import sys
from data_fetcher import fetch_market_data
from report_generator import generate_report
from email_sender import send_email
from ai_analyzer import call_ai_analysis, generate_template_outlook
from risk_analyzer import generate_risk_alerts

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

        # 2. AI分析
        logging.info("🤖 步骤2: AI生成明日展望...")
        ai_result = call_ai_analysis(data)
        if ai_result:
            data['ai_core'] = ai_result.get('core', '')
            data['ai_config'] = ai_result.get('config', '')
        else:
            template = generate_template_outlook(data)
            data['ai_core'] = template['core']
            data['ai_config'] = template['config']
            logging.info("使用模板降级生成展望")

        # 3. 动态风险提示
        logging.info("⚠️ 步骤3: 动态生成风险提示...")
        data['risks'] = generate_risk_alerts(data)

        # 调试：打印指数键名
        logging.info(f"🔍 indices keys: {list(data['indices'].keys())}")

        # 4. 生成报告
        logging.info("📝 步骤4: 生成复盘报告...")
        wechat_html, filepath = generate_report(data)

        # 5. 发送邮件
        logging.info("📧 步骤5: 发送邮件...")
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