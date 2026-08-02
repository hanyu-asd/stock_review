"""
多源数据管理器 - 盘后场景专用
主数据源: akshare (历史日线)
备用数据源: baostock, easy_tdx, tickflow (均用于日线数据)
"""
import logging
import time
import pandas as pd
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class DataSourceManager:
    def __init__(self):
        # 数据源按优先级排列，均用于 index_daily 类型
        self.sources = [
            ("akshare", self._fetch_akshare),
            ("baostock", self._fetch_baostock),
            ("easy_tdx", self._fetch_easy_tdx),
            ("tickflow", self._fetch_tickflow),
        ]
        self._cache = {}

    def fetch_with_fallback(self, data_type, **kwargs):
        """
        统一数据获取接口
        data_type 可选: index_daily, sector, news, stock_hist
        """
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

    # ---------- 各数据源实现 ----------

    def _fetch_akshare(self, data_type, **kwargs):
        import akshare as ak
        if data_type == "index_daily":
            symbol = kwargs.get('symbol', 'sh000001')
            return ak.stock_zh_index_daily(symbol=symbol)
        elif data_type == "sector":
            return ak.stock_sector_spot()
        elif data_type == "news":
            return ak.stock_news_em()
        elif data_type == "stock_hist":
            start = kwargs.get('start_date')
            end = kwargs.get('end_date')
            return ak.stock_zh_a_hist(start_date=start, end_date=end)
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
                for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
        return None

    def _fetch_easy_tdx(self, data_type, **kwargs):
        """
        easy-tdx 备用数据源（通达信协议）
        需安装: pip install easy-tdx
        """
        try:
            from easy_tdx import MacClient, Market
        except ImportError:
            raise ImportError("easy-tdx 未安装")

        if data_type == "index_daily":
            symbol = kwargs.get('symbol', 'sh000001')
            # 解析代码
            if symbol.startswith('sh'):
                code = symbol[2:]
                market = Market.SH
            elif symbol.startswith('sz'):
                code = symbol[2:]
                market = Market.SZ
            else:
                code = symbol
                market = Market.SH
            with MacClient.from_best_host() as client:
                return client.get_stock_kline(market, code, count=200)
        return None

    def _fetch_tickflow(self, data_type, **kwargs):
        """
        tickflow 备用数据源（efinance 作者新作）
        需安装: pip install tickflow
        """
        try:
            import tickflow as tf
        except ImportError:
            raise ImportError("tickflow 未安装")

        if data_type == "index_daily":
            symbol = kwargs.get('symbol', '000001.SZ')
            # 转换符号格式
            if symbol.startswith('sh'):
                symbol = symbol[2:] + '.SH'
            elif symbol.startswith('sz'):
                symbol = symbol[2:] + '.SZ'
            return tf.klines.get(symbol, period="1d", count=200, as_dataframe=True)
        return None