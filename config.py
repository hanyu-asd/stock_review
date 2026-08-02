import os

# 从环境变量读取配置（GitHub Secrets 注入）
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.qq.com")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_FROM_PASSWORD = os.getenv("EMAIL_FROM_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# 本地目录
REPORT_DIR = "./reports"
TEMPLATE_DIR = "./templates"