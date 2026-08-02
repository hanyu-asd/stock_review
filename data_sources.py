"""
多源数据管理器 - 支持 AkShare, Baostock, efinance 等
所有方法返回 pandas DataFrame
"""
import logging
import time
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)


class DataSourceManager:
    def __init__(self):
        self.sources = [
            ("akshare", self._fetch_akshare),
            ("baostock", self._fetch_baostock),
            ("efinance", self._fetch_efinance),
        ]
        self._cache = {}

    def fetch_with_fallback(self, data_type, **kwargs):
        """
        统一入口：data_type 可选 'index_spot', 'stock_spot', 'sector', 'fund_flow', 'index_daily'
        """
        last_error = None
        for name, func in self.sources:
            try:
                logging.info(f"📡 尝试数据源: {name} 获取 {data_type}")
                result = func(data_type, **kwargs)
                if result is not None and not result.empty:
                    logging.info(f"✅ {name} 成功")
                    return result
            except Exception as e:
                logging.warning(f"⚠️ {name} 失败: {e}")
                last_error = e
                time.sleep(0.5)
        logging.error(f"❌ 所有数据源失败: {last_error}")
        return None

    # ---------- 各数据源实现 ----------

    def _fetch_akshare(self, data_type, **kwargs):
        import akshare as ak
        if data_type == "index_spot":
            return ak.stock_zh_index_spot()
        elif data_type == "stock_spot":
            return ak.stock_zh_a_spot_em()
        elif data_type == "sector":
            return ak.stock_sector_spot()
        elif data_type == "fund_flow":
            # 兼容不同参数
            try:
                return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流向")
            except:
                return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业")
        elif data_type == "index_daily":
            symbol = kwargs.get('symbol', 'sh000001')
            return ak.stock_zh_index_daily(symbol=symbol)
        elif data_type == "news":
            return ak.stock_news_em()
        return None

    def _fetch_baostock(self, data_type, **kwargs):
        try:
            import baostock as bs
            if data_type == "index_daily":
                symbol = kwargs.get('symbol', 'sh.000001')
                start = kwargs.get('start_date', '2020-01-01')
                end = kwargs.get('end_date', datetime.now().strftime('%Y-%m-%d'))
                lg = bs.login()
                if lg.error_code != '0':
                    return None
                rs = bs.query_history_k_data_plus(symbol,
                    "date,open,high,low,close,volume,amount",
                    start_date=start, end_date=end)
                data_list = []
                while (rs.error_code == '0') and rs.next():
                    data_list.append(rs.get_row_data())
                bs.logout()
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    # 转换数据类型
                    for col in ['open','high','low','close','volume','amount']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
        except Exception as e:
            logging.warning(f"baostock 失败: {e}")
        return None

    def _fetch_efinance(self, data_type, **kwargs):
        try:
            import efinance as ef
            if data_type == "stock_spot":
                return ef.stock.get_realtime_quotes()
            elif data_type == "index_daily":
                # efinance 获取股票历史
                symbol = kwargs.get('symbol', '000001')
                return ef.stock.get_quote_history(symbol, start_date=kwargs.get('start_date'))
        except Exception as e:
            logging.warning(f"efinance 失败: {e}")
        return None