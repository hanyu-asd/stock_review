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
    # ...（保持不变，与之前相同）...
    return []

# ---------- 周趋势 ----------
def fetch_weekly_summary(last_date_str):
    """从 easy-tdx 或 baostock 获取周趋势"""
    try:
        df = manager.fetch_with_fallback("index_daily", symbol="sh000001")
        if df is None or df.empty:
            df = manager.fetch_with_fallback("index_daily", symbol="sh.000001")
        if df is not None and not df.empty:
            # 适配列名（easy-tdx 使用 datetime，akshare 使用 date）
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
                        # 适配列名
                        if 'datetime' in df.columns:
                            date_col = 'datetime'
                        else:
                            date_col = 'date'
                        df[date_col] = pd.to_datetime(df[date_col])
                        df = df.sort_values(date_col)
                        last_two = df.tail(2)
                        if len(last_two) >= 2:
                            current = float(last_two.iloc[-1]["close"])
                            previous = float(last_two.iloc[-2]["close"])
                            pct = calculate_change_pct(current, previous)
                        else:
                            current = float(last_two.iloc[-1]["close"])
                            pct = None
                        data["indices"][name] = {
                            "最新价": round(current, 2),
                            "涨跌幅": pct,
                            "振幅": None,
                            "成交额": round(float(last_two.iloc[-1].get("amount", 0)) / 1e8, 2)
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
            logging.error("❌ 所有指数数据源均失败")

    # ===== 2. 消息面 =====
    news = fetch_market_news_with_fallback()
    data["news"] = news if news else []

    # ===== 3. 涨跌数据（市场情绪）：baostock 全量查询 =====
    market_data = None
    # 先尝试从缓存加载
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

    # 填充成交额
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
        # 使用 easy-tdx get_board_ranking
        ranking = manager.fetch_with_fallback("board_ranking")
        if ranking is not None and not ranking.empty:
            # 按主力净流入排序
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
        # 尝试 akshare 备用
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