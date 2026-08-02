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
    amount_trend = weekly.get('amount_trend', [])
    trend_dir = weekly.get('trend_direction', '震荡')

    # ---------- 风险1：业绩披露风险（动态时间窗口） ----------
    now = datetime.now()
    month = now.month
    day = now.day
    
    # 动态判断业绩披露窗口
    is_earnings_window = False
    if month in [1, 2, 3, 4]:  # 年报+一季报
        is_earnings_window = True
        report_type = "年报/一季报" if month == 4 else "年报"
    elif month in [7, 8]:  # 中报
        is_earnings_window = True
        report_type = "中报"
    elif month == 10:  # 三季报
        is_earnings_window = True
        report_type = "三季报"
    
    if is_earnings_window:
        risks.append(f"📊 当前处于{report_type}披露窗口期，业绩变脸及不及预期标的面临回调风险")

    # ---------- 风险2：套牢盘压力 ----------
    if sh_price > 3800:
        risks.append(f"📈 上证指数{sh_price:.0f}点接近前期密集套牢区（3800-3850点），突破需持续增量资金配合")

    # ---------- 风险3：风格分化 ----------
    if abs(cy_pct) > 0.1 and abs(sz_pct) > 0.1:
        diff = cy_pct - sz_pct
        if diff > 1.5:
            risks.append(f"🔄 创业板（{cy_pct:+.2f}%）与上证50（{sz_pct:+.2f}%）分化达{diff:.1f}%，若权重补跌可能拖累全市场")
        elif diff < -1.5:
            risks.append(f"🔄 上证50（{sz_pct:+.2f}%）强于创业板（{cy_pct:+.2f}%）达{abs(diff):.1f}%，需关注风格切换持续性")

    # ---------- 风险4：量能变化风险（修复：基于成交额对比） ----------
    # 优先使用成交额趋势（amount_trend），如果没有则用量能趋势
    if amount_trend and len(amount_trend) >= 3:
        try:
            # 取最近3-5日均值
            avg_vol = sum(amount_trend[-5:]) / len(amount_trend[-5:])
            if vol_today > 0 and avg_vol > 0:
                vol_ratio = vol_today / avg_vol
                if vol_ratio < 0.7:
                    risks.append(f"📉 今日成交额{vol_today:.0f}亿显著低于近5日均值{avg_vol:.0f}亿（{vol_ratio*100:.0f}%），若持续缩量需警惕流动性收缩")
                elif vol_ratio > 1.6:
                    risks.append(f"📈 今日成交额{vol_today:.0f}亿显著高于近5日均值{avg_vol:.0f}亿（{vol_ratio*100:.0f}%），放量突破需验证持续性")
                elif vol_ratio > 1.2:
                    risks.append(f"📈 今日成交额{vol_today:.0f}亿高于近5日均值{avg_vol:.0f}亿，量能温和放大")
        except:
            pass
    elif vol_trend and len(vol_trend) >= 3:
        # 如果没有成交额趋势，用量能趋势代替
        try:
            avg_vol = sum(vol_trend[-5:]) / len(vol_trend[-5:])
            if vol_today > 0 and avg_vol > 0:
                vol_ratio = vol_today / avg_vol
                if vol_ratio < 0.7:
                    risks.append(f"📉 今日成交额{vol_today:.0f}亿显著低于近期水平，若持续缩量需警惕流动性收缩")
                elif vol_ratio > 1.6:
                    risks.append(f"📈 今日成交额{vol_today:.0f}亿显著高于近期水平，放量突破需验证持续性")
        except:
            pass

    # ---------- 风险5：板块拥挤度 ----------
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

    # ---------- 风险6：趋势反转信号 ----------
    if trend_dir == "上升" and sh_pct < -1 and cy_pct < -0.5:
        risks.append("📉 上证指数单日跌幅较大，需关注周线级别上升趋势是否被破坏")
    elif trend_dir == "下降" and sh_pct > 1 and cy_pct > 1.5:
        risks.append("📈 市场出现反弹信号，关注是否形成趋势反转")

    # ---------- 风险7：外部风险 ----------
    for news in data.get('news', []):
        if any(k in news for k in ['海外', '美股', '外围', '美联储', '地缘', '冲突']):
            risks.append("🌍 需关注海外市场波动及地缘政治对A股开盘情绪的影响")
            break

    # ---------- 风险8：涨跌家数异常 ----------
    if up_count > 0 and down_count > 0:
        ratio = up_count / down_count if down_count > 0 else 10
        if ratio > 3:
            risks.append(f"📊 上涨家数是下跌家数的{ratio:.1f}倍，市场情绪过热，警惕回调风险")
        elif ratio < 0.3:
            risks.append(f"📊 下跌家数是上涨家数的{1/ratio:.1f}倍，市场情绪低迷，关注超跌反弹机会")

    # ---------- 风险9：涨跌停异常 ----------
    if limit_up > 150:
        risks.append(f"🚀 涨停家数达{limit_up}家，市场局部过热，需警惕监管风险")
    if limit_down > 50:
        risks.append(f"💀 跌停家数达{limit_down}家，部分标的流动性风险凸显")

    # ---------- 如果没有任何风险触发 ----------
    if not risks:
        risks.append(f"📊 上证指数{sh_pct:+.2f}%，创业板{cy_pct:+.2f}%，市场整体运行平稳")
        risks.append("📊 关注量能变化、外部事件及中报业绩披露情况")

    # 最多保留6条
    return risks[:6]