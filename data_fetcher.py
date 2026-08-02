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

# ---------- 缓存 ----------
CACHE_FILE = "./data_cache.json"
CACHE_EXPIRE_HOURS = 24

def load_cache():
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
    try:
        cache = {
            '_timestamp': datetime.now().isoformat(),
            'data': data
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except:
        pass

# ---------- 交易日 ----------
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

# ---------- 消息面 ----------
def fetch_market_news_with_fallback():
    """7层备用数据源"""
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

    logging.warning("所有新闻源均失败")
    return []

# ---------- 周趋势 ----------
def fetch_weekly_summary(last_date_str):
    try:
        df = manager.fetch_with_fallback("index_daily", symbol="sh000001")
        if df is None or df.empty:
            df = manager.fetch_with_fallback("index_daily", symbol="sh.000001")
        if df is not None and not df.empty:
            if 'datetime' in df.columns:
                date_col = 'datetime'
            else:
                date_col = 'date'
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col)
            last_date = pd.Timestamp(last_date_str)
            df_week = df[df[date_col] <= last_date].tail(5)
            if len(df_week) >= 2:
                values = df_week['close'].values
                vol = df_week['vol'].values if 'vol' in df_week.columns else []
                trend_dir = "上升" if values[-1] > values[0] else "下降"
                trend_strength = abs((values[-1] - values[0]) / values[0] * 100)
                return {
                    "dates": [d.strftime('%Y-%m-%d') for d in df_week[date_col]],
                    "trend_direction": trend_dir,
                    "trend_strength": trend_strength,
                    "vol_trend": vol.tolist() if len(vol) > 0 else [],
                    "index_trend": {d.strftime('%Y-%m-%d'): v for d, v in zip(df_week[date_col], values)}
                }
    except Exception as e:
        logging.warning(f"周趋势获取失败: {e}")
    return {"trend_direction": "未知", "trend_strength": None, "dates": [], "vol_trend": [], "index_trend": {}}

# ---------- 计算涨跌幅 ----------
def calculate_change_pct(current, previous):
    if previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 2)

# ---------- baostock 全量查询市场情绪 ----------
def fetch_market_stats_from_baostock(date_str):
    import baostock as bs
    import time

    logging.info(f"📊 开始从 Baostock 获取 {date_str} 全市场涨跌数据...")

    lg = bs.login()
    if lg.error_code != '0':
        logging.error(f"Baostock 登录失败: {lg.error_msg}")
        return None

    try:
        stock_list = bs.query_all_stock()
        if stock_list.error_code != '0':
            logging.error(f"获取股票列表失败: {stock_list.error_msg}")
            return None

        all_codes = []
        while (stock_list.error_code == '0') and stock_list.next():
            row = stock_list.get_row_data()
            code = row[0]
            if (code.startswith('sh') or code.startswith('sz')) and not code.endswith('B'):
                all_codes.append(code)

        logging.info(f"📈 共 {len(all_codes)} 只 A 股，开始查询...")

        up = down = flat = limit_up = limit_down = 0
        batch_size = 100
        total = len(all_codes)

        for i in range(0, total, batch_size):
            batch = all_codes[i:i+batch_size]
            for code in batch:
                try:
                    rs = bs.query_history_k_data_plus(
                        code,
                        "date,close,preclose",
                        start_date=date_str,
                        end_date=date_str,
                        frequency="d",
                        adjustflag="2"
                    )
                    if rs.error_code != '0':
                        continue
                    data_list = []
                    while (rs.error_code == '0') and rs.next():
                        data_list.append(rs.get_row_data())
                    if not data_list:
                        continue
                    row = data_list[0]
                    close = float(row[1]) if row[1] else 0
                    preclose = float(row[2]) if row[2] and row[2] != '0' else close
                    if close == 0:
                        continue
                    if close == preclose:
                        flat += 1
                    elif close > preclose:
                        up += 1
                        if preclose > 0 and (close - preclose) / preclose >= 0.095:
                            limit_up += 1
                    else:
                        down += 1
                        if preclose > 0 and (preclose - close) / preclose >= 0.095:
                            limit_down += 1
                except:
                    continue
            time.sleep(0.1)
            logging.info(f"  已处理 {min(i+batch_size, total)}/{total} 只")

        bs.logout()
        logging.info(f"✅ Baostock 汇总: 上涨{up}，下跌{down}，平盘{flat}，涨停{limit_up}，跌停{limit_down}")
        return {"up": up, "down": down, "flat": flat, "limit_up": limit_up, "limit_down": limit_down}
    except Exception as e:
        logging.error(f"Baostock 查询失败: {e}")
        bs.logout()
        return None


# ---------- 获取指数数据（支持 easy-tdx 优先，35个股民关注指数） ----------
def fetch_index_data_with_easy_tdx(index_codes, date_str):
    """
    使用 easy-tdx 获取指数K线数据（包含成交额 amount）
    支持上交所(SH)、深交所(SZ)，北交所(BJ)自动跳过走降级
    """
    result = {}
    from easy_tdx import MacClient, Market

    try:
        with MacClient.from_best_host() as client:
            for name, info in index_codes.items():
                # 北交所指数 easy-tdx 不支持，跳过走降级
                if info["market"] == "BJ":
                    logging.info(f"⏭️ 跳过 {name}({info['code']}) easy-tdx 不支持北交所")
                    continue
                try:
                    code = info["code"]
                    market = Market.SH if info["market"] == "SH" else Market.SZ
                    df = client.get_stock_kline(market, code, count=2)
                    if df is not None and not df.empty:
                        df = df.sort_values('datetime')
                        last_two = df.tail(2)
                        if len(last_two) >= 2:
                            current = float(last_two.iloc[-1]["close"])
                            previous = float(last_two.iloc[-2]["close"])
                            pct = calculate_change_pct(current, previous)
                            amount = float(last_two.iloc[-1].get("amount", 0))
                            result[name] = {
                                "最新价": round(current, 2),
                                "涨跌幅": pct,
                                "振幅": None,
                                "成交额": round(amount / 1e8, 2) if amount > 0 else None
                            }
                        else:
                            current = float(last_two.iloc[-1]["close"])
                            amount = float(last_two.iloc[-1].get("amount", 0))
                            result[name] = {
                                "最新价": round(current, 2),
                                "涨跌幅": None,
                                "振幅": None,
                                "成交额": round(amount / 1e8, 2) if amount > 0 else None
                            }
                    else:
                        logging.warning(f"easy-tdx 获取 {name}({code}) 失败")
                except Exception as e:
                    logging.warning(f"easy-tdx 获取 {name} 异常: {e}")
    except Exception as e:
        logging.error(f"easy-tdx 连接失败: {e}")

    return result


# ---------- 主数据获取 ----------
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

    # ===== 1. 指数数据（35个股民关注指数） =====
    index_codes = {
        # ===== 上证系列（宽基） =====
        "上证指数": {"code": "000001", "market": "SH"},
        "上证A指": {"code": "000002", "market": "SH"},
        "上证B指": {"code": "000003", "market": "SH"},
        "上证180": {"code": "000010", "market": "SH"},
        "上证50": {"code": "000016", "market": "SH"},
        "上证380": {"code": "000009", "market": "SH"},
        # ===== 中证系列（宽基） =====
        "沪深300": {"code": "000300", "market": "SH"},
        "中证500": {"code": "000905", "market": "SH"},
        "中证1000": {"code": "000852", "market": "SH"},
        "中证2000": {"code": "932000", "market": "SH"},
        "中证A500": {"code": "000510", "market": "SH"},
        # ===== 科创/创业板 =====
        "科创50": {"code": "000688", "market": "SH"},
        "科创综指": {"code": "000680", "market": "SH"},
        "创业板指": {"code": "399006", "market": "SZ"},
        "创业板综": {"code": "399102", "market": "SZ"},
        # ===== 深证系列 =====
        "深证成指": {"code": "399001", "market": "SZ"},
        "深证综指": {"code": "399106", "market": "SZ"},
        "深证A指": {"code": "399107", "market": "SZ"},
        "深证B指": {"code": "399108", "market": "SZ"},
        "中小板指": {"code": "399005", "market": "SZ"},
        "深证100": {"code": "399330", "market": "SZ"},
        # ===== 北交所 =====
        "北证50": {"code": "899050", "market": "BJ"},
        # ===== 策略/红利 =====
        "红利指数": {"code": "000015", "market": "SH"},
        "上证央企": {"code": "000042", "market": "SH"},
        "上证民企": {"code": "000049", "market": "SH"},
        "上证成长": {"code": "000028", "market": "SH"},
        # ===== 行业主题（股民关注） =====
        "国证芯片": {"code": "980017", "market": "SZ"},
        "中证军工": {"code": "399967", "market": "SZ"},
        "中证消费": {"code": "399932", "market": "SZ"},
        "中证医药": {"code": "399933", "market": "SZ"},
        "中证新能源": {"code": "399808", "market": "SZ"},
        "中证白酒": {"code": "399997", "market": "SZ"},
        "中证银行": {"code": "399986", "market": "SZ"},
        "中证证券": {"code": "399975", "market": "SZ"},
        "中证保险": {"code": "399974", "market": "SZ"},
        "中证人工智能": {"code": "399971", "market": "SZ"},
    }

    # 方式A：easy-tdx 优先
    indices_data = fetch_index_data_with_easy_tdx(index_codes, data_date_str)
    if indices_data:
        data["indices"] = indices_data
        logging.info(f"✅ easy-tdx 指数数据成功，共 {len(data['indices'])} 条")
    else:
        logging.warning("easy-tdx 指数获取失败，尝试 akshare...")

    # 方式B：akshare 实时接口（补充 easy-tdx 未获取到的指数）
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
                if '成交额' in col:
                    cols['成交额'] = col
            if code_col is None:
                code_col = '代码'
            for k in ['最新价', '涨跌幅', '成交额']:
                if k not in cols:
                    cols[k] = k

            akshare_codes = {name: info["code"] for name, info in index_codes.items()}
            for name, code in akshare_codes.items():
                # 如果 easy-tdx 已有数据，跳过
                if name in data["indices"]:
                    continue
                row = spot[spot[code_col] == code]
                if not row.empty:
                    r = row.iloc[0]
                    data["indices"][name] = {
                        "最新价": round(float(r.get(cols['最新价'], 0)), 2),
                        "涨跌幅": round(float(r.get(cols['涨跌幅'], 0)), 2),
                        "振幅": None,
                        "成交额": round(float(r.get(cols['成交额'], 0)) / 1e8, 2)
                    }
            if data["indices"]:
                logging.info(f"✅ akshare 指数实时数据补充成功，共 {len(data['indices'])} 条")
    except Exception as e:
        logging.warning(f"akshare 实时指数获取失败: {e}")

    # 方式C：akshare 历史日线（补充仍未获取到的指数）
    if len(data["indices"]) < len(index_codes):
        try:
            akshare_symbols = {}
            for name, info in index_codes.items():
                if name in data["indices"]:
                    continue
                if info["market"] == "BJ":
                    akshare_symbols[name] = f"bj{info['code']}"
                elif info["market"] == "SH":
                    akshare_symbols[name] = f"sh{info['code']}"
                else:
                    akshare_symbols[name] = f"sz{info['code']}"

            for name, symbol in akshare_symbols.items():
                try:
                    df = manager.fetch_with_fallback("index_daily", symbol=symbol)
                    if df is not None and not df.empty:
                        if 'date' in df.columns:
                            df['date'] = pd.to_datetime(df['date'])
                            df = df.sort_values('date')
                            last_two = df.tail(2)
                            if len(last_two) >= 2:
                                current = float(last_two.iloc[-1]["close"])
                                previous = float(last_two.iloc[-2]["close"])
                                pct = calculate_change_pct(current, previous)
                            else:
                                current = float(last_two.iloc[-1]["close"])
                                pct = None
                            amount = float(last_two.iloc[-1].get("amount", 0))
                            data["indices"][name] = {
                                "最新价": round(current, 2),
                                "涨跌幅": pct,
                                "振幅": None,
                                "成交额": round(amount / 1e8, 2) if amount > 0 else None
                            }
                except Exception as e2:
                    logging.warning(f"获取 {name} 历史日线失败: {e2}")
            if data["indices"]:
                logging.info(f"✅ akshare 历史日线补充成功，共 {len(data['indices'])} 条")
        except Exception as e2:
            logging.error(f"历史日线降级失败: {e2}")

    # 如果指数数据仍然为空，从缓存加载
    if not data["indices"]:
        cache = load_cache()
        if cache.get('indices'):
            data["indices"] = cache['indices']
            logging.info(f"✅ 从缓存加载指数数据，共 {len(data['indices'])} 条")
        else:
            logging.error("❌ 所有指数数据源均失败，指数数据不可用")

    # ===== 2. 消息面 =====
    news = fetch_market_news_with_fallback()
    data["news"] = news if news else []

    # ===== 3. 涨跌数据（市场情绪）：baostock 全量查询 =====
    market_data = None
    cache = load_cache()
    if cache.get('market'):
        market_data = cache['market']
        logging.info("✅ 从缓存加载涨跌数据")
    else:
        logging.info("⚠️ 缓存无涨跌数据，从 Baostock 获取真实数据...")
        baostock_data = fetch_market_stats_from_baostock(data_date_str)
        if baostock_data:
            market_data = baostock_data
            logging.info("✅ Baostock 真实数据获取成功")
        else:
            market_data = {"up": None, "down": None, "flat": None, "limit_up": None, "limit_down": None}
            logging.error("❌ 所有真实数据源均失败，涨跌数据不可用")

    # 填充成交额（从指数数据累加）
    total_vol = 0
    for idx in data["indices"].values():
        vol = idx.get("成交额")
        if vol is not None and vol > 0:
            total_vol += vol
    if market_data:
        market_data["total_vol"] = round(total_vol, 2) if total_vol > 0 else None
        data["market"] = market_data

    # ===== 4. 行业板块 =====
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

    # ===== 5. 资金流向 =====
    fund_success = False
    try:
        ranking = manager.fetch_with_fallback("board_ranking")
        if ranking is not None and not ranking.empty:
            sorted_df = ranking.sort_values(by='main_net_amount', ascending=False)
            top_in = sorted_df.head(3)[['name', 'main_net_amount']].values.tolist()
            top_out = sorted_df.tail(3)[['name', 'main_net_amount']].values.tolist()
            data["fund_in"] = [[str(name), round(float(amount) / 1e8, 2)] for name, amount in top_in]
            data["fund_out"] = [[str(name), round(float(amount) / 1e8, 2)] for name, amount in top_out]
            fund_success = True
            logging.info("✅ 资金流向数据获取成功 (easy-tdx board_ranking)")
    except Exception as e:
        logging.error(f"easy-tdx 资金流向失败: {e}")

    if not fund_success:
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
                logging.info("✅ 资金流向数据获取成功 (akshare 备用)")
        except Exception as e:
            logging.error(f"akshare 资金流向备用失败: {e}")

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

    # ===== 6. 保存缓存 =====
    cache_data = {}
    if data["indices"]:
        cache_data['indices'] = data["indices"]
    if data["market"] and any(v is not None for v in data["market"].values()):
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