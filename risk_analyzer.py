import logging
from datetime import datetime


def generate_risk_alerts(data):
    """
    完全基于真实数据生成风险提示
    如果数据为 None 或空，跳过该条风险判断
    """
    risks = []

    indices = data.get('indices', {})
    if not indices:
        return ["📊 指数数据暂不可用，无法生成风险提示"]

    sh = indices.get('上证指数', {})
    cy = indices.get('创业板指', {})
    sz = indices.get('上证50', {})

    sh_price = sh.get('最新价')
    sh_pct = sh.get('涨跌幅')
    cy_pct = cy.get('涨跌幅')
    sz_pct = sz.get('涨跌幅')

    market = data.get('market', {})
    up = market.get('up')
    down = market.get('down')
    limit_up = market.get('limit_up')
    limit_down = market.get('limit_down')
    vol_today = market.get('total_vol')

    weekly = data.get('weekly', {})
    vol_trend = weekly.get('vol_trend', [])

    # ---------- 风险1：业绩披露风险 ----------
    now = datetime.now()
    month = now.month
    day = now.day

    is_earnings_window = False
    earnings_desc = ""

    if month == 4:
        is_earnings_window = True
        earnings_desc = "一季报/年报密集披露期"
    elif month in [7, 8]:
        is_earnings_window = True
        earnings_desc = "中报密集披露期"
    elif month == 10:
        is_earnings_window = True
        earnings_desc = "三季报密集披露期"
    elif month in [1, 2, 3] and day <= 15:
        is_earnings_window = True
        earnings_desc = "年报业绩预告窗口期"

    if is_earnings_window:
        risks.append(f"📊 {earnings_desc}，业绩不达预期标的面临回调风险")

    # ---------- 风险2：套牢盘压力 ----------
    if sh_price is not None and sh_price > 0:
        index_trend = weekly.get('index_trend', {})
        if index_trend:
            recent_high = max(index_trend.values())
            if sh_price > recent_high * 0.98:
                risks.append(f"📈 上证指数{sh_price:.0f}点接近近期高点（{recent_high:.0f}），追高需谨慎")

    # ---------- 风险3：风格分化 ----------
    if sh_pct is not None and cy_pct is not None and sz_pct is not None:
        if abs(cy_pct) > 0.1 and abs(sz_pct) > 0.1:
            diff = cy_pct - sz_pct
            if diff > 1.5:
                risks.append(f"🔄 创业板（{cy_pct:+.2f}%）与上证50（{sz_pct:+.2f}%）分化达{diff:.1f}%，若权重补跌可能拖累全市场")
            elif diff < -1.5:
                risks.append(f"🔄 上证50（{sz_pct:+.2f}%）强于创业板（{cy_pct:+.2f}%）达{abs(diff):.1f}%，需关注风格切换持续性")

    # ---------- 风险4：量能萎缩 ----------
    if vol_today is not None and vol_today > 0 and vol_trend and len(vol_trend) > 2:
        try:
            vol_avg = sum(vol_trend) / len(vol_trend) / 1e8
            if vol_avg > 0:
                vol_ratio = vol_today / vol_avg
                if vol_ratio < 0.7:
                    risks.append(f"📉 今日成交额{vol_today:.0f}亿低于近期均值{vol_avg:.0f}亿（{vol_ratio*100:.0f}%），若持续缩量需警惕流动性收缩")
                elif vol_ratio > 1.5:
                    risks.append(f"📈 今日成交额{vol_today:.0f}亿高于近期均值{vol_avg:.0f}亿（{vol_ratio*100:.0f}%），放量突破需验证持续性")
        except:
            pass

    # ---------- 风险5：涨跌家数异常 ----------
    if up is not None and down is not None and up > 0 and down > 0:
        ratio = up / down
        if ratio > 3.5:
            risks.append(f"📊 上涨家数（{up}）是下跌家数（{down}）的{ratio:.1f}倍，市场情绪过热，警惕回调")
        elif ratio < 0.25:
            risks.append(f"📊 下跌家数（{down}）是上涨家数（{up}）的{1/ratio:.1f}倍，市场情绪低迷，关注超跌反弹机会")

    # ---------- 风险6：涨跌停异常 ----------
    if limit_up is not None and limit_down is not None:
        if limit_up > 100 and limit_down < 10:
            risks.append(f"🚀 涨停家数（{limit_up}）远多于跌停家数（{limit_down}），市场情绪极端亢奋，警惕情绪回落")
        elif limit_down > 50 and limit_up < 20:
            risks.append(f"💀 跌停家数（{limit_down}）显著增加（涨停{limit_up}家），市场恐慌情绪蔓延，需谨慎")

    # ---------- 风险7：外部风险 ----------
    for news in data.get('news', []):
        if any(k in news for k in ['海外', '美股', '外围', '美联储']):
            risks.append("🌍 需关注海外市场波动对明日A股开盘情绪的影响")
            break

    # ---------- 如果没有风险触发 ----------
    if not risks:
        if sh_pct is not None and cy_pct is not None:
            risks.append(f"📊 上证指数{sh_pct:+.2f}%，创业板{cy_pct:+.2f}%，市场整体运行平稳")
        else:
            risks.append("📊 指数数据不完整，部分风险判断不可用")

    return risks[:5]