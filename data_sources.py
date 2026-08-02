"""
多源数据管理器 - 集成 AkShare, easy-tdx, TickFlow, Baostock
"""
import logging
import time
import pandas as pd
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class DataSourceManager:
    def __init__(self):
        self.sources = [
            ("akshare", self._fetch_akshare),
            ("easy_tdx", self._fetch_easy_tdx),
            ("tickflow", self._fetch_tickflow),
            ("baostock", self._fetch_baostock),
        ]
        self._cache = {}

    def fetch_with_fallback(self, data_type, **kwargs):
        last_error = None
        for name, func in self.sources:
            try:
                logging.info(f"📡 尝试数据源: {name} 获取 {data_type}")
                result = func(data_type, **kwargs)
                if result is not None:
                    if hasattr(result, 'empty') and result.empty:
                        logging.warning(f"⚠️ {name} 返回空数据")
                        continue
                    logging.info(f"✅ {name} 成功")
                    return result
            except ImportError as e:
                logging.warning(f"⚠️ {name} 未安装: {e}")
                continue
            except Exception as e:
                logging.warning(f"⚠️ {name} 失败: {e}")
                last_error = e
                time.sleep(0.3)
        logging.error(f"❌ 所有数据源均失败: {last_error}")
        return None

    def _fetch_akshare(self, data_type, **kwargs):
        import akshare as ak
        if data_type == "index_spot":
            try:
                return ak.stock_zh_index_spot()
            except AttributeError:
                return ak.stock_zh_index_spot_sina()
        elif data_type == "stock_spot":
            return ak.stock_zh_a_spot_em()
        elif data_type == "sector":
            return ak.stock_sector_spot()
        elif data_type == "fund_flow":
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

    def _fetch_easy_tdx(self, data_type, **kwargs):
        try:
            from easy_tdx import MacClient, Market
        except ImportError:
            raise ImportError("easy-tdx 未安装")

        with MacClient.from_best_host() as client:
            if data_type == "market_stat":
                # 返回 DataFrame，列包含 up_count, down_count, neutral_count, limit_up_count, limit_down_count
                return client.get_market_stat()
            elif data_type == "index_daily":
                symbol = kwargs.get('symbol', 'sh000001')
                if symbol.startswith('sh'):
                    code = symbol[2:]
                    market = Market.SH
                elif symbol.startswith('sz'):
                    code = symbol[2:]
                    market = Market.SZ
                else:
                    code = symbol
                    market = Market.SH
                return client.get_stock_kline(market, code, count=200)
        return None

    def _fetch_tickflow(self, data_type, **kwargs):
        try:
            import tickflow as tf
        except ImportError:
            raise ImportError("tickflow 未安装")

        if data_type == "index_daily":
            symbol = kwargs.get('symbol', '000001.SZ')
            if symbol.startswith('sh'):
                symbol = symbol[2:] + '.SH'
            elif symbol.startswith('sz'):
                symbol = symbol[2:] + '.SZ'
            return tf.klines.get(symbol, period="1d", count=200, as_dataframe=True)
        return None

    def _fetch_baostock(self, data_type, **kwargs):
        try:
            import baostock as bs
            import pandas as pd
        except ImportError:
            raise ImportError("baostock 未安装")

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
                for col in ['open','high','low','close','volume','amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
        return None