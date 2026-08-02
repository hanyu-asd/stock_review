import os
import requests
import logging


def call_ai_analysis(data):
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN")
    model = os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen2.5-72B-Instruct")

    if not api_key:
        logging.warning("⚠️ 未配置 MODELSCOPE_SDK_TOKEN，跳过AI分析")
        return None

    # 检查数据完整性
    if not data.get('indices'):
        logging.warning("⚠️ 指数数据为空，无法进行AI分析")
        return None

    try:
        sh = data['indices'].get('上证指数', {})
        cy = data['indices'].get('创业板指', {})
        kc = data['indices'].get('科创50', {})
        market = data.get('market', {})
        sector_top = data.get('sector_top5', [])
        sector_bottom = data.get('sector_bottom5', [])
        fund_in = data.get('fund_in', [])
        fund_out = data.get('fund_out', [])

        # 只使用真实数据，不使用估算
        sh_pct = sh.get('涨跌幅')
        cy_pct = cy.get('涨跌幅')
        kc_pct = kc.get('涨跌幅')

        # 如果涨跌幅为 None，用 0 替代（但标记为未知）
        sh_pct_display = sh_pct if sh_pct is not None else "数据暂不可用"
        cy_pct_display = cy_pct if cy_pct is not None else "数据暂不可用"
        kc_pct_display = kc_pct if kc_pct is not None else "数据暂不可用"

        # 构建摘要（仅使用真实数据）
        daily_summary = f"""
【今日指数】上证{sh_pct_display}%，创业板{cy_pct_display}%，科创50{kc_pct_display}%。
"""

        if market.get('up') is not None:
            daily_summary += f"【涨跌分布】上涨{market.get('up', 0)}家，下跌{market.get('down', 0)}家，涨停{market.get('limit_up', 0)}家。\n"

        if sector_top:
            top_str = ', '.join([f'{s[0]}{s[1]:+.2f}%' for s in sector_top[:3]])
            daily_summary += f"【领涨板块】{top_str}。\n"

        if sector_bottom:
            bottom_str = ', '.join([f'{s[0]}{s[1]:+.2f}%' for s in sector_bottom[:3]])
            daily_summary += f"【领跌板块】{bottom_str}。\n"

        if fund_in and fund_out:
            daily_summary += f"【资金流向】{fund_in[0][0]}净流入{fund_in[0][1]:.1f}亿，{fund_out[0][0]}净流出{abs(fund_out[0][1]):.1f}亿。\n"

    except Exception as e:
        logging.warning(f"构建摘要失败: {e}")
        return None

    weekly = data.get('weekly', {})
    weekly_summary = ""
    if weekly.get('trend_direction') and weekly.get('trend_direction') != "未知":
        weekly_summary = f"【本周趋势】{weekly.get('trend_direction', '')}，周振幅约{weekly.get('trend_strength', 0):.1f}%\n"

    news_summary = ""
    if data.get("news"):
        news_summary = f"\n【今日要闻】{'; '.join(data['news'][:3])}"

    prompt = f"""
你是一个A股复盘分析师。结合今日数据和本周趋势，生成明日展望。

【今日数据】{daily_summary}
【本周趋势】{weekly_summary}
{news_summary}

要求：
1. 基于真实数据做判断，不虚构数据
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
    """
    AI不可用时的降级模板（仅使用真实数据，无静态占位）
    如果数据不足，返回简短提示
    """
    sh = data.get('indices', {}).get('上证指数', {})
    cy = data.get('indices', {}).get('创业板指', {})
    sh_pct = sh.get('涨跌幅')
    cy_pct = cy.get('涨跌幅')

    weekly = data.get('weekly', {})
    direction = weekly.get('trend_direction')

    # 构建核心判断
    core_parts = []
    if sh_pct is not None:
        core_parts.append(f"上证{sh_pct:+.2f}%")
    if cy_pct is not None:
        core_parts.append(f"创业板{cy_pct:+.2f}%")

    if core_parts:
        core = f"今日{'，'.join(core_parts)}。"
    else:
        core = "今日指数数据暂不可用。"

    # 添加周趋势
    if direction and direction != "未知":
        core += f" 本周趋势{direction}。"

    # 构建配置建议
    config = ""

    # 使用真实板块数据
    sector_top = data.get('sector_top5', [])
    if sector_top:
        top_names = [s[0] for s in sector_top[:2] if s and s[0]]
        if top_names:
            config = f"关注{'、'.join(top_names)}持续性和量能变化。"

    # 如果板块数据为空，给出通用建议
    if not config:
        # 基于涨跌幅给出建议
        if sh_pct is not None and cy_pct is not None:
            avg_pct = (sh_pct + cy_pct) / 2
            if avg_pct > 1:
                config = "进攻端关注科技成长方向；防守端配置高股息板块。"
            elif avg_pct < -1:
                config = "进攻端谨慎；防守端关注高股息及防御性板块。"
            else:
                config = "进攻端关注结构性机会；防守端均衡配置。"
        else:
            config = "建议均衡配置，关注量能变化。"

    # 确保非空
    if not core:
        core = "市场数据暂不完整，请参考具体数据自行判断。"
    if not config:
        config = "建议关注量能变化及市场情绪。"

    return {
        'core': core,
        'config': config
    }