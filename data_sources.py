"""
多数据源管理器 - 自动故障转移
所有数据源统一返回 pandas DataFrame
"""
import logging
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)


class DataSourceManager:
    """多数据源自动切换管理器"""

    def __init__(self):
        self.sources = []
        self._register_sources()

    def _register_sources(self):
        """注册所有可用的数据源（按优先级从高到低）"""
        self.sources = [
            ("akshare", self._fetch_akshare),
            ("efinance", self._fetch_efinance),
            ("baostock", self._fetch_baostock),
            ("tickflow", self._fetch_tickflow),
            ("easytdx", self._fetch_easytdx),
        ]

    def fetch_with_fallback(self, fetch_func, *args, **kwargs):
        """
        通用数据获取方法：依次尝试所有数据源，直到成功
        """
        last_error = None
        for source_name, source_func in self.sources:
            try:
                logging.info(f"📡 尝试数据源: {source_name}")
                result = source_func(*args, **kwargs)
                if result is not None and not result.empty:
                    logging.info(f"✅ 数据源 {source_name} 成功")
                    return result
            except Exception as e:
                logging.warning(f"⚠️ 数据源 {source_name} 失败: {e}")
                last_error = e
                time.sleep(0.3)
        logging.error(f"❌ 所有数据源均失败: {last_error}")
        return None

    # ==================== 各数据源实现 ====================

    def _fetch_akshare(self, period="spot", symbol=None, start_date=None, end_date=None):
        """AkShare 数据源"""
        try:
            import akshare as ak
            if period == "spot":
                return ak.stock_zh_a_spot_em()
            elif period == "index_spot":
                return ak.stock_zh_index_spot()
            elif period == "daily" and symbol:
                return ak.stock_zh_index_daily(symbol=symbol)
            elif period == "sector":
                return ak.stock_sector_spot()
            elif period == "fund_flow":
                return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流向")
        except Exception as e:
            logging.warning(f"AkShare 子调用失败: {e}")
            return None

    def _fetch_efinance(self, period="spot", symbol=None, start_date=None, end_date=None):
        """efinance 数据源（东方财富同源）"""
        try:
            import efinance as ef
            if period == "spot":
                return ef.stock.get_realtime_quotes()
            elif period == "daily" and symbol:
                return ef.stock.get_quote_history(symbol, start_date=start_date, end_date=end_date)
        except ImportError:
            return None
        except Exception as e:
            logging.warning(f"efinance 失败: {e}")
            return None

    def _fetch_baostock(self, period="daily", symbol=None, start_date=None, end_date=None):
        """Baostock 数据源（A股历史数据最稳）"""
        try:
            import baostock as bs
            import pandas as pd
            if period == "daily" and symbol:
                lg = bs.login()
                if lg.error_code != '0':
                    return None
                rs = bs.query_history_k_data_plus(
                    symbol,
                    "date,open,high,low,close,volume,amount",
                    start_date=start_date or "2020-01-01",
                    end_date=end_date or datetime.now().strftime("%Y-%m-%d")
                )
                data_list = []
                while (rs.error_code == '0') and rs.next():
                    data_list.append(rs.get_row_data())
                bs.logout()
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    return df
        except ImportError:
            return None
        except Exception as e:
            logging.warning(f"baostock 失败: {e}")
            return None

    def _fetch_tickflow(self, period="daily", symbol=None, start_date=None, end_date=None):
        """TickFlow 数据源（免费版无需注册）"""
        try:
            from tickflow import TickFlow
            tf = TickFlow.free()
            if period == "daily" and symbol:
                return tf.klines.get(symbol, period="1d", count=200, as_dataframe=True)
        except ImportError:
            return None
        except Exception as e:
            logging.warning(f"tickflow 失败: {e}")
            return None

    def _fetch_easytdx(self, period="spot", symbol=None, start_date=None, end_date=None):
        """easy-tdx 数据源（免费，无API Key）"""
        try:
            from easy_tdx import MacClient, Market
            with MacClient.from_best_host() as client:
                if period == "daily" and symbol:
                    return client.get_stock_kline(Market.SH, symbol, count=200)
                elif period == "spot":
                    # 获取全市场行情
                    return client.get_stock_list()
        except ImportError:
            return None
        except Exception as e:
            logging.warning(f"easy-tdx 失败: {e}")
            return None


# ==================== 便捷函数 ====================

def get_market_data_with_fallback(data_type="spot", **kwargs):
    """获取市场数据（自动故障转移）"""
    manager = DataSourceManager()
    return manager.fetch_with_fallback(manager._fetch_akshare, period=data_type, **kwargs)