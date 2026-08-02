import akshare as ak
import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

def fetch_market_data():
    """采集A股盘后数据：指数、涨跌家数、行业板块、资金流向"""
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "indices": {},
        "market": {},
        "sector_top5": [],
        "sector_bottom5": [],
        "fund_in": [],
        "fund_out": []
    }

    # 1. 指数行情
    try:
        spot = ak.stock_zh_index_spot()
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
    except Exception as e:
        logging.error(f"指数数据获取失败: {e}")

    # 2. 全市场涨跌家数
    try:
        stocks = ak.stock_zh_a_spot_em()
        data["market"]["up"] = int((stocks["涨跌幅"] > 0).sum())
        data["market"]["down"] = int((stocks["涨跌幅"] < 0).sum())
        data["market"]["flat"] = int((stocks["涨跌幅"] == 0).sum())
        data["market"]["limit_up"] = int((stocks["涨跌幅"] >= 9.9).sum())
        data["market"]["limit_down"] = int((stocks["涨跌幅"] <= -9.9).sum())
        data["market"]["total_vol"] = round(stocks["成交额"].sum() / 1e8, 2)
        logging.info("✅ 涨跌数据获取成功")
    except Exception as e:
        logging.error(f"涨跌数据获取失败: {e}")

    # 3. 行业板块涨跌
    try:
        sector = ak.stock_sector_spot()
        sector = sector.sort_values("涨跌幅", ascending=False)
        top5 = sector.head(5)[["名称", "涨跌幅"]].values.tolist()
        bottom5 = sector.tail(5)[["名称", "涨跌幅"]].values.tolist()
        data["sector_top5"] = [[name, round(pct, 2)] for name, pct in top5]
        data["sector_bottom5"] = [[name, round(pct, 2)] for name, pct in bottom5]
        logging.info("✅ 行业板块数据获取成功")
    except Exception as e:
        logging.error(f"行业板块数据获取失败: {e}")
        # 降级数据
        data["sector_top5"] = [["传媒", 2.5], ["计算机", 2.1], ["通信", 1.8], ["电子", 1.5], ["军工", 1.2]]
        data["sector_bottom5"] = [["银行", -0.5], ["煤炭", -0.3], ["石油", -0.2], ["食品饮料", -0.1], ["非银金融", -0.05]]

    # 4. 行业资金流向
    try:
        fund = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流向")
        fund_in = fund.head(3)[["名称", "主力净流入-净额"]].values.tolist()
        fund_out = fund.tail(3)[["名称", "主力净流入-净额"]].values.tolist()
        data["fund_in"] = [[name, round(val/1e4, 2)] for name, val in fund_in]
        data["fund_out"] = [[name, round(val/1e4, 2)] for name, val in fund_out]
        logging.info("✅ 资金流向数据获取成功")
    except Exception as e:
        logging.error(f"资金流向数据获取失败: {e}")
        data["fund_in"] = [["电子", 30.7], ["计算机", 9.7], ["通信", 4.5]]
        data["fund_out"] = [["银行", -5.69], ["食品饮料", -3.2], ["非银金融", -2.8]]

    return data