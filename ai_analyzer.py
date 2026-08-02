import os
import requests
import logging

def call_ai_analysis(data):
    """调用ModelScope API生成情绪总结和明日展望"""
    api_key = os.getenv("MODELSCOPE_SDK_TOKEN")
    model = os.getenv("MODELSCOPE_MODEL", "Qwen/Qwen2.5-72B-Instruct")

    if not api_key:
        logging.warning("⚠️ 未配置 MODELSCOPE_SDK_TOKEN，跳过AI分析")
        return None

    # 构建数据摘要
    summary = f"""
【指数表现】上证{data['indices']['上证指数']['涨跌幅']:.2f}%，创业板{data['indices']['创业板指']['涨跌幅']:.2f}%，科创50{data['indices']['科创50']['涨跌幅']:.2f}%。
【涨跌分布】上涨{data['market']['up']}家，下跌{data['market']['down']}家，涨停{data['market']['limit_up']}家。
【领涨板块】{', '.join([f'{s[0]}{s[1]:+.2f}%' for s in data['sector_top5'][:3]])}。
【领跌板块】{', '.join([f'{s[0]}{s[1]:+.2f}%' for s in data['sector_bottom5'][:3]])}。
【资金流向】电子净流入{data['fund_in'][0][1]:.1f}亿，银行净流出{abs(data['fund_out'][0][1]):.1f}亿。
"""
    if data.get("news"):
        summary += f"\n【今日要闻】{'; '.join(data['news'][:3])}"

    prompt = f"""
你是一个A股复盘分析师。根据今日数据，生成明日展望，要求：
1. 100字以内，分两段：核心判断 + 配置建议
2. 只做事实归纳，不推荐个股，不预测具体点位
3. 语言冷静客观，不要过度渲染情绪

数据如下：
{summary}

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
    """AI不可用时的降级模板"""
    if data['indices']['上证指数']['涨跌幅'] > 1:
        trend = "市场偏强势，但需警惕冲高回落"
    elif data['indices']['上证指数']['涨跌幅'] < -1:
        trend = "市场承压，关注权重股能否企稳"
    else:
        trend = "市场震荡磨底，结构分化延续"
    top_sector = data['sector_top5'][0][0] if data['sector_top5'] else "科技"
    return {
        'core': f"今日{trend}。",
        'config': f"关注{top_sector}持续性和量能变化；防御配置高股息板块。"
    }