"""
动态风险提示生成器
基于当日数据 + 周数据，自动生成有数据支撑的风险提示
"""
import logging
from datetime import datetime


def generate_risk_alerts(data):
    """基于数据动态生成风险提示"""
    risks = []

    # 1. 中报业绩风险（8月窗口）
    if datetime.now().month == 8:
        risks.append("📊 8月进入中报密集披露期，无业绩支撑标的面临回调风险")

    # 2. 套牢盘压力（基于指数点位）
    sh_price = data['indices']['上证指数']['最新价']
    if sh_price > 3800:
        risks.append(f"📈 上证指数{sh_price:.0f}点接近前期密集套牢区（3850点上方），突破需持续增量资金配合")

    # 3. 风格切换风险（基于涨跌幅分化）
    cy_diff = data['indices']['创业板指']['涨跌幅']
    sz_diff = data['indices']['上证50']['涨跌幅']
    if cy_diff - sz_diff > 2:
        risks.append(f"🔄 创业板（{cy_diff:+.2f}%）与上证50（{sz_diff:+.2f}%）分化超2%，若权重持续走弱可能拖累全市场")

    # 4. 量能萎缩风险
    vol_today = data['market']['total_vol']
    weekly = data.get('weekly', {})
    vol_trend = weekly.get('vol_trend', [])
    if vol_trend:
        vol_avg = sum(vol_trend) / len(vol_trend) / 1e8  # 转为亿元
        if vol_today < vol_avg * 0.85 and vol_avg > 0:
            risks.append(f"📉 今日成交额{vol_today:.0f}亿低于本周日均{vol_avg:.0f}亿，若持续缩量需注意流动性风险")

    # 5. 板块拥挤度风险
    if data['sector_top5'] and data['sector_bottom5']:
        top_concentration = data['sector_top5'][0][1] - data['sector_bottom5'][0][1]
        if top_concentration > 5:
            risks.append(f"🎯 领涨与领跌板块差异达{top_concentration:.1f}%，资金高度集中，警惕强势板块回调")

    # 6. 外部风险提醒（基于消息面关键词）
    for news in data.get('news', []):
        if '海外' in news or '美股' in news or '外围' in news:
            risks.append("🌍 需关注海外市场波动对明日A股开盘情绪的影响")
            break

    # 如果没有触发任何风险，给一个温和提示
    if not risks:
        risks = ["📊 市场整体运行平稳，但需持续关注量能变化及外部事件冲击"]

    # 最多保留5条，避免过长
    return risks[:5]