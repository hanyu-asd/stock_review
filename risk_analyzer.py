import logging
from datetime import datetime


def generate_risk_alerts(data):
    """
    完全动态化风险提示生成
    所有条件基于当日真实数据，无静态占位
    """
    risks = []

    indices = data.get('indices', {})
    if not isinstance(indices, dict):
        indices = {}

    sh = indices.get('上证指数', {})
    cy = indices.get('创业板指', {})
    sz = indices.get('上证50', {})
    kc = indices.get('科创50', {})

    sh_price = sh.get('最新价', 0)
    sh_pct = sh.get('涨跌幅', 0)
    cy_pct = cy.get('涨跌幅', 0)
    sz_pct = sz.get('涨跌幅', 0)
    kc_pct = kc.get('涨跌幅', 0)

    market = data.get('market', {})
    vol_today = market.get('total_vol', 0)
    up_count = market.get('up', 0)
    down_count = market.get('down', 0)
    limit_up = market.get('limit_up', 0)
    limit_down = market.get('limit_down', 0)

    weekly = data.get('weekly', {})
    vol_trend = weekly.get('vol_trend', [])
    trend_dir = weekly.get('trend_direction', '震荡')

    # ---------- 风险1：业绩披露风险（动态时间窗口） ----------
    now = datetime.now()
    month = now.month
    day = now.day
    # 动态判断业绩披露窗口
    is_earnings_window = False
    # 年报：1-4月
    if month in [1, 2, 3, 4]:
        is_earnings_window = True
    # 中报：7-8月
    if month in [7, 8]:
        is_earnings_window = True
    # 一季报：4月
    if month == 4:
        is_earnings_window = True
    # 三季报：10月
    if month == 10:
        is_earnings_window = True
    
    if is_earnings_window:
        if month == 4:
            risks.append("📊 4月为一季报/年报密集披露期，业绩不达预期标的面临调整风险")
        elif month in [7, 8]:
            risks.append("📊 当前处于中报披露窗口期，业绩变脸及不及预期标的面临回调风险")
        elif month == 10:
            risks.append("📊 10月为三季报密集披露期，关注业绩确定性和估值匹配度")
        elif month in [1, 2, 3]:
            risks.append("📊 年报披露季即将来临，关注业绩预告及估值修复机会")

    # ---------- 风险2：套牢盘压力（基于实际点位） ----------
    if sh_price > 3800:
        risks.append(f"📈 上证指数{sh_price:.0f}点接近前期密集套牢区（3800-3850点），突破需持续增量资金配合")

    # ---------- 风险3：风格分化风险（基于实时数据） ----------
    if abs(cy_pct) > 0.1 and abs(sz_pct) > 0.1:
        diff = cy_pct - sz_pct
        if diff > 1.5:
            risks.append(f"🔄 创业板（{cy_pct:+.2f}%）与上证50（{sz_pct:+.2f}%）分化达{diff:.1f}%，若权重补跌可能拖累全市场")
        elif diff < -1.5:
            risks.append(f"🔄 上证50（{sz_pct:+.2f}%）强于创业板（{cy_pct:+.2f}%）达{abs(diff):.1f}%，需关注风格切换持续性")

    # ---------- 风险4：量能萎缩风险 ----------
    if vol_trend and len(vol_trend) > 2:
        try:
            vol_avg = sum(vol_trend) / len(vol_trend) / 1e8
            if vol_today > 0 and vol_avg > 0:
                vol_ratio = vol_today / vol_avg
                if vol_ratio < 0.75:
                    risks.append(f"📉 今日成交额{vol_today:.0f}亿低于近期均值{vol_avg:.0f}亿（{vol_ratio*100:.0f}%），若持续缩量需警惕流动性收缩")
                elif vol_ratio > 1.5:
                    risks.append(f"📈 今日成交额{vol_today:.0f}亿高于近期均值{vol_avg:.0f}亿（{vol_ratio*100:.0f}%），放量突破需验证持续性")
        except:
            pass

    # ---------- 风险5：板块拥挤度风险 ----------
    sector_top = data.get('sector_top5', [])
    sector_bottom = data.get('sector_bottom5', [])
    if sector_top and sector_bottom:
        try:
            top_pct = sector_top[0][1] if len(sector_top[0]) > 1 else 0
            bottom_pct = sector_bottom[0][1] if len(sector_bottom[0]) > 1 else 0
            gap = top_pct - bottom_pct
            if gap > 4:
                risks.append(f"🎯 领涨与领跌板块差异达{gap:.1f}%，资金高度集中，警惕强势板块获利回吐")
        except:
            pass

    # ---------- 风险6：趋势反转风险 ----------
    if trend_dir == "上升" and sh_pct < -1 and cy_pct < -0.5:
        risks.append("📉 上证指数单日跌幅较大，需关注周线级别上升趋势是否被破坏")
    elif trend_dir == "下降" and sh_pct > 1 and cy_pct > 1.5:
        risks.append("📈 市场出现反弹信号，关注是否形成趋势反转")

    # ---------- 风险7：外部风险 ----------
    for news in data.get('news', []):
        if '海外' in news or '美股' in news or '外围' in news or '美联储' in news:
            risks.append("🌍 需关注海外市场波动对明日A股开盘情绪的影响")
            break

    # ---------- 风险8：涨跌家数异常 ----------
    if up_count > 0 and down_count > 0:
        ratio = up_count / down_count
        if ratio > 3:
            risks.append(f"📊 上涨家数是下跌家数的{ratio:.1f}倍，市场情绪过热，警惕回调风险")
        elif ratio < 0.3:
            risks.append(f"📊 下跌家数是上涨家数的{1/ratio:.1f}倍，市场情绪低迷，关注是否有超跌反弹机会")

    # ---------- 如果没有任何风险触发，生成温和提示 ----------
    if not risks:
        risks.append(f"📊 上证指数{sh_pct:+.2f}%，创业板{cy_pct:+.2f}%，市场整体运行平稳")
        risks.append("📊 关注量能变化、外部事件及中报业绩披露情况")

    # 最多保留5条
    return risks[:5]