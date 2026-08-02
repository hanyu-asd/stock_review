import os
import requests
import logging


def call_ai_analysis(data):
    """调用ModelScope API生成情绪总结和明日展望（基于当日+周数据）"""
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN")
    model = os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen2.5-72B-Instruct")

    if not api_key:
        logging.warning("⚠️ 未配置 MODELSCOPE_SDK_TOKEN，跳过AI分析")
        return None

    # 当日数据摘要
    daily_summary = f"""
【今日指数】上证{data['indices']['上证指数']['涨跌幅']:.2f}%，创业板{data['indices']['创业板指']['涨跌幅']:.2f}%，科创50{data['indices']['科创50']['涨跌幅']:.2f}%。
【涨跌分布】上涨{data['market']['up']}家，下跌{data['market']['down']}家，涨停{data['market']['limit_up']}家。
【领涨板块】{', '.join([f'{s[0]}{s[1]:+.2f}%' for s in data['sector_top5'][:3]])}。
【领跌板块】{', '.join([f'{s[0]}{s[1]:+.2f}%' for s in data['sector_bottom5'][:3]])}。
【资金流向】电子净流入{data['fund_in'][0][1]:.1f}亿，银行净流出{abs(data['fund_out'][0][1]):.1f}亿。
"""

    # 周趋势数据
    weekly = data.get('weekly', {})
    weekly_summary = f"""
【本周趋势】{weekly.get('trend_direction', '震荡')}，周振幅约{weekly.get('trend_strength', 0):.1f}%
【本周交易日】{len(weekly.get('dates', []))}天
"""

    # 消息面
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
            content = response.json()["choices"][0]["message"]["content"]
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
            logging.info(f"✅ AI分析生成成功 (使用模型: {model})")
            return result
        else:
            logging.error(f"ModelScope API返回错误: {response.text}")
            return None
    except Exception as e:
        logging.error(f"ModelScope API调用异常: {e}")
        return None


def generate_template_outlook(data):
    """AI不可用时的降级模板（基于当日+周数据）"""
    weekly = data.get('weekly', {})
    direction = weekly.get('trend_direction', '震荡')
    strength = weekly.get('trend_strength', 0)

    if direction == "上升" and strength > 2:
        trend = f"本周趋势向上（+{strength:.1f}%），短期偏强但需警惕获利回吐"
    elif direction == "下降" and strength > 2:
        trend = f"本周趋势向下（-{strength:.1f}%），关注权重股能否企稳"
    else:
        trend = "市场震荡磨底，结构分化延续"

    top_sector = data['sector_top5'][0][0] if data['sector_top5'] else "科技"
    return {
        'core': f"本周{trend}。量能变化是关键观察信号。",
        'config': f"关注{top_sector}持续性和量能变化；防御配置高股息板块。"
    }