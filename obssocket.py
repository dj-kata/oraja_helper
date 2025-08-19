import threading
import time
from typing import Callable, Optional
import logging, logging.handlers
import traceback
import os
import base64
from PIL import Image
import io

os.makedirs('log', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

try:
    import obsws_python as obs
except ImportError:
    obs = None
    print("Warning: obsws_python not installed. Install with: pip install obsws-python")

class OBSWebSocketManager:
    def __init__(self, status_callback: Optional[Callable[[str, bool], None]] = None):
        """
        OBS WebSocket接続を管理するクラス
        
        Args:
            status_callback: 接続状態変更時に呼び出されるコールバック関数
                           (status_message: str, is_connected: bool) -> None
        """
        self.client = None
        self.is_connected = False
        self.status_callback = status_callback
        self.connection_thread = None
        self.should_reconnect = False
        self.config = None
        
        # ログ設定
        self.logger = logging.getLogger(__name__)
        
    def set_config(self, config):
        """設定オブジェクトを設定"""
        self.config = config
        
    def connect(self, host: str, port: int, password: str = "") -> bool:
        """
        OBS WebSocketサーバーに接続
        
        Args:
            host: ホスト名
            port: ポート番号
            password: パスワード（オプション）
            
        Returns:
            bool: 接続成功可否
        """
        if obs is None:
            self._update_status("obsws_python がインストールされていません", False)
            return False
            
        try:
            # 既存の接続があれば切断
            self.disconnect()
            
            self._update_status("OBS WebSocketに接続中...", False)
            
            # OBS WebSocketクライアント作成（タイムアウト短縮で切断検出を向上）
            self.client = obs.ReqClient(host=host, port=port, password=password, timeout=3)
            
            # 接続テスト（バージョン情報取得）
            version_info = self.client.get_version()
            obs_version = version_info.obs_version
            ws_version = version_info.obs_web_socket_version
            
            self.is_connected = True
            self._update_status(f"OBS WebSocket接続完了 (OBS: {obs_version}, WS: {ws_version})", True)
            
            self.logger.info(f"OBS WebSocket connected to {host}:{port}")
            return True
            
        except ConnectionRefusedError:
            self.is_connected = False
            error_message = f"OBS WebSocket接続拒否: {host}:{port} (OBSが起動していない可能性があります)"
            self._update_status(error_message, False)
            self.logger.error(error_message)
        except TimeoutError:
            self.is_connected = False
            error_message = f"OBS WebSocket接続タイムアウト: {host}:{port}"
            self._update_status(error_message, False)
            self.logger.error(error_message)
        except Exception as e:
            self.is_connected = False
            error_message = f"OBS WebSocket接続エラー: {str(e)}"
            self._update_status(error_message, False)
            self.logger.error(error_message)
            
        # エラー時のクリーンアップ
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
            self.client = None
                
        return False
    
    def disconnect(self):
        """OBS WebSocketから切断"""
        self.should_reconnect = False
        
        if self.client:
            try:
                self.client.disconnect()
                self.logger.info("OBS WebSocket disconnected")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")
            finally:
                self.client = None
                
        self.is_connected = False
        self._update_status("OBS WebSocket切断", False)
    
    def auto_connect(self):
        """設定に基づいて自動接続を試行"""
        if not self.config or not self.config.enable_websocket:
            self._update_status("WebSocket連携が無効です", False)
            return False
            
        if not self.config.websocket_host:
            self._update_status("WebSocketホストが設定されていません", False)
            return False
            
        return self.connect(
            self.config.websocket_host,
            self.config.websocket_port,
            self.config.websocket_password
        )
    
    def start_auto_reconnect(self):
        """自動再接続を開始"""
        if self.connection_thread is None or not self.connection_thread.is_alive():
            self.should_reconnect = True
            self.connection_thread = threading.Thread(target=self._connection_worker, daemon=True)
            self.connection_thread.start()
    
    def stop_auto_reconnect(self):
        """自動再接続を停止"""
        self.should_reconnect = False
        
    def _connection_worker(self):
        """接続監視・自動再接続ワーカー"""
        check_interval = 2  # 接続確認間隔を2秒に短縮
        reconnect_interval = 0
        
        while self.should_reconnect:
            try:
                # 未接続で再接続が必要な場合
                if not self.is_connected and self.config and self.config.enable_websocket:
                    # 再接続間隔の制御（5秒間隔で再接続試行）
                    if reconnect_interval <= 0:
                        self.logger.info("Attempting auto-reconnect to OBS WebSocket...")
                        if self.auto_connect():
                            reconnect_interval = 0  # 接続成功時はリセット
                        else:
                            reconnect_interval = 5  # 失敗時は5秒待機
                    else:
                        reconnect_interval -= check_interval
                
                # 接続確認（より頻繁に、かつ複数の方法で確認）
                elif self.is_connected and self.client:
                    connection_lost = False
                    
                    try:
                        # 1. より軽量な接続確認（stats取得）
                        self.client.get_stats()
                    except Exception as e:
                        self.logger.warning(f"Stats check failed: {e}")
                        
                        # 2. フォールバック：バージョン情報で再確認
                        try:
                            self.client.get_version()
                        except Exception as e2:
                            self.logger.warning(f"Version check also failed: {e2}")
                            connection_lost = True
                    
                    # 接続が失われた場合の処理
                    if connection_lost:
                        self.logger.warning("OBS WebSocket connection lost")
                        self.is_connected = False
                        self._update_status("OBS WebSocket接続が失われました", False)
                        
                        # クリーンアップ
                        if self.client:
                            try:
                                self.client.disconnect()
                            except:
                                pass
                            self.client = None
                        
                        reconnect_interval = 3  # 3秒後に再接続開始
                            
            except Exception as e:
                self.logger.error(f"Connection worker error: {e}")
                # 予期しないエラーの場合も接続を切断
                if self.is_connected:
                    self.is_connected = False
                    self._update_status("OBS WebSocket予期しないエラー", False)
                    if self.client:
                        try:
                            self.client.disconnect()
                        except:
                            pass
                        self.client = None
            
            # 短い間隔で確認
            time.sleep(check_interval)
    
    def _update_status(self, message: str, is_connected: bool):
        """ステータス更新"""
        self.is_connected = is_connected
        if self.status_callback:
            try:
                self.status_callback(message, is_connected)
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")
    
    def get_status(self) -> tuple[str, bool]:
        """現在のステータスを取得"""
        if not obs:
            return "obsws_python がインストールされていません", False
        elif not self.config:
            return "設定が読み込まれていません", False
        elif not self.config.enable_websocket:
            return "WebSocket連携が無効です", False
        elif self.is_connected:
            return f"接続中 ({self.config.websocket_host}:{self.config.websocket_port})", True
        else:
            return "切断中", False
    
    def send_command(self, command_name: str, **kwargs):
        """
        OBSにコマンドを送信（汎用メソッド）
        
        Args:
            command_name: 実行するコマンド名
            **kwargs: コマンドのパラメータ
            
        Returns:
            コマンドの実行結果、またはエラー時はNone
        """
        if not self.is_connected or not self.client:
            self.logger.warning("OBS WebSocket not connected")
            return None
            
        try:
            # 動的にメソッドを呼び出し
            method = getattr(self.client, command_name)
            result = method(**kwargs)
            self.logger.info(f"OBS command executed: {command_name}")
            return result
        except AttributeError:
            self.logger.error(f"Unknown OBS command: {command_name}")
            return None
        except Exception as e:
            self.logger.error(f"OBS command failed: {command_name}, error: {e}")
            return None
    
    def get_scene_list(self):
        """シーン一覧を取得"""
        if not self.is_connected:
            return None
        try:
            return self.client.get_scene_list()
        except Exception as e:
            self.logger.error(f"Failed to get scene list: {e}")
            return None
    
    def set_current_scene(self, scene_name: str):
        """現在のシーンを変更"""
        return self.send_command("set_current_program_scene", scene_name=scene_name)
    
    def __del__(self):
        """デストラクタ"""
        self.disconnect()

    def change_scene(self,name:str):
        try:
            self.client.set_current_program_scene(name)
        except Exception:
            pass

    def get_scenes(self):
        try:
            res = self.client.get_scene_list()
            ret = res.scenes
            return res.scenes
        except Exception:
            logger.debug(traceback.format_exc())
            return []

    def get_sources(self, scene):
        ret = []
        try:
            allitem = self.client.get_scene_item_list(scene).scene_items
            for x in allitem:
                if x['isGroup']:
                    grp = self.client.get_group_scene_item_list(x['sourceName']).scene_items
                    for y in grp:
                        ret.append(y['sourceName'])
                ret.append(x['sourceName'])
        except Exception:
            logger.debug(traceback.format_exc())
        ret.reverse()
        return ret

    def change_text(self, source, text):
        try:
            res = self.client.set_input_settings(source, {'text':text}, True)
        except Exception:
            logger.debug(traceback.format_exc())

    def save_screenshot(self):
        #logger.debug(f'dst:{self.dst_screenshot}')
        try:
            res = self.client.save_source_screenshot(self.inf_source, 'png', self.dst_screenshot, self.picw, self.pich, 100)
            return res
        except Exception:
            logger.debug(traceback.format_exc())
            return False

    def save_screenshot_dst(self, dst):
        try:
            res = self.client.save_source_screenshot(self.inf_source, 'png', dst, self.picw, self.pich, 100)
            return res
        except Exception:
            logger.debug(traceback.format_exc())
            return False

    # 設定されたソースを取得し、PIL.Image形式で返す
    def get_screenshot(self):
        b = self.client.get_source_screenshot(self.inf_source, 'jpeg', self.picw, self.pich, 100).image_data
        b = b.split(',')[1]
        c = base64.b64decode(b) # バイナリ形式のはず？
        tmp = io.BytesIO(c)
        img = Image.open(tmp)
        return img

    def enable_source(self, scenename, sourceid): # グループ内のitemはscenenameにグループ名を指定する必要があるので注意
        try:
            res = self.client.set_scene_item_enabled(scenename, sourceid, enabled=True)
        except Exception as e:
            return e

    def disable_source(self, scenename, sourceid):
        try:
            res = self.client.set_scene_item_enabled(scenename, sourceid, enabled=False)
        except Exception as e:
            return e
        
    def refresh_source(self, sourcename):
        try:
            self.client.press_input_properties_button(sourcename, 'refreshnocache')
        except Exception:
            pass

    def search_itemid(self, scene, target):
        ret = scene, None # グループ名, ID
        try:
            allitem = self.client.get_scene_item_list(scene).scene_items
            for x in allitem:
                if x['sourceName'] == target:
                    ret = scene, x['sceneItemId']
                if x['isGroup']:
                    grp = self.client.get_group_scene_item_list(x['sourceName']).scene_items
                    for y in grp:
                        if y['sourceName'] == target:
                            ret = x['sourceName'], y['sceneItemId']

        except:
            pass
        return ret
    
    def get_scene_collection_list(self):
        """OBSに設定されたシーンコレクションの一覧をListで返す

        Returns:
            list: シーンコレクション名の文字列
        """
        try:
            return self.client.get_scene_collection_list().scene_collections
        except Exception:
            logger.debug(traceback.format_exc())
            return []
        
    def set_scene_collection(self, scene_collection:str):
        """シーンコレクションを引数で指定したものに変更する。

        Args:
            scene_collection (str): シーンコレクション名

        Returns:
            bool: 成功ならTrue,失敗したらFalse
        """
        try:
            self.client.set_current_scene_collection(scene_collection)
            return True
        except Exception:
            logger.debug(traceback.format_exc())
            return False

if __name__ == '__main__':
    from config import Config
    import time
    a = OBSWebSocketManager()
    config = Config()
    a.set_config(config)
    a.start_auto_reconnect()
    time.sleep(1)
    print(a.search_itemid('成果確認', 'receipt.html'))