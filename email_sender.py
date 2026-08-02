import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import logging
from config import EMAIL_SMTP_SERVER, EMAIL_FROM, EMAIL_FROM_PASSWORD, EMAIL_TO


def send_email(wechat_html, subject=None):
    if not all([EMAIL_FROM, EMAIL_FROM_PASSWORD, EMAIL_TO]):
        logging.error("❌ 邮件配置不完整，请检查 Secrets")
        return False

    if subject is None:
        from datetime import datetime
        subject = f"A股复盘日报 {datetime.now().strftime('%Y-%m-%d')}"

    try:
        logging.info(f"📧 尝试发送邮件: {EMAIL_FROM} -> {EMAIL_TO} (服务器: {EMAIL_SMTP_SERVER})")

        msg = MIMEMultipart('alternative')
        # 修复：直接使用邮箱地址，不加显示名称
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = Header(subject, 'utf-8')

        text_part = MIMEText("请查看HTML内容", 'plain', 'utf-8')
        msg.attach(text_part)

        html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: 'PingFang SC','Microsoft YaHei',sans-serif; max-width: 700px; margin:0 auto; padding:20px; background:#f5f6fa;">
<div style="background:#fff; border-radius:12px; padding:20px;">
    <p style="font-size:22px;font-weight:700;color:#1a73e8;">📈 A股复盘日报</p>
    <p style="font-size:14px;color:#888;">{subject.replace('A股复盘日报 ', '')} · 盘后分析</p>
    <hr style="border:none;border-top:2px solid #1a73e8;">
</div>
<div style="background:#fff8e1; border-radius:12px; padding:16px 20px; margin:16px 0; font-size:13px; color:#795548;">
    <p><strong>📋 公众号发布指引</strong></p>
    <p>1. 全选复制下方「公众号复制版」内容</p>
    <p>2. 打开「公众号助手」App → 新建图文 → 粘贴</p>
</div>
<div style="background:#f8f9fa; border:1px solid #ddd; border-radius:8px; padding:16px; font-size:14px; line-height:1.8; color:#222;">
    {wechat_html}
</div>
<div style="text-align:center;color:#aaa;font-size:12px;margin-top:20px;">—— 仅供参考 · 不构成投资建议 ——</div>
</body>
</html>
        """
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)

        if 'qq.com' in EMAIL_SMTP_SERVER or '163.com' in EMAIL_SMTP_SERVER:
            server = smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, 465, timeout=30)
        else:
            server = smtplib.SMTP(EMAIL_SMTP_SERVER, 587, timeout=30)
            server.starttls()

        server.login(EMAIL_FROM, EMAIL_FROM_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()

        logging.info(f"✅ 邮件发送成功 -> {EMAIL_TO}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logging.error(f"❌ SMTP认证失败: {e}")
        logging.error("  请检查 EMAIL_FROM 和 EMAIL_FROM_PASSWORD (授权码) 是否正确")
        return False
    except smtplib.SMTPConnectError as e:
        logging.error(f"❌ SMTP连接失败: {e}")
        logging.error(f"  无法连接到 {EMAIL_SMTP_SERVER}，请检查网络或服务器地址")
        return False
    except smtplib.SMTPException as e:
        logging.error(f"❌ SMTP错误: {e}")
        return False
    except socket.timeout:
        logging.error(f"❌ SMTP连接超时: {EMAIL_SMTP_SERVER} 响应太慢")
        return False
    except Exception as e:
        logging.error(f"❌ 邮件发送失败: {e}")
        return False