import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import logging
from config import EMAIL_SMTP_SERVER, EMAIL_FROM, EMAIL_FROM_PASSWORD, EMAIL_TO

def send_email(wechat_html, subject=None):
    """发送邮件，包含公众号复制版和邮件预览版"""
    if not all([EMAIL_FROM, EMAIL_FROM_PASSWORD, EMAIL_TO]):
        logging.error("❌ 邮件配置不完整，请检查 Secrets")
        return False
    
    if subject is None:
        from datetime import datetime
        subject = f"A股复盘日报 {datetime.now().strftime('%Y-%m-%d')}"
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = Header(f"A股复盘助手 <{EMAIL_FROM}>")
        msg['To'] = Header(f"收件人 <{EMAIL_TO}>")
        msg['Subject'] = Header(subject, 'utf-8')
        
        # ---- 纯文本版（兜底） ----
        text_plain = f"""
📈 A股复盘日报
{subject.replace('A股复盘日报 ', '')} · 盘后分析

详细数据请查看邮件中的HTML内容，或复制下方“公众号复制版”到公众号发布。
        """
        plain_part = MIMEText(text_plain, 'plain', 'utf-8')
        msg.attach(plain_part)
        
        # ---- 邮件正文（预览版 + 复制区） ----
        # 构建完整的邮件HTML，包含预览和复制区
        mail_html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: 'PingFang SC','Microsoft YaHei',sans-serif; max-width: 700px; margin:0 auto; padding:20px; background:#f5f6fa;">

<div style="background:#fff; border-radius:12px; padding:20px; margin-bottom:16px;">
    <p style="font-size:22px;font-weight:700;color:#1a73e8;">📈 A股复盘日报</p>
    <p style="font-size:14px;color:#888;">{subject.replace('A股复盘日报 ', '')} · 盘后分析</p>
    <hr style="border:none;border-top:2px solid #1a73e8;">
    <!-- 此处可以放一个简要预览，也可以直接放wechat内容作为预览 -->
    <!-- 但我们下面会专门给出复制区，预览区可以简单放个提示 -->
    <p style="font-size:16px;color:#333;">邮件预览版（仅供参考）</p>
    <p style="font-size:14px;color:#666;">下方灰色区域是可直接复制到公众号的排版内容，请下滑查看。</p>
</div>

<div style="background:#fff8e1; border-radius:12px; padding:16px 20px; margin-bottom:16px; font-size:13px; color:#795548;">
    <p><strong>📋 公众号发布指引</strong></p>
    <p style="margin:4px 0;">1. 全选复制下方 <strong style="color:#1a73e8;">「公众号复制版」</strong> 内容</p>
    <p style="margin:4px 0;">2. 打开「公众号助手」App → 新建图文 → 粘贴</p>
    <p style="margin:4px 0;">3. 检查格式 → 发布</p>
</div>

<div style="background:#fff; border-radius:12px; padding:20px; border:1px solid #ddd;">
    <p style="font-size:16px; font-weight:700; color:#1a73e8;">📋 公众号复制版（全选复制下方灰色区域）</p>
    <div style="background:#f8f9fa; border:1px solid #ddd; border-radius:8px; padding:16px; font-size:14px; line-height:1.8; color:#222; user-select: all;">
        {wechat_html}
    </div>
</div>

<div style="text-align:center;color:#aaa;font-size:12px;margin-top:20px;padding-top:16px;border-top:1px solid #eee;">
    —— 自动化复盘报告 · 仅供参考 · 不构成投资建议 ——
</div>

</body>
</html>
        """
        html_part = MIMEText(mail_html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 发送
        if 'qq.com' in EMAIL_SMTP_SERVER or '163.com' in EMAIL_SMTP_SERVER:
            server = smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, 465, timeout=30)
        else:
            server = smtplib.SMTP(EMAIL_SMTP_SERVER, 25, timeout=30)
            server.starttls()
        
        server.login(EMAIL_FROM, EMAIL_FROM_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()
        
        logging.info(f"✅ 邮件发送成功 -> {EMAIL_TO}")
        return True
        
    except Exception as e:
        logging.error(f"❌ 邮件发送失败: {e}")
        return False