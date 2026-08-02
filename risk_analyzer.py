import logging
from datetime import datetime

def generate_risk_alerts(data):
    """基于数据动态生成风险提示"""
    risks = []

    # ---------- 安全获取指数数据 ----------
    indices = data.get('indices', {})
    if not isinstance(indices, dict):
        indices = {}

    sh = indices.get('上证指数', {})
    cy = indices.get('创业板指', {})
    sz = indices.get('上证50', {})

    sh_price = sh.get('最新价', 0) if sh else 0
    sh_pct = sh.get('涨跌幅', 0) if sh else 0
    cy_pct = cy.get('涨跌幅', 0) if cy else 0
    sz_pct = sz.get('涨跌幅', 0) if sz else 0

    market = data.get('market', {})
    vol_today = market.get('total_vol', 0)

    weekly = data.get('weekly', {})
    vol_trend = weekly.get('vol_trend', [])

    # ---------- 各风险条件 ----------
    # 1. 中报业绩风险（8月窗口）
    if datetime.now().month == 8:
        risks.append("📊 8月进入中报密集披露期，无业绩支撑标的面临回调风险")

    # 2. 套牢盘压力
    if sh_price > 3800:
        risks.append(f"📈 上证指数{sh_price:.0f}点接近前期密集套牢区（3850点上方），突破需持续增量资金配合")

    # 3. 风格切换风险
    if abs(cy_pct) > 0.1 and abs(sz_pct) > 0.1 and (cy_pct - sz_pct) > 2:
        risks.append(f"🔄 创业板（{cy_pct:+.2f}%）与上证50（{sz_pct:+.2f}%）分化超2%，若权重持续走弱可能拖累全市场")

    # 4. 量能萎缩风险
    if vol_trend and len(vol_trend) > 1:
        try:
            vol_avg = sum(vol_trend) / len(vol_trend) / 1e8
            if vol_today > 0 and vol_avg > 0 and vol_today < vol_avg * 0.85:
                risks.append(f"📉 今日成交额{vol_today:.0f}亿低于本周日均{vol_avg:.0f}亿，若持续缩量需注意流动性风险")
        except:
            pass

    # 5. 板块拥挤度
    sector_top = data.get('sector_top5', [])
    sector_bottom = data.get('sector_bottom5', [])
    if sector_top and sector_bottom:
        try:
            top_pct = sector_top[0][1] if len(sector_top[0]) > 1 else 0
            bottom_pct = sector_bottom[0][1] if len(sector_bottom[0]) > 1 else 0
            if (top_pct - bottom_pct) > 5:
                risks.append(f"🎯 领涨与领跌板块差异达{top_pct - bottom_pct:.1f}%，资金高度集中，警惕强势板块回调")
        except:
            pass

    # 6. 外部风险
    for news in data.get('news', []):
        if '海外' in news or '美股' in news or '外围' in news:
            risks.append("🌍 需关注海外市场波动对明日A股开盘情绪的影响")
            break

    if not risks:
        risks = ["📊 市场整体运行平稳，但需持续关注量能变化及外部事件冲击"]

    return risks[:5]