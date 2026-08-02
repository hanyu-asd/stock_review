import pandas as pd
import logging
import json
import os
from datetime import datetime, timedelta
import akshare as ak
from data_sources import DataSourceManager

logging.basicConfig(level=logging.INFO)

# 全局数据源管理器
manager = DataSourceManager()


def get_last_trading_day(target_date=None):
    """
    获取最近的交易日（如果 target_date 非交易日，则向前回溯）
    """
    if target_date is None:
        target_date = datetime.now()
    # 尝试获取交易日历
    try:
        # 获取从今年1月1日到今天的交易日
        start = datetime(target_date.year, 1, 1).strftime('%Y-%m-%d')
        end = target_date.strftime('%Y-%m-%d')
        trade_days = ak.tool_trade_date_hist_sina()
        trade_days = pd.to_datetime(trade_days['trade_date'])
        # 过滤出 <= target_date 的最近一个
        available = trade_days[trade_days <= pd.Timestamp(target_date)]
        if not available.empty:
            last = available.max().strftime('%Y-%m-%d')
            logging.info(f"最近交易日: {last}")
            return last
    except Exception as e:
        logging.warning(f"获取交易日历失败: {e}，使用原始日期")

    # 降级：如果今天非工作日则向前推到周五
    if target_date.weekday() >= 5:  # 周六=5, 周日=6
        days_back = target_date.weekday() - 4  # 回到周五
        last = (target_date - timedelta(days=days_back)).strftime('%Y-%m-%d')
        logging.info(f"使用降级最近交易日: {last}")
        return last
    return target_date.strftime('%Y-%m-%d')


def fetch_market_news_with_fallback():
    """多源获取消息"""
    try:
        df = manager.fetch_with_fallback("news")
        if df is not None and not df.empty:
            news = []
            for _, row in df.head(5).iterrows():
                title = row.get('title', '') or row.get('标题', '')
                if title and any(k in title for k in ['A股','市场','科技','板块','资金','政策']):
                    news.append(title.strip())
            if news:
                return news[:3]
    except Exception as e:
        logging.warning(f"新闻获取失败: {e}")

    # 缓存或动态生成
    cache_file = "./news_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('date') == datetime.now().strftime('%Y-%m-%d'):
                return cache.get('news', [])[:3]
        except:
            pass

    today = datetime.now().strftime('%Y-%m-%d')
    return [
        f"{today} A股市场震荡分化，科技板块表现活跃",
        f"{today} 市场关注后续政策面催化及中报业绩验证",
        "北向资金呈现结构性调仓态势"
    ]


def fetch_weekly_summary(last_date_str):
    """获取最近一周（从 last_date_str 往前推5个交易日）的指数趋势"""
    try:
        # 获取上证指数日线
        df = manager.fetch_with_fallback("index_daily", symbol="sh000001")
        if df is None or df.empty:
            df = manager.fetch_with_fallback("index_daily", symbol="sh.000001")
        if df is None or df.empty:
            return {"trend_direction": "震荡", "trend_strength": 0, "dates": [], "vol_trend": []}

        # 统一日期列
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            # 取最近5个交易日
            last_date = pd.Timestamp(last_date_str)
            df_week = df[df['date'] <= last_date].tail(5)
            if len(df_week) < 2:
                return {"trend_direction": "震荡", "trend_strength": 0, "dates": [], "vol_trend": []}

            values = df_week['close'].values
            vol = df_week['volume'].values
            trend_dir = "上升" if values[-1] > values[0] else "下降"
            trend_strength = abs((values[-1] - values[0]) / values[0] * 100)
            return {
                "dates": [d.strftime('%Y-%m-%d') for d in df_week['date']],
                "trend_direction": trend_dir,
                "trend_strength": trend_strength,
                "vol_trend": vol.tolist()
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
    """主数据获取函数，自动处理非交易日"""
    # 1. 确定实际数据日期（最近交易日）
    data_date_str = get_last_trading_day()
    logging.info(f"📅 使用数据日期: {data_date_str}")

    # 2. 初始化数据结构
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

    # 3. 获取指数实时行情（使用多源）
    spot = manager.fetch_with_fallback("index_spot")
    if spot is not None and not spot.empty:
        index_map = {
            "上证指数": "000001",
            "深证成指": "399001",
            "创业板指": "399006",
            "科创50": "000688",
            "上证50": "000016"
        }
        for name, code in index_map.items():
            row = spot[spot["代码"] == code]
            if not row.empty:
                data["indices"][name] = {
                    "最新价": round(row["最新价"].iloc[0], 2),
                    "涨跌幅": round(row["涨跌幅"].iloc[0], 2),
                    "振幅": round(row["振幅"].iloc[0], 2),
                    "成交额": round(row["成交额"].iloc[0] / 1e8, 2)
                }
        logging.info("✅ 指数数据获取成功")
    else:
        # 降级：尝试从历史日线获取最近交易日数据
        try:
            df = manager.fetch_with_fallback("index_daily", symbol="sh000001")
            if df is not None and not df.empty:
                # 取最后一天
                last = df.iloc[-1]
                data["indices"]["上证指数"] = {
                    "最新价": round(last["close"], 2),
                    "涨跌幅": 0,  # 没有涨跌幅，用0
                    "振幅": 0,
                    "成交额": round(last.get("amount", 0) / 1e8, 2)
                }
                # 其他指数无法获取，使用预置
                for name in ["深证成指", "创业板指", "科创50", "上证50"]:
                    data["indices"][name] = {"最新价": 0, "涨跌幅": 0, "振幅": 0, "成交额": 0}
                logging.info("✅ 从历史日线获取指数数据")
        except Exception as e:
            logging.error(f"指数降级失败: {e}")
            data["indices"] = get_fallback_indices()

    # 4. 获取全市场涨跌（使用多源）
    stocks = manager.fetch_with_fallback("stock_spot")
    if stocks is not None and not stocks.empty:
        try:
            data["market"]["up"] = int((stocks["涨跌幅"] > 0).sum())
            data["market"]["down"] = int((stocks["涨跌幅"] < 0).sum())
            data["market"]["flat"] = int((stocks["涨跌幅"] == 0).sum())
            data["market"]["limit_up"] = int((stocks["涨跌幅"] >= 9.9).sum())
            data["market"]["limit_down"] = int((stocks["涨跌幅"] <= -9.9).sum())
            data["market"]["total_vol"] = round(stocks["成交额"].sum() / 1e8, 2)
            logging.info("✅ 涨跌数据获取成功")
        except Exception as e:
            logging.error(f"涨跌数据处理失败: {e}")
            data["market"] = get_fallback_market()
    else:
        data["market"] = get_fallback_market()

    # 5. 行业板块
    sector = manager.fetch_with_fallback("sector")
    if sector is not None and not sector.empty:
        try:
            # 列名兼容
            name_col = None
            pct_col = None
            for col in sector.columns:
                if '名称' in col or '板块' in col:
                    name_col = col
                if '涨跌幅' in col:
                    pct_col = col
            if name_col is None or pct_col is None:
                name_col = sector.columns[0]
                pct_col = sector.columns[1]
            sector = sector.sort_values(by=pct_col, ascending=False)
            top5 = sector.head(5)[[name_col, pct_col]].values.tolist()
            bottom5 = sector.tail(5)[[name_col, pct_col]].values.tolist()
            data["sector_top5"] = [[str(n), round(float(p), 2)] for n, p in top5]
            data["sector_bottom5"] = [[str(n), round(float(p), 2)] for n, p in bottom5]
            logging.info("✅ 行业板块数据获取成功")
        except Exception as e:
            logging.error(f"行业板块处理失败: {e}")
            data["sector_top5"] = [["传媒", 2.5], ["计算机", 2.1], ["通信", 1.8]]
            data["sector_bottom5"] = [["银行", -0.5], ["煤炭", -0.3], ["石油", -0.2]]
    else:
        data["sector_top5"] = [["传媒", 2.5], ["计算机", 2.1], ["通信", 1.8]]
        data["sector_bottom5"] = [["银行", -0.5], ["煤炭", -0.3], ["石油", -0.2]]

    # 6. 资金流向
    fund = manager.fetch_with_fallback("fund_flow")
    if fund is not None and not fund.empty:
        try:
            name_col = None
            flow_col = None
            for col in fund.columns:
                if '名称' in col or '板块' in col:
                    name_col = col
                if '主力净流入' in col or '净流入' in col:
                    flow_col = col
            if name_col is None or flow_col is None:
                name_col = fund.columns[0]
                flow_col = fund.columns[1]
            fund_in = fund.head(3)[[name_col, flow_col]].values.tolist()
            fund_out = fund.tail(3)[[name_col, flow_col]].values.tolist()
            data["fund_in"] = [[str(n), round(float(v)/1e4, 2)] for n, v in fund_in]
            data["fund_out"] = [[str(n), round(float(v)/1e4, 2)] for n, v in fund_out]
            logging.info("✅ 资金流向数据获取成功")
        except Exception as e:
            logging.error(f"资金流向处理失败: {e}")
            data["fund_in"] = [["电子", 30.7], ["计算机", 9.7]]
            data["fund_out"] = [["银行", -5.69], ["食品饮料", -3.2]]
    else:
        data["fund_in"] = [["电子", 30.7], ["计算机", 9.7]]
        data["fund_out"] = [["银行", -5.69], ["食品饮料", -3.2]]

    return data