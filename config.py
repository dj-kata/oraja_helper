import json
import os

class Config:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.oraja_path = ""
        self.player_path = ""
        self.websocket_host = "localhost"
        self.websocket_port = 4444
        self.websocket_password = ""
        self.enable_websocket = False
        self.enable_autotweet = False
        self.autoload_offset = 0
        self.enable_register_conditions = False  # 画面判定条件設定機能の有効/無効
        
        # ウィンドウ位置設定
        self.main_window_x = 100
        self.main_window_y = 100
        self.main_window_width = 500
        self.main_window_height = 300

        # スキップする難易度表の名前を登録
        # settings.py側はOKListを選択する形になっているが、DiffTableではこちらの方が扱いやすいので変換している。
        self.difftable_nglist = []
        
        self.load_config()
    
    def load_config(self):
        """設定ファイルから設定を読み込む"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.oraja_path = config_data.get("oraja_path", "")
                    self.player_path = config_data.get("player_path", "")
                    self.websocket_host = config_data.get("websocket_host", "localhost")
                    self.websocket_port = config_data.get("websocket_port", 4444)
                    self.websocket_password = config_data.get("websocket_password", "")
                    self.enable_websocket = config_data.get("enable_websocket", False)
                    self.enable_autotweet = config_data.get("enable_autotweet", False)
                    self.autoload_offset = config_data.get("autoload_offset", 0)
                    self.enable_register_conditions = config_data.get("enable_register_conditions", False)
                    
                    # ウィンドウ位置設定
                    window_config = config_data.get("window", {})
                    self.main_window_x = window_config.get("x", 100)
                    self.main_window_y = window_config.get("y", 100)
                    self.main_window_width = window_config.get("width", 500)
                    self.main_window_height = window_config.get("height", 300)

                    self.difftable_nglist = config_data.get('difftable_nglist', [])
            except Exception as e:
                print(f"設定ファイル読み込みエラー: {e}")
    
    def save_config(self):
        """設定ファイルに設定を保存する"""
        config_data = {
            "oraja_path": self.oraja_path,
            "player_path": self.player_path,
            "websocket_host": self.websocket_host,
            "websocket_port": self.websocket_port,
            "websocket_password": self.websocket_password,
            "enable_websocket": self.enable_websocket,
            "enable_autotweet": self.enable_autotweet,
            "autoload_offset": self.autoload_offset,
            "enable_register_conditions": self.enable_register_conditions,
            "window": {
                "x": self.main_window_x,
                "y": self.main_window_y,
                "width": self.main_window_width,
                "height": self.main_window_height
            },
            "difftable_nglist": self.difftable_nglist
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"設定ファイル保存エラー: {e}")
    
    def save_window_position(self, x, y, width, height):
        """ウィンドウ位置を保存"""
        self.main_window_x = x
        self.main_window_y = y
        self.main_window_width = width
        self.main_window_height = height
        self.save_config()
    
    def get_target_file_path(self):
        """監視対象のファイルパスを取得する（例：指定フォルダ内のtarget.txtファイル）"""
        if self.oraja_path:
            return os.path.join(self.oraja_path, "target.txt")
        return ""