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

# ---------- 全局缓存 ----------
CACHE_FILE = "./data_cache.json"
CACHE_EXPIRE_HOURS = 24


def load_cache():
    """加载缓存数据"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            cache_time = datetime.fromisoformat(cache.get('_timestamp', '2000-01-01'))
            if (datetime.now() - cache_time).total_seconds() < CACHE_EXPIRE_HOURS * 3600:
                return cache.get('data', {})
        except:
            pass
    return {}


def save_cache(data):
    """保存缓存数据"""
    try:
        cache = {
            '_timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except:
        pass


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
    """7层备用数据源，全部为真实新闻源，全部失败时返回空列表"""
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

    # 全部失败：返回空列表
    logging.warning("所有新闻源均失败，消息面将显示为「暂无可显示消息」")
    return []


# ========== 周趋势 ==========

def fetch_weekly_summary(last_date_str):
    """从真实历史数据获取周趋势"""
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

    return {"trend_direction": "未知", "trend_strength": None, "dates": [], "vol_trend": [], "index_trend": {}}


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
    indices_success = False
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
                indices_success = True
                logging.info(f"✅ 指数实时数据成功，共 {len(data['indices'])} 条")
    except Exception as e:
        logging.warning(f"实时指数获取失败: {e}")

    if not indices_success:
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
                            "涨跌幅": None,
                            "振幅": None,
                            "成交额": round(float(last.get("amount", 0)) / 1e8, 2)
                        }
                except Exception as e2:
                    logging.warning(f"获取 {name} 历史日线失败: {e2}")
            if data["indices"]:
                indices_success = True
                logging.info(f"✅ 从历史日线获取指数数据，共 {len(data['indices'])} 条")
        except Exception as e2:
            logging.error(f"历史日线降级失败: {e2}")

    if not indices_success:
        cache = load_cache()
        if cache.get('indices'):
            data["indices"] = cache['indices']
            logging.info(f"✅ 从缓存加载指数数据，共 {len(data['indices'])} 条")
        else:
            data["indices"] = {}
            logging.error("❌ 所有指数数据源均失败，指数数据不可用")

    # ===== 2. 涨跌数据 =====
    market_success = False
    try:
        activity = manager.fetch_with_fallback("market_activity")
        if activity is not None and not activity.empty:
            row = activity.iloc[-1]
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
                total_vol = 0
                for idx in data["indices"].values():
                    vol = idx.get("成交额")
                    if vol is not None:
                        total_vol += vol
                data["market"]["total_vol"] = round(total_vol, 2) if total_vol > 0 else None
                market_success = True
                logging.info(f"✅ 市场情绪数据获取成功: 上涨{data['market']['up']}家，下跌{data['market']['down']}家")
            else:
                logging.warning("市场情绪接口返回数据但列名未匹配")
    except Exception as e:
        logging.warning(f"市场情绪聚合数据获取失败: {e}")

    if not market_success:
        try:
            stocks = manager.fetch_with_fallback("stock_spot")
            if stocks is not None and not stocks.empty:
                data["market"]["up"] = int((stocks["涨跌幅"] > 0).sum())
                data["market"]["down"] = int((stocks["涨跌幅"] < 0).sum())
                data["market"]["flat"] = int((stocks["涨跌幅"] == 0).sum())
                data["market"]["limit_up"] = int((stocks["涨跌幅"] >= 9.9).sum())
                data["market"]["limit_down"] = int((stocks["涨跌幅"] <= -9.9).sum())
                data["market"]["total_vol"] = round(float(stocks["成交额"].sum()) / 1e8, 2)
                market_success = True
                logging.info("✅ 涨跌数据获取成功（全列表统计）")
        except Exception as e2:
            logging.error(f"全列表统计失败: {e2}")

    if not market_success:
        cache = load_cache()
        if cache.get('market'):
            data["market"] = cache['market']
            logging.info("✅ 从缓存加载涨跌数据")
        else:
            data["market"] = {}
            logging.error("❌ 所有涨跌数据源均失败，涨跌数据不可用")

    # ===== 3. 行业板块 =====
    sector_success = False
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
            sector_success = True
            logging.info("✅ 行业板块数据获取成功")
    except Exception as e:
        logging.error(f"行业板块异常: {e}")

    if not sector_success:
        cache = load_cache()
        if cache.get('sector_top5') and cache.get('sector_bottom5'):
            data["sector_top5"] = cache['sector_top5']
            data["sector_bottom5"] = cache['sector_bottom5']
            logging.info("✅ 从缓存加载行业板块数据")
        else:
            data["sector_top5"] = []
            data["sector_bottom5"] = []
            logging.error("❌ 行业板块数据不可用")

    # ===== 4. 资金流向 =====
    fund_success = False
    try:
        fund = manager.fetch_with_fallback("fund_flow")
        if fund is not None and not fund.empty:
            name_col = next((c for c in fund.columns if '名称' in c or '板块' in c), fund.columns[0])
            flow_col = next((c for c in fund.columns if '主力净流入' in c or '净流入' in c), fund.columns[1])
            fund_in = fund.head(3)[[name_col, flow_col]].values.tolist()
            fund_out = fund.tail(3)[[name_col, flow_col]].values.tolist()
            data["fund_in"] = [[str(n), round(float(v)/1e4, 2)] for n, v in fund_in]
            data["fund_out"] = [[str(n), round(float(v)/1e4, 2)] for n, v in fund_out]
            fund_success = True
            logging.info("✅ 资金流向数据获取成功")
    except Exception as e:
        logging.error(f"资金流向异常: {e}")

    if not fund_success:
        cache = load_cache()
        if cache.get('fund_in') and cache.get('fund_out'):
            data["fund_in"] = cache['fund_in']
            data["fund_out"] = cache['fund_out']
            logging.info("✅ 从缓存加载资金流向数据")
        else:
            data["fund_in"] = []
            data["fund_out"] = []
            logging.error("❌ 资金流向数据不可用")

    # ===== 5. 消息面 =====
    news = fetch_market_news_with_fallback()
    data["news"] = news if news else []

    # ===== 6. 保存缓存 =====
    cache_data = {}
    if data["indices"]:
        cache_data['indices'] = data["indices"]
    if data["market"]:
        cache_data['market'] = data["market"]
    if data["sector_top5"]:
        cache_data['sector_top5'] = data["sector_top5"]
        cache_data['sector_bottom5'] = data["sector_bottom5"]
    if data["fund_in"]:
        cache_data['fund_in'] = data["fund_in"]
        cache_data['fund_out'] = data["fund_out"]
    if cache_data:
        save_cache(cache_data)

    return data