"""
多源数据管理器 - 集成 AkShare, easy-tdx, TickFlow, Baostock
支持自动故障转移
"""
import logging
import time
import pandas as pd
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class DataSourceManager:
    def __init__(self):
        # 数据源注册（优先级从高到低）
        self.sources = [
            ("akshare", self._fetch_akshare),
            ("easy_tdx", self._fetch_easy_tdx),
            ("tickflow", self._fetch_tickflow),
            ("baostock", self._fetch_baostock),
        ]
        self._cache = {}

    def fetch_with_fallback(self, data_type, **kwargs):
        """
        统一数据获取接口
        data_type 可选: index_spot, stock_spot, sector, fund_flow, index_daily, news
        """
        last_error = None
        for name, func in self.sources:
            try:
                logging.info(f"📡 尝试数据源: {name} 获取 {data_type}")
                result = func(data_type, **kwargs)
                if result is not None:
                    # 对 DataFrame 检查是否为空
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
        """AkShare 数据源"""
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
        """
        easy-tdx 数据源（通达信协议，免费、无需注册、无API Key）
        注意：需要安装 easy-tdx 库，导入包名为 easy_tdx
        """
        try:
            from easy_tdx import MacClient, Market
        except ImportError:
            raise ImportError("easy-tdx 未安装")

        with MacClient.from_best_host() as client:
            if data_type == "stock_spot":
                # 获取全市场实时行情列表（返回的是列表，需转DataFrame）
                # 注意：get_stock_list 可能返回所有股票代码列表，不包含行情；
                # 更可能是 get_quote 获取单只，但这里我们尝试 get_stock_list 并获取每只的行情？
                # 实际上 easy-tdx 有 get_stock_list 只返回代码，没有实时数据。
                # 为了兼容，我们尝试获取一个指数行情作为替代，或者使用 get_quote 批量获取。
                # 由于 easy-tdx 没有直接的批量实时行情接口，我们暂时返回 None，让下一个源尝试。
                logging.warning("easy-tdx 暂不支持批量实时行情，跳过")
                return None
            elif data_type == "index_daily":
                symbol = kwargs.get('symbol', 'sh000001')
                # 指数代码可能是 'sh000001'，但 easy_tdx 要求 Market 和 code 分开
                # 这里简单处理，如果是 'sh000001' 则用 Market.SH 和 '000001'
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
        """
        TickFlow 数据源（efinance 作者新作，免费）
        """
        try:
            import tickflow as tf
        except ImportError:
            raise ImportError("tickflow 未安装")

        if data_type == "stock_spot":
            # 获取实时行情，需要传入股票代码列表，这里我们默认获取上证50成分股？
            # 实际上难以批量获取全市场，但我们可以尝试获取一个代表性的指数
            # 为简化，我们返回 None，让 baostock 或预置数据兜底
            return None
        elif data_type == "index_daily":
            symbol = kwargs.get('symbol', '000001.SZ')
            # 转换符号格式：例如 sh000001 -> 000001.SH
            if symbol.startswith('sh'):
                symbol = symbol[2:] + '.SH'
            elif symbol.startswith('sz'):
                symbol = symbol[2:] + '.SZ'
            return tf.klines.get(symbol, period="1d", count=200, as_dataframe=True)
        return None

    def _fetch_baostock(self, data_type, **kwargs):
        """Baostock 备用数据源"""
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