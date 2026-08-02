import os
import requests
import logging


def call_ai_analysis(data):
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN")
    model = os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen2.5-72B-Instruct")

    if not api_key:
        logging.warning("⚠️ 未配置 MODELSCOPE_SDK_TOKEN，跳过AI分析")
        return None

    try:
        sh = data['indices'].get('上证指数', {})
        cy = data['indices'].get('创业板指', {})
        kc = data['indices'].get('科创50', {})
        market = data.get('market', {})
        sector_top = data.get('sector_top5', [["传媒", 2.5], ["计算机", 2.1], ["通信", 1.8]])
        sector_bottom = data.get('sector_bottom5', [["银行", -0.5], ["煤炭", -0.3], ["石油", -0.2]])
        fund_in = data.get('fund_in', [["电子", 30.7], ["计算机", 9.7]])
        fund_out = data.get('fund_out', [["银行", -5.69], ["食品饮料", -3.2]])

        daily_summary = f"""
【今日指数】上证{sh.get('涨跌幅', 0):.2f}%，创业板{cy.get('涨跌幅', 0):.2f}%，科创50{kc.get('涨跌幅', 0):.2f}%。
【涨跌分布】上涨{market.get('up', 0)}家，下跌{market.get('down', 0)}家，涨停{market.get('limit_up', 0)}家。
【领涨板块】{', '.join([f'{s[0]}{s[1]:+.2f}%' for s in sector_top[:3]])}。
【领跌板块】{', '.join([f'{s[0]}{s[1]:+.2f}%' for s in sector_bottom[:3]])}。
【资金流向】电子净流入{fund_in[0][1] if fund_in else 0:.1f}亿，银行净流出{abs(fund_out[0][1]) if fund_out else 0:.1f}亿。
"""
    except Exception as e:
        logging.warning(f"构建摘要失败: {e}")
        return None

    weekly = data.get('weekly', {})
    weekly_summary = f"""
【本周趋势】{weekly.get('trend_direction', '震荡')}，周振幅约{weekly.get('trend_strength', 0):.1f}%
"""

    news_summary = ""
    if data.get("news"):
        news_summary = f"\n【今日要闻】{'; '.join(data['news'][:3])}"

    prompt = f"""
你是一个A股复盘分析师。结合今日数据和本周趋势，生成明日展望。

【今日数据】{daily_summary}
【本周趋势】{weekly_summary}
{news_summary}

要求：
1. 结合一周趋势做判断，而非单日波动
2. 100字以内，分两段：核心判断 + 配置建议
3. 只做事实归纳，不推荐个股，不预测具体点位
4. 使用"需关注"、"若…则…"等条件句式

输出格式（严格按此格式）：
核心判断：xxx
配置建议：进攻端xxx；防守端xxx
"""

    try:
        base_url = "https://api-inference.modelscope.cn/v1/"
        response = requests.post(
            f"{base_url}chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.6,
                "max_tokens": 300
            },
            timeout=15
        )

        if response.status_code == 200:
            resp_json = response.json()
            choices = resp_json.get('choices', [])
            if choices and len(choices) > 0:
                message = choices[0].get('message', {})
                content = message.get('content', '')
                if content:
                    lines = [line.strip() for line in content.split('\n') if line.strip()]
                    result = {}
                    for line in lines[:2]:
                        if '核心' in line:
                            result['core'] = line.replace('核心判断：', '').replace('核心：', '').strip()
                        elif '配置' in line:
                            result['config'] = line.replace('配置建议：', '').replace('建议：', '').strip()
                    if not result.get('core'):
                        result['core'] = lines[0] if lines else ""
                        result['config'] = lines[1] if len(lines) > 1 else ""
                    logging.info(f"✅ AI分析生成成功")
                    return result
        else:
            logging.error(f"ModelScope API返回错误: {response.status_code}, {response.text[:200]}")
            return None
    except Exception as e:
        logging.error(f"ModelScope API调用异常: {e}")
        return None

    return None


def generate_template_outlook(data):
    weekly = data.get('weekly', {})
    direction = weekly.get('trend_direction', '震荡')
    strength = weekly.get('trend_strength', 0)

    if direction == "上升" and strength > 2:
        trend = f"本周趋势向上（+{strength:.1f}%），短期偏强但需警惕获利回吐"
    elif direction == "下降" and strength > 2:
        trend = f"本周趋势向下（-{strength:.1f}%），关注权重股能否企稳"
    else:
        trend = "市场震荡磨底，结构分化延续"

    top_sector = data.get('sector_top5', [["科技", 0]])[0][0] if data.get('sector_top5') else "科技"
    return {
        'core': f"本周{trend}。量能变化是关键观察信号。",
        'config': f"关注{top_sector}持续性和量能变化；防御配置高股息板块。"
    }