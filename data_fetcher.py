import pandas as pd
import logging
import json
import os
import requests
import feedparser
import time
from datetime import datetime, timedelta
import akshare as ak
from data_sources import DataSourceManager

logging.basicConfig(level=logging.INFO)

manager = DataSourceManager()


def get_last_trading_day(target_date=None):
    if target_date is None:
        target_date = datetime.now()
    try:
        trade_days = ak.tool_trade_date_hist_sina()
        trade_days = pd.to_datetime(trade_days['trade_date'])
        available = trade_days[trade_days <= pd.Timestamp(target_date)]
        if not available.empty:
            last = available.max().strftime('%Y-%m-%d')
            logging.info(f"最近交易日: {last}")
            return last
    except Exception as e:
        logging.warning(f"获取交易日历失败: {e}")
    if target_date.weekday() >= 5:
        days_back = target_date.weekday() - 4
        last = (target_date - timedelta(days=days_back)).strftime('%Y-%m-%d')
        logging.info(f"使用降级最近交易日: {last}")
        return last
    return target_date.strftime('%Y-%m-%d')


# ========== 消息面催化：7层备用数据源 ==========

def fetch_market_news_with_fallback():
    """
    7层备用数据源，逐级降级
    第1层: levistock（SDK封装，最稳定）
    第2层: 新浪财经API
    第3层: RSSHub财联社
    第4层: 腾讯财经API
    第5层: 东方财富网
    第6层: 华尔街见闻RSS
    第7层: 基于当日指数数据动态生成
    """
    # 第1层：levistock
    try:
        import levistock as lk
        emotion = lk.market_emotion_cls()
        if emotion is not None:
            news_list = []
            if hasattr(emotion, 'head'):
                for _, row in emotion.head(5).iterrows():
                    title = row.get('title', '') or row.get('内容', '') or str(row)
                    if title and len(title) > 5:
                        news_list.append(title.strip())
            if news_list:
                filtered = [n for n in news_list if any(k in n for k in ['A股', '市场', '科技', '板块', '资金', '政策', '涨', '跌'])]
                if filtered:
                    logging.info(f"✅ levistock: {len(filtered[:3])}条")
                    return filtered[:3]
    except ImportError:
        logging.warning("levistock 未安装，跳过")
    except Exception as e:
        logging.warning(f"levistock 失败: {e}")

    # 第2层：新浪财经
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&num=10"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('result', {}).get('data', [])
            news = [item.get('title', '') for item in items[:8] if item.get('title', '') and len(item.get('title', '')) > 5]
            if news:
                filtered = [n for n in news if any(k in n for k in ['A股', '市场', '科技', '板块', '资金', '政策', '涨', '跌'])]
                if filtered:
                    logging.info(f"✅ 新浪财经: {len(filtered[:3])}条")
                    return filtered[:3]
    except Exception as e:
        logging.warning(f"新浪财经失败: {e}")

    # 第3层：RSSHub财联社
    try:
        feed = feedparser.parse("https://rsshub.app/cls/telegraph")
        if feed.entries:
            news = [entry.title for entry in feed.entries[:8] if entry.title and len(entry.title) > 5]
            if news:
                filtered = [n for n in news if any(k in n for k in ['A股', '市场', '科技', '板块', '资金', '政策', '涨', '跌'])]
                if filtered:
                    logging.info(f"✅ 财联社(RSS): {len(filtered[:3])}条")
                    return filtered[:3]
    except Exception as e:
        logging.warning(f"RSSHub财联社失败: {e}")

    # 第4层：腾讯财经
    try:
        news_url = "https://web.ifzq.gtimg.cn/appstock/news/news"
        resp = requests.get(news_url, timeout=8, params={"num": 10})
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('data', [])
            news = [item.get('title', '') or item.get('subject', '') for item in items[:8] if (item.get('title', '') or item.get('subject', '')) and len(item.get('title', '') or item.get('subject', '')) > 5]
            if news:
                filtered = [n for n in news if any(k in n for k in ['A股', '市场', '科技', '板块', '资金', '政策', '涨', '跌'])]
                if filtered:
                    logging.info(f"✅ 腾讯财经: {len(filtered[:3])}条")
                    return filtered[:3]
    except Exception as e:
        logging.warning(f"腾讯财经失败: {e}")

    # 第5层：东方财富
    try:
        df = ak.stock_news_em()
        if df is not None and not df.empty:
            news = [row.get('title', '') or row.get('标题', '') for _, row in df.head(8).iterrows() if (row.get('title', '') or row.get('标题', '')) and len(row.get('title', '') or row.get('标题', '')) > 5]
            if news:
                filtered = [n for n in news if any(k in n for k in ['A股', '市场', '科技', '板块', '资金', '政策', '涨', '跌'])]
                if filtered:
                    logging.info(f"✅ 东方财富: {len(filtered[:3])}条")
                    return filtered[:3]
    except Exception as e:
        logging.warning(f"东方财富失败: {e}")

    # 第6层：华尔街见闻
    try:
        feed = feedparser.parse("https://rsshub.app/wallstreetcn/live")
        if feed.entries:
            news = [entry.title for entry in feed.entries[:8] if entry.title and len(entry.title) > 5]
            if news:
                filtered = [n for n in news if any(k in n for k in ['A股', '市场', '科技', '板块', '资金', '政策', '涨', '跌', '中国'])]
                if filtered:
                    logging.info(f"✅ 华尔街见闻: {len(filtered[:3])}条")
                    return filtered[:3]
    except Exception as e:
        logging.warning(f"华尔街见闻失败: {e}")

    # 第7层：动态生成
    logging.warning("所有新闻源失败，将使用动态生成")
    return None


def generate_dynamic_news_from_indices(indices):
    """基于指数数据动态生成消息"""
    if not indices:
        return ["今日A股市场震荡整理，关注结构性机会", "市场量能变化是短期关键观察指标"]
    
    sh = indices.get('上证指数', {})
    cy = indices.get('创业板指', {})
    sh_pct = sh.get('涨跌幅', 0)
    cy_pct = cy.get('涨跌幅', 0)
    
    news = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    if sh_pct > 1.5 and cy_pct > 2:
        news.append(f"{today} A股放量上涨，创业板大涨{cy_pct:.2f}%，科技板块领涨市场")
    elif sh_pct > 1:
        news.append(f"{today} A股震荡上行，上证指数收涨{sh_pct:.2f}%，市场情绪回暖")
    elif sh_pct < -1.5 and cy_pct < -2:
        news.append(f"{today} A股承压调整，创业板下跌{abs(cy_pct):.2f}%，防御板块相对抗跌")
    elif sh_pct < -1:
        news.append(f"{today} A股震荡整理，上证指数下跌{abs(sh_pct):.2f}%，关注权重股企稳信号")
    else:
        news.append(f"{today} A股窄幅震荡，市场等待方向选择")
    
    news.append("市场聚焦科技主线与政策催化方向")
    return news[:3]


# ========== 周趋势 ==========

def fetch_weekly_summary(last_date_str):
    try:
        df = manager.fetch_with_fallback("index_daily", symbol="sh000001")
        if df is None or df.empty:
            df = manager.fetch_with_fallback("index_daily", symbol="sh.000001")
        if df is not None and not df.empty:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                last_date = pd.Timestamp(last_date_str)
                df_week = df[df['date'] <= last_date].tail(5)
                if len(df_week) >= 2:
                    values = df_week['close'].values
                    vol = df_week['volume'].values if 'volume' in df_week.columns else []
                    trend_dir = "上升" if values[-1] > values[0] else "下降"
                    trend_strength = abs((values[-1] - values[0]) / values[0] * 100)
                    return {
                        "dates": [d.strftime('%Y-%m-%d') for d in df_week['date']],
                        "trend_direction": trend_dir,
                        "trend_strength": trend_strength,
                        "vol_trend": vol.tolist() if len(vol) > 0 else [],
                        "index_trend": {d.strftime('%Y-%m-%d'): v for d, v in zip(df_week['date'], values)}
                    }
    except Exception as e:
        logging.warning(f"周趋势获取失败: {e}")

    return {"trend_direction": "震荡", "trend_strength": 0, "dates": [], "vol_trend": [], "index_trend": {}}


# ========== 动态获取指数默认值（基于历史日线） ==========

def get_dynamic_fallback_indices():
    """
    从历史日线动态获取最近一个交易日的指数数据，作为最终降级
    """
    fallback = {}
    index_codes = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
        "科创50": "sh000688",
        "上证50": "sh000016"
    }
    for name, symbol in index_codes.items():
        try:
            df = manager.fetch_with_fallback("index_daily", symbol=symbol)
            if df is not None and not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                last = df.iloc[-1]
                fallback[name] = {
                    "最新价": round(float(last["close"]), 2),
                    "涨跌幅": 0,
                    "振幅": 0,
                    "成交额": round(float(last.get("amount", 0)) / 1e8, 2)
                }
            else:
                # 如果单个获取失败，使用简单推断
                if name == "上证指数":
                    fallback[name] = {"最新价": 3800, "涨跌幅": 0, "振幅": 0, "成交额": 10000}
                elif name == "深证成指":
                    fallback[name] = {"最新价": 13500, "涨跌幅": 0, "振幅": 0, "成交额": 12000}
                elif name == "创业板指":
                    fallback[name] = {"最新价": 3300, "涨跌幅": 0, "振幅": 0, "成交额": 6000}
                elif name == "科创50":
                    fallback[name] = {"最新价": 1600, "涨跌幅": 0, "振幅": 0, "成交额": 1500}
                elif name == "上证50":
                    fallback[name] = {"最新价": 2900, "涨跌幅": 0, "振幅": 0, "成交额": 2000}
        except Exception as e:
            logging.warning(f"获取 {name} 历史日线失败: {e}")
            # 使用简单推断值
            if name == "上证指数":
                fallback[name] = {"最新价": 3800, "涨跌幅": 0, "振幅": 0, "成交额": 10000}
            elif name == "深证成指":
                fallback[name] = {"最新价": 13500, "涨跌幅": 0, "振幅": 0, "成交额": 12000}
            elif name == "创业板指":
                fallback[name] = {"最新价": 3300, "涨跌幅": 0, "振幅": 0, "成交额": 6000}
            elif name == "科创50":
                fallback[name] = {"最新价": 1600, "涨跌幅": 0, "振幅": 0, "成交额": 1500}
            elif name == "上证50":
                fallback[name] = {"最新价": 2900, "涨跌幅": 0, "振幅": 0, "成交额": 2000}
    return fallback


# ========== 动态估算（仅作为极端降级） ==========

def calculate_market_stats_from_indices(indices):
    """
    根据指数数据估算涨跌家数（仅在准确数据源全部失败时使用）
    """
    if not indices:
        logging.warning("无指数数据，使用默认涨跌估算")
        return {"up": 2500, "down": 2300, "flat": 200, "limit_up": 50, "limit_down": 10, "total_vol": 15000}
    
    sh = indices.get('上证指数', {})
    cy = indices.get('创业板指', {})
    sh_pct = sh.get('涨跌幅', 0)
    cy_pct = cy.get('涨跌幅', 0)
    
    avg_pct = (sh_pct + cy_pct) / 2
    if avg_pct > 1.5:
        up_ratio = 0.78
    elif avg_pct > 0.5:
        up_ratio = 0.62
    elif avg_pct > -0.5:
        up_ratio = 0.48
    elif avg_pct > -1.5:
        up_ratio = 0.32
    else:
        up_ratio = 0.18
    
    total = 5000
    up = int(total * up_ratio)
    down = int(total * (1 - up_ratio - 0.02))
    flat = total - up - down
    limit_up = int(up * 0.025) if up > 0 else 30
    limit_down = int(down * 0.015) if down > 0 else 10
    
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "total_vol": 0
    }


def generate_estimated_sectors(indices):
    """基于指数表现动态生成板块列表（仅在无板块数据时使用）"""
    sh = indices.get('上证指数', {})
    cy = indices.get('创业板指', {})
    sh_pct = sh.get('涨跌幅', 0)
    cy_pct = cy.get('涨跌幅', 0)
    avg_pct = (sh_pct + cy_pct) / 2
    
    if avg_pct > 0.8:
        top = [
            ["科技", round(avg_pct + 0.5, 2)],
            ["电子", round(avg_pct + 0.3, 2)],
            ["通信", round(avg_pct + 0.1, 2)],
            ["传媒", round(avg_pct - 0.1, 2)],
            ["汽车", round(avg_pct - 0.2, 2)]
        ]
        bottom = [
            ["银行", round(-0.2, 2)],
            ["煤炭", round(-0.1, 2)],
            ["石油", round(0.0, 2)]
        ]
    elif avg_pct < -0.8:
        top = [
            ["银行", round(0.2, 2)],
            ["食品饮料", round(0.1, 2)],
            ["非银金融", round(0.0, 2)]
        ]
        bottom = [
            ["科技", round(avg_pct - 0.5, 2)],
            ["电子", round(avg_pct - 0.3, 2)],
            ["通信", round(avg_pct - 0.1, 2)]
        ]
    else:
        top = [
            ["科技", round(avg_pct + 0.3, 2)],
            ["电子", round(avg_pct + 0.1, 2)],
            ["通信", round(avg_pct, 2)]
        ]
        bottom = [
            ["银行", round(-0.1, 2)],
            ["煤炭", round(0.0, 2)],
            ["石油", round(-0.1, 2)]
        ]
    
    while len(top) < 5:
        top.append([f"其他{len(top)+1}", round(avg_pct - 0.1*len(top), 2)])
    while len(bottom) < 5:
        bottom.append([f"其他{len(bottom)+1}", round(-avg_pct + 0.1*len(bottom), 2)])
    
    return top[:5], bottom[:5]


def calculate_fund_flow_from_sectors(sector_top5, sector_bottom5, indices):
    """根据板块数据估算资金流向（仅在无准确数据时使用）"""
    fund_in = []
    fund_out = []
    
    if sector_top5 and sector_bottom5:
        for name, pct in sector_top5[:3]:
            if pct > 0:
                inflow = round(abs(pct) * 50, 1)
                fund_in.append([name, inflow])
        for name, pct in sector_bottom5[:3]:
            if pct < 0:
                outflow = round(abs(pct) * 35, 1)
                fund_out.append([name, -outflow])
    
    if not fund_in and not fund_out:
        sh = indices.get('上证指数', {})
        cy = indices.get('创业板指', {})
        sh_pct = sh.get('涨跌幅', 0)
        cy_pct = cy.get('涨跌幅', 0)
        avg_pct = (sh_pct + cy_pct) / 2
        
        if avg_pct > 0.5:
            fund_in = [["科技", round(avg_pct * 30, 1)], ["电子", round(avg_pct * 20, 1)], ["通信", round(avg_pct * 15, 1)]]
            fund_out = [["银行", -round(abs(avg_pct) * 5, 1)], ["食品饮料", -round(abs(avg_pct) * 3, 1)]]
        elif avg_pct < -0.5:
            fund_in = [["银行", round(abs(avg_pct) * 5, 1)], ["食品饮料", round(abs(avg_pct) * 3, 1)]]
            fund_out = [["科技", -round(abs(avg_pct) * 25, 1)], ["电子", -round(abs(avg_pct) * 18, 1)]]
        else:
            fund_in = [["科技", 15.0], ["电子", 10.0], ["通信", 8.0]]
            fund_out = [["银行", -5.0], ["食品饮料", -3.0], ["非银金融", -2.0]]
    
    while len(fund_in) < 3:
        fund_in.append([f"板块{len(fund_in)+1}", 5.0])
    while len(fund_out) < 3:
        fund_out.append([f"板块{len(fund_out)+1}", -2.0])
    
    return fund_in[:3], fund_out[:3]


# ========== 主数据获取函数 ==========

def fetch_market_data():
    data_date_str = get_last_trading_day()
    logging.info(f"📅 使用数据日期: {data_date_str}")

    data = {
        "date": data_date_str,
        "indices": {},
        "market": {},
        "sector_top5": [],
        "sector_bottom5": [],
        "fund_in": [],
        "fund_out": [],
        "news": [],
        "weekly": fetch_weekly_summary(data_date_str)
    }

    # ===== 1. 指数数据 =====
    try:
        spot = manager.fetch_with_fallback("index_spot")
        if spot is not None and not spot.empty:
            code_col = None
            cols = {}
            for col in spot.columns:
                if '代码' in col or 'code' in col.lower():
                    code_col = col
                if '最新价' in col or 'close' in col.lower():
                    cols['最新价'] = col
                if '涨跌幅' in col:
                    cols['涨跌幅'] = col
                if '振幅' in col:
                    cols['振幅'] = col
                if '成交额' in col:
                    cols['成交额'] = col
            if code_col is None:
                code_col = '代码'
            for k in ['最新价', '涨跌幅', '振幅', '成交额']:
                if k not in cols:
                    cols[k] = k

            index_map = {
                "上证指数": "000001",
                "深证成指": "399001",
                "创业板指": "399006",
                "科创50": "000688",
                "上证50": "000016"
            }
            for name, code in index_map.items():
                row = spot[spot[code_col] == code]
                if not row.empty:
                    r = row.iloc[0]
                    data["indices"][name] = {
                        "最新价": round(float(r.get(cols['最新价'], 0)), 2),
                        "涨跌幅": round(float(r.get(cols['涨跌幅'], 0)), 2),
                        "振幅": round(float(r.get(cols['振幅'], 0)), 2),
                        "成交额": round(float(r.get(cols['成交额'], 0)) / 1e8, 2)
                    }
            if data["indices"]:
                logging.info(f"✅ 指数实时数据成功，共 {len(data['indices'])} 条")
            else:
                raise Exception("实时数据未获取到任何指数")
        else:
            raise Exception("实时数据返回空")
    except Exception as e:
        logging.warning(f"实时指数获取失败: {e}，尝试历史日线")
        try:
            index_codes = {
                "上证指数": "sh000001",
                "深证成指": "sz399001",
                "创业板指": "sz399006",
                "科创50": "sh000688",
                "上证50": "sh000016"
            }
            for name, symbol in index_codes.items():
                try:
                    df = manager.fetch_with_fallback("index_daily", symbol=symbol)
                    if df is not None and not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date')
                        last = df.iloc[-1]
                        data["indices"][name] = {
                            "最新价": round(float(last["close"]), 2),
                            "涨跌幅": 0,
                            "振幅": 0,
                            "成交额": round(float(last.get("amount", 0)) / 1e8, 2)
                        }
                    else:
                        raise Exception(f"{name} 历史日线为空")
                except Exception as e2:
                    logging.warning(f"获取 {name} 历史日线失败: {e2}")
            if data["indices"]:
                logging.info(f"✅ 从历史日线获取指数数据，共 {len(data['indices'])} 条")
            else:
                raise Exception("所有历史日线获取失败")
        except Exception as e2:
            logging.error(f"历史日线降级完全失败: {e2}")
            data["indices"] = get_dynamic_fallback_indices()
            logging.warning("⚠️ 使用动态获取的默认指数数据")

    # ===== 2. 获取消息面 =====
    news = fetch_market_news_with_fallback()
    if news:
        data["news"] = news
    else:
        data["news"] = generate_dynamic_news_from_indices(data["indices"])

    # ===== 3. 涨跌数据（优先使用准确的聚合接口） =====
    try:
        activity = manager.fetch_with_fallback("market_activity")
        if activity is not None and not activity.empty:
            row = activity.iloc[-1]
            # 动态查找列名
            up_col = next((c for c in activity.columns if '上涨' in c or '涨家数' in c), None)
            down_col = next((c for c in activity.columns if '下跌' in c or '跌家数' in c), None)
            flat_col = next((c for c in activity.columns if '平盘' in c or '平家数' in c), None)
            limit_up_col = next((c for c in activity.columns if '涨停' in c), None)
            limit_down_col = next((c for c in activity.columns if '跌停' in c), None)
            
            if up_col and down_col:
                data["market"]["up"] = int(row[up_col])
                data["market"]["down"] = int(row[down_col])
                data["market"]["flat"] = int(row[flat_col]) if flat_col else 0
                data["market"]["limit_up"] = int(row[limit_up_col]) if limit_up_col else 0
                data["market"]["limit_down"] = int(row[limit_down_col]) if limit_down_col else 0
                # 成交额从指数获取
                total_vol = 0
                for idx in data["indices"].values():
                    total_vol += idx.get("成交额", 0)
                data["market"]["total_vol"] = round(total_vol, 2)
                logging.info(f"✅ 市场情绪数据获取成功: 上涨{data['market']['up']}家，下跌{data['market']['down']}家")
            else:
                raise Exception("列名未找到")
        else:
            raise Exception("market_activity 返回空")
    except Exception as e:
        logging.warning(f"市场情绪聚合数据获取失败: {e}，尝试全列表统计")
        try:
            stocks = manager.fetch_with_fallback("stock_spot")
            if stocks is not None and not stocks.empty:
                data["market"]["up"] = int((stocks["涨跌幅"] > 0).sum())
                data["market"]["down"] = int((stocks["涨跌幅"] < 0).sum())
                data["market"]["flat"] = int((stocks["涨跌幅"] == 0).sum())
                data["market"]["limit_up"] = int((stocks["涨跌幅"] >= 9.9).sum())
                data["market"]["limit_down"] = int((stocks["涨跌幅"] <= -9.9).sum())
                data["market"]["total_vol"] = round(float(stocks["成交额"].sum()) / 1e8, 2)
                logging.info("✅ 涨跌数据获取成功（全列表统计）")
            else:
                raise Exception("stock_spot 返回空")
        except Exception as e2:
            logging.error(f"所有涨跌数据源均失败: {e2}")
            data["market"] = calculate_market_stats_from_indices(data["indices"])
            logging.warning("⚠️ 使用估算涨跌数据（极端降级）")

    # ===== 4. 行业板块 =====
    try:
        sector = manager.fetch_with_fallback("sector")
        if sector is not None and not sector.empty:
            name_col = next((c for c in sector.columns if '名称' in c or '板块' in c), sector.columns[0])
            pct_col = next((c for c in sector.columns if '涨跌幅' in c), sector.columns[1])
            sector = sector.sort_values(by=pct_col, ascending=False)
            top5 = sector.head(5)[[name_col, pct_col]].values.tolist()
            bottom5 = sector.tail(5)[[name_col, pct_col]].values.tolist()
            data["sector_top5"] = [[str(n), round(float(p), 2)] for n, p in top5]
            data["sector_bottom5"] = [[str(n), round(float(p), 2)] for n, p in bottom5]
            logging.info("✅ 行业板块数据获取成功")
        else:
            top, bottom = generate_estimated_sectors(data["indices"])
            data["sector_top5"] = top
            data["sector_bottom5"] = bottom
            logging.warning("⚠️ 使用动态估算行业板块数据（极端降级）")
    except Exception as e:
        logging.error(f"行业板块异常: {e}")
        top, bottom = generate_estimated_sectors(data["indices"])
        data["sector_top5"] = top
        data["sector_bottom5"] = bottom

    # ===== 5. 资金流向 =====
    try:
        fund = manager.fetch_with_fallback("fund_flow")
        if fund is not None and not fund.empty:
            name_col = next((c for c in fund.columns if '名称' in c or '板块' in c), fund.columns[0])
            flow_col = next((c for c in fund.columns if '主力净流入' in c or '净流入' in c), fund.columns[1])
            fund_in = fund.head(3)[[name_col, flow_col]].values.tolist()
            fund_out = fund.tail(3)[[name_col, flow_col]].values.tolist()
            data["fund_in"] = [[str(n), round(float(v)/1e4, 2)] for n, v in fund_in]
            data["fund_out"] = [[str(n), round(float(v)/1e4, 2)] for n, v in fund_out]
            logging.info("✅ 资金流向数据获取成功")
        else:
            fund_in, fund_out = calculate_fund_flow_from_sectors(
                data["sector_top5"], data["sector_bottom5"], data["indices"]
            )
            data["fund_in"] = fund_in
            data["fund_out"] = fund_out
            logging.warning("⚠️ 使用估算资金流向数据（极端降级）")
    except Exception as e:
        logging.error(f"资金流向异常: {e}")
        fund_in, fund_out = calculate_fund_flow_from_sectors(
            data["sector_top5"], data["sector_bottom5"], data["indices"]
        )
        data["fund_in"] = fund_in
        data["fund_out"] = fund_out

    return data