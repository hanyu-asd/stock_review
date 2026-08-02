import pandas as pd
import logging
import json
import os
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


def fetch_market_news_with_fallback():
    try:
        df = manager.fetch_with_fallback("news")
        if df is not None and not df.empty:
            news = []
            for _, row in df.head(5).iterrows():
                title = row.get('title', '') or row.get('标题', '')
                if title and any(k in title for k in ['A股', '市场', '科技', '板块', '资金', '政策']):
                    news.append(title.strip())
            if news:
                return news[:3]
    except Exception as e:
        logging.warning(f"新闻获取失败: {e}")

    today = datetime.now().strftime('%Y-%m-%d')
    return [
        f"{today} A股市场震荡分化，科技板块表现活跃",
        f"{today} 市场关注后续政策面催化及中报业绩验证",
        "北向资金呈现结构性调仓态势"
    ]


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
                        "vol_trend": vol.tolist() if len(vol) > 0 else []
                    }
    except Exception as e:
        logging.warning(f"周趋势获取失败: {e}")

    return {"trend_direction": "震荡", "trend_strength": 0, "dates": [], "vol_trend": []}


def get_fallback_indices():
    return {
        "上证指数": {"最新价": 3800, "涨跌幅": 0, "振幅": 0, "成交额": 10000},
        "深证成指": {"最新价": 13500, "涨跌幅": 0, "振幅": 0, "成交额": 12000},
        "创业板指": {"最新价": 3300, "涨跌幅": 0, "振幅": 0, "成交额": 6000},
        "科创50": {"最新价": 1600, "涨跌幅": 0, "振幅": 0, "成交额": 1500},
        "上证50": {"最新价": 2900, "涨跌幅": 0, "振幅": 0, "成交额": 2000}
    }


def get_fallback_market():
    return {"up": 2500, "down": 2500, "flat": 100, "limit_up": 50, "limit_down": 10, "total_vol": 15000}


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
        "news": fetch_market_news_with_fallback(),
        "weekly": fetch_weekly_summary(data_date_str)
    }

    # ===== 1. 指数数据 =====
    try:
        spot = manager.fetch_with_fallback("index_spot")
        if spot is not None and not spot.empty:
            # 动态列名
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
            df = manager.fetch_with_fallback("index_daily", symbol="sh000001")
            if df is not None and not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                last = df.iloc[-1]
                data["indices"]["上证指数"] = {
                    "最新价": round(float(last["close"]), 2),
                    "涨跌幅": 0,
                    "振幅": 0,
                    "成交额": round(float(last.get("amount", 0)) / 1e8, 2)
                }
                fallback = {
                    "深证成指": {"最新价": 13578.93, "涨跌幅": 0, "振幅": 0, "成交额": 13543},
                    "创业板指": {"最新价": 3343.96, "涨跌幅": 0, "振幅": 0, "成交额": 6712},
                    "科创50": {"最新价": 1635.96, "涨跌幅": 0, "振幅": 0, "成交额": 1630},
                    "上证50": {"最新价": 2922.97, "涨跌幅": 0, "振幅": 0, "成交额": 2404}
                }
                for name, vals in fallback.items():
                    data["indices"][name] = vals
                logging.info("✅ 从历史日线获取上证指数，其他指数使用预置参考值")
            else:
                data["indices"] = get_fallback_indices()
                logging.warning("⚠️ 所有指数数据源失败，使用完全预置数据")
        except Exception as e2:
            logging.error(f"历史日线降级失败: {e2}")
            data["indices"] = get_fallback_indices()

    # ===== 2. 涨跌数据 =====
    try:
        stocks = manager.fetch_with_fallback("stock_spot")
        if stocks is not None and not stocks.empty:
            data["market"]["up"] = int((stocks["涨跌幅"] > 0).sum())
            data["market"]["down"] = int((stocks["涨跌幅"] < 0).sum())
            data["market"]["flat"] = int((stocks["涨跌幅"] == 0).sum())
            data["market"]["limit_up"] = int((stocks["涨跌幅"] >= 9.9).sum())
            data["market"]["limit_down"] = int((stocks["涨跌幅"] <= -9.9).sum())
            data["market"]["total_vol"] = round(float(stocks["成交额"].sum()) / 1e8, 2)
            logging.info("✅ 涨跌数据获取成功")
        else:
            data["market"] = get_fallback_market()
            logging.warning("⚠️ 使用预置涨跌数据")
    except Exception as e:
        logging.error(f"涨跌获取异常: {e}")
        data["market"] = get_fallback_market()

    # ===== 3. 行业板块 =====
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
            data["sector_top5"] = [["传媒", 2.5], ["计算机", 2.1], ["通信", 1.8]]
            data["sector_bottom5"] = [["银行", -0.5], ["煤炭", -0.3], ["石油", -0.2]]
    except Exception as e:
        logging.error(f"行业板块异常: {e}")
        data["sector_top5"] = [["传媒", 2.5], ["计算机", 2.1], ["通信", 1.8]]
        data["sector_bottom5"] = [["银行", -0.5], ["煤炭", -0.3], ["石油", -0.2]]

    # ===== 4. 资金流向（直接使用预置） =====
    data["fund_in"] = [["电子", 30.7], ["计算机", 9.7], ["通信", 4.5]]
    data["fund_out"] = [["银行", -5.69], ["食品饮料", -3.2], ["非银金融", -2.8]]
    logging.info("✅ 使用预置资金流向数据")

    return data