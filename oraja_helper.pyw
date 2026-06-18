import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import time
import os, sys
import tempfile
import sys
import base64
import io
import datetime
import json
import traceback
from config import Config
from settings import SettingsWindow
from obs_control import OBSControlWindow, ImageRecognitionData, OBSWebSocketManager
from dataclass import *
from pickle_converter import *
from named_pipe_receiver import NamedPipeLineReceiver
from nexus_core import NexusCalculator
import requests
from bs4 import BeautifulSoup

# PILのインポート
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL not installed. Install with: pip install pillow")

# imagehashのインポート
try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("Warning: imagehash not installed. Install with: pip install imagehash")

try:
    with open('version.txt', 'r') as f:
        SWVER = f.readline().strip()
except Exception:
    SWVER = "v?.?.?"

import logging, logging.handlers
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

class ApplicationLock:
    """アプリケーションの二重起動防止クラス"""
    def __init__(self, app_name="db_monitor_app"):
        self.app_name = app_name
        self.lock_file_path = os.path.join(tempfile.gettempdir(), f"{app_name}.lock")
        self.lock_file = None
        
    def acquire_lock(self) -> bool:
        """ロックを取得"""
        try:
            # ロックファイルが既に存在するかチェック
            if os.path.exists(self.lock_file_path):
                # ファイル内のPIDを確認
                try:
                    with open(self.lock_file_path, 'r') as f:
                        pid = int(f.read().strip())
                    
                    # プロセスが実際に動いているかチェック
                    if self._is_process_running(pid):
                        return False  # 別のインスタンスが動作中
                    else:
                        # プロセスが終了しているので古いロックファイルを削除
                        os.remove(self.lock_file_path)
                except (ValueError, IOError):
                    # 不正なロックファイルは削除
                    try:
                        os.remove(self.lock_file_path)
                    except:
                        pass
            
            # 新しいロックファイルを作成
            with open(self.lock_file_path, 'w') as f:
                f.write(str(os.getpid()))
            
            return True
            
        except Exception as e:
            print(f"ロック取得エラー: {e}")
            return False
    
    def release_lock(self):
        """ロックを解放"""
        try:
            if os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
        except Exception as e:
            print(f"ロック解放エラー: {e}")
    
    def _is_process_running(self, pid: int) -> bool:
        """指定されたPIDのプロセスが動作中かチェック"""
        try:
            if sys.platform == "win32":
                import subprocess
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                       capture_output=True, text=True)
                return str(pid) in result.stdout
            else:
                # Unix系システム
                os.kill(pid, 0)
                return True
        except (OSError, subprocess.SubprocessError):
            return False

class MainWindow:
    def __init__(self):
        # 二重起動チェック
        self.app_lock = ApplicationLock("db_monitor_app")
        if not self.app_lock.acquire_lock():
            messagebox.showerror(
                "起動エラー", 
                "アプリケーションは既に起動しています。\n"
                "複数のインスタンスを同時に実行することはできません。"
            )
            logger.error('duplication check failed')
            sys.exit(1)

        logger.info('started')
        
        self.root = tk.Tk()
        self.config = Config()
        self.convert_old_settings()
        self.config.save_config()
        self.start_time = datetime.datetime.now()
        self.play_st    = None
        
        # スレッド管理
        self.is_running = True
        self.db_monitoring_thread = None
        self.named_pipe_thread = None
        self.screen_monitoring_thread = None
        self.named_pipe_receiver = None
        self.use_named_pipe = False
        self.nexus_calculator = NexusCalculator()
        self.nexus_skill_update_running = False
        self.nexus_skill_update_pending = False
        self.nexus_skill_update_lock = threading.Lock()
        
        # 監視データ
        self.file_exists = False
        self.current_game_state = None  # None, "select", "play", "result"
        self.current_song_data = {}
        self.play_end_metrics_received_for_current_play = False
        
        # OBS WebSocket管理クラス初期化
        self.obs_manager = OBSWebSocketManager(status_callback=self.on_obs_status_changed)
        self.obs_manager.set_config(self.config)

        # データアクセス用クラス初期化
        self.database_accessor = DataBaseAccessor()
        self.init_named_pipe_receiver()
        self.database_accessor.set_config(self.config, reload_db=not self.use_named_pipe)
        # self.database_accessor.read_old_results()
        self.database_accessor.manage_results.write_history_xml()
        self.database_accessor.manage_results.write_updates_xml()
        self.write_current_song_history({})
        
        self.setup_ui()
        self.load_cached_nexus_skill_to_gui()
        self.set_embedded_icon()
        self.restore_window_position()
        self.start_all_threads()
        self.update_display()
        self.check_updates()
        self.update_db_status()
        self.root.after(500, self.request_nexus_skill_update)
        
        # WebSocket自動接続開始
        if self.config.enable_websocket:
            self.obs_manager.start_auto_reconnect()
            for i in range(20):
                if self.obs_manager.is_connected:
                    self.execute_obs_trigger("app_start")
                    break
                time.sleep(0.5)
        
    def get_latest_version(self):
        """GitHubから最新版のバージョンを取得する。

        Returns:
            str: バージョン番号
        """
        ret = None
        url = 'https://github.com/dj-kata/oraja_helper/tags'
        r = requests.get(url)
        soup = BeautifulSoup(r.text,features="html.parser")
        for tag in soup.find_all('a'):
            if 'releases/tag/v.' in tag['href']:
                ret = tag['href'].split('/')[-1]
                break # 1番上が最新なので即break
        return ret

    def check_updates(self, always_disp_dialog=False):
        ver = self.get_latest_version()
        if (ver != SWVER) and (ver is not None):
            logger.info(f'現在のバージョン: {SWVER}, 最新版:{ver}')
            ans = tk.messagebox.askquestion('バージョン更新',f'アップデートが見つかりました。\n\n{SWVER} -> {ver}\n\nアプリを終了して更新します。', icon='warning')
            if ans == "yes":
                if os.path.exists('update.exe'):
                    logger.info('アップデート確認のため終了します')
                    res = subprocess.Popen('update.exe')
                    self.on_closing()
                else:
                    raise ValueError("update.exeがありません")
        else:
            logger.info(f'お使いのバージョンは最新です({SWVER})')
            if always_disp_dialog:
                messagebox.showinfo("oraja_helper", f'お使いのバージョンは最新です({SWVER})')

        # アプリ起動時のOBS制御実行
    def get_resource_path(self, relative_path):
        """埋め込みリソースのパスを取得"""
        try:
            # PyInstaller実行時
            base_path = sys._MEIPASS
        except AttributeError:
            # 開発時
            base_path = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base_path, relative_path)

    def set_embedded_icon(self):
        """埋め込まれたアイコンを設定"""
        try:
            # 埋め込まれたアイコンのパスを取得
            icon_path = self.get_resource_path("assets/icon.ico")
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(default=icon_path)
                print(f"埋め込みアイコンを設定: {icon_path}")
            else:
                # フォールバック
                self.try_alternative_icons()
        except Exception as e:
            print(f"アイコン設定エラー: {e}")    

    def convert_old_settings(self):
        """1.16以前のpkl形式の設定がある場合はconvert
        """
        data = convert_with_dummy_class('settings.pkl')
        if data:
            ret = messagebox.askyesno('確認', '前のバージョンの設定(settings.pkl)を変換しますか？\n変換後に元の設定ファイルは削除されます。\n\n※注意:OBS制御設定は引き継げません。お手数ですが再設定をお願いします。')
            if ret:
                self.config.main_window_x = data.get('lx', self.config.main_window_x)
                self.config.main_window_y = data.get('ly', self.config.main_window_y)
                self.config.oraja_path = data.get('dir_oraja', self.config.oraja_path)
                self.config.player_path = data.get('dir_player', self.config.player_path)
                self.config.enable_autotweet = data.get('tweet_on_exit', self.config.enable_autotweet)
                self.config.monitor_source_name = data.get('obs_source', self.config.monitor_source_name)
                self.config.websocket_host = data.get('host', self.config.websocket_host)
                self.config.websocket_port = data.get('port', self.config.websocket_port)
                self.config.websocket_password = data.get('passwd', self.config.websocket_password)

                # pkl削除
                os.remove('settings.pkl')
                logger.info('convert succeeded. settings.pkl was removed.')

    def setup_ui(self):
        """UIの初期設定"""
        self.root.title(f"oraja_helper")
        self.root.geometry("550x380")
        self.root.minsize(550,380)    # 最小サイズも調整
        
        # メニューバー
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 設定メニュー
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=settings_menu)
        settings_menu.add_command(label="settings", command=self.open_settings)
        settings_menu.add_command(label="OBS制御設定", command=self.open_obs_control)
        settings_menu.add_command(label="アップデートを確認", command=self.check_updates)
        tweet_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='Tweet', menu=tweet_menu)
        tweet_menu.add_command(label='daily', command=self.database_accessor.manage_results.tweet_summary)
        tweet_menu.add_command(label='history', command=self.database_accessor.manage_results.tweet_history)
        nexus_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label='BMS Nexus', menu=nexus_menu)
        nexus_menu.add_command(label='リコメンド計算', command=self.calculate_nexus_recommendations_async)
        
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 経過時間表示
        ttk.Label(main_frame, text="uptime:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.elapsed_time_var = tk.StringVar(value="00:00:00")
        ttk.Label(main_frame, textvariable=self.elapsed_time_var, font=("Arial", 12, "bold")).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 監視対象フォルダ表示
        ttk.Label(main_frame, text="beatoraja path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.oraja_path_var = tk.StringVar()
        ttk.Label(main_frame, textvariable=self.oraja_path_var, wraplength=300).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ファイル存在状況表示
        ttk.Label(main_frame, text="db state:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.file_status_var = tk.StringVar(value="確認中...")
        self.file_status_label = ttk.Label(main_frame, textvariable=self.file_status_var)
        self.file_status_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ゲーム状態表示
        ttk.Label(main_frame, text="oraja state:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.game_state_var = tk.StringVar(value="未判定")
        self.game_state_label = ttk.Label(main_frame, textvariable=self.game_state_var, font=("Arial", 12, "bold"))
        self.game_state_label.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # OBS WebSocket連携状況表示
        ttk.Label(main_frame, text="OBS WebSocket:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.obs_status_var = tk.StringVar()
        self.obs_status_label = ttk.Label(main_frame, textvariable=self.obs_status_var, wraplength=300)
        self.obs_status_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # プレイ曲数
        ttk.Label(main_frame, text="playcount:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.playcount_var = tk.StringVar(value='0')
        self.playcount_label = ttk.Label(main_frame, textvariable=self.playcount_var, font=("Arial", 12, "bold"))
        self.playcount_label.grid(row=5, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ノーツ数
        ttk.Label(main_frame, text="notes:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.notes_var = tk.StringVar(value='0')
        self.notes_label = ttk.Label(main_frame, textvariable=self.notes_var, font=("Arial", 12, "bold"))
        self.notes_label.grid(row=6, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # スコアレート
        ttk.Label(main_frame, text="score rate:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.score_rate_var = tk.StringVar(value='0.00%')
        self.score_rate_label = ttk.Label(main_frame, textvariable=self.score_rate_var, font=("Arial", 12, "bold"))
        self.score_rate_label.grid(row=7, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # BMS Nexus skill
        ttk.Label(main_frame, text="nexus skill:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.nexus_skill_var = tk.StringVar(value='-')
        self.nexus_skill_label = ttk.Label(main_frame, textvariable=self.nexus_skill_var, font=("Arial", 12, "bold"))
        self.nexus_skill_label.grid(row=8, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ステータスバー
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, padx=5, pady=2)
        
        # グリッドの重み設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        self.update_config_display()

    def calculate_nexus_recommendations_async(self):
        self.status_var.set("BMS Nexusリコメンドを計算中...")
        thread = threading.Thread(target=self.calculate_nexus_recommendations_worker, daemon=True)
        thread.start()

    def calculate_nexus_recommendations_worker(self):
        try:
            if not self.database_accessor.is_valid():
                raise FileNotFoundError("beatorajaのDBファイルが見つかりません。設定を確認してください。")

            self.database_accessor.reload_db()
            result = self.nexus_calculator.calculate_from_database_accessor(self.database_accessor)
            output_path = "nexus_recommendations.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            self.post_to_gui(lambda: self.on_nexus_recommendations_done(result, output_path))
        except Exception as e:
            logger.error(traceback.format_exc())
            self.post_to_gui(lambda error=e: self.on_nexus_recommendations_failed(error))

    def on_nexus_recommendations_done(self, result, output_path):
        user_skill = result.get("user_skill", 0.0)
        recommend = result.get("recommend", [])
        top_lines = []
        for row in recommend[:5]:
            top_lines.append(
                f'{row["table"]} {row["title"]}: {row["recommend_percent"]:.1f}%'
            )
        top_text = "\n".join(top_lines) if top_lines else "リコメンド対象がありません。"
        self.status_var.set(
            f'BMS Nexus計算完了: skill {user_skill:.2f}, recommend {len(recommend)}件'
        )
        if user_skill != 0:
            self.nexus_skill_var.set(self.format_nexus_skill(user_skill))
            self.database_accessor.manage_results.nexus_skill = user_skill
            self.nexus_calculator.save_cached_user_skill(user_skill)
        messagebox.showinfo(
            "BMS Nexus",
            f"総合リコメンド値: {user_skill:.2f}\n"
            f"譜面別リコメンド: {len(recommend)}件\n\n"
            f"{top_text}\n\n"
            f"出力: {output_path}",
        )

    def on_nexus_recommendations_failed(self, error):
        self.status_var.set("BMS Nexus計算失敗")
        messagebox.showerror("BMS Nexus", f"リコメンド計算に失敗しました。\n\n{error}")

    def request_nexus_skill_update(self):
        with self.nexus_skill_update_lock:
            if self.nexus_skill_update_running:
                self.nexus_skill_update_pending = True
                return
            self.nexus_skill_update_running = True

        thread = threading.Thread(target=self.update_nexus_skill_worker, daemon=True)
        thread.start()

    def load_cached_nexus_skill_to_gui(self):
        user_skill = self.nexus_calculator.load_cached_user_skill()
        if user_skill is not None and user_skill != 0:
            self.nexus_skill_var.set(self.format_nexus_skill(user_skill))
            self.database_accessor.manage_results.nexus_skill = user_skill

    def update_nexus_skill_worker(self):
        try:
            if not self.database_accessor.is_valid():
                raise FileNotFoundError("beatorajaのDBファイルが見つかりません。")
            try:
                updated = self.nexus_calculator.update_ir_data_from_remote_once()
                if updated:
                    logger.info("BMS Nexus ir_data.json updated from remote.")
            except Exception:
                logger.error(traceback.format_exc())
            user_skill = self.nexus_calculator.calculate_user_skill_from_database_accessor(
                self.database_accessor
            )
            self.post_to_gui(lambda: self.on_nexus_skill_update_done(user_skill))
        except Exception as e:
            logger.error(traceback.format_exc())
            self.post_to_gui(lambda error=e: self.on_nexus_skill_update_failed(error))

    def post_to_gui(self, callback):
        try:
            self.root.after(0, callback)
        except RuntimeError:
            logger.warning("Tk mainloop is not available; skipped GUI callback.")

    def finish_nexus_skill_update(self):
        with self.nexus_skill_update_lock:
            rerun = self.nexus_skill_update_pending
            self.nexus_skill_update_running = False
            self.nexus_skill_update_pending = False

        if rerun:
            self.request_nexus_skill_update()

    def on_nexus_skill_update_done(self, user_skill):
        if user_skill != 0:
            self.nexus_skill_var.set(self.format_nexus_skill(user_skill))
            self.database_accessor.manage_results.nexus_skill = user_skill
            self.nexus_calculator.save_cached_user_skill(user_skill)
            if self.current_song_data:
                self.write_current_song_history(self.current_song_data)
        self.finish_nexus_skill_update()

    def on_nexus_skill_update_failed(self, error):
        logger.warning(f"BMS Nexus skill update failed: {error}")
        self.finish_nexus_skill_update()

    def format_nexus_skill(self, user_skill):
        return f"★{user_skill:.2f}"
    
    def start_all_threads(self):
        """全スレッドを開始"""
        if self.use_named_pipe:
            self.start_named_pipe_monitoring()
        else:
            self.start_db_monitoring()
        self.start_screen_monitoring()

    def init_named_pipe_receiver(self):
        """lr2orajaからのnamed pipe受信が使えるか確認"""
        try:
            self.named_pipe_receiver = NamedPipeLineReceiver("oraja_helper")
            self.use_named_pipe = self.named_pipe_receiver.is_available()
            if self.use_named_pipe:
                logger.info("named pipe受信を使用します")
        except Exception as e:
            self.named_pipe_receiver = None
            self.use_named_pipe = False
            logger.warning(f"named pipe受信初期化失敗。DB監視にフォールバックします: {e}")

    def start_named_pipe_monitoring(self):
        """named pipe受信スレッドを開始"""
        if self.named_pipe_thread is None or not self.named_pipe_thread.is_alive():
            self.named_pipe_thread = threading.Thread(target=self.named_pipe_worker, daemon=True)
            self.named_pipe_thread.start()
            print("named pipe受信スレッドを開始しました")

    def named_pipe_worker(self):
        """lr2orajaからのJSON Linesを受信するワーカースレッド"""
        print("named pipe受信スレッド開始")
        while self.is_running:
            try:
                line = self.named_pipe_receiver.read_line()
                if line:
                    self.dump_named_pipe_receive(line)
                    logger.info(f"named pipe受信: {line}")
                    self.handle_oraja_helper_event(self.normalize_pipe_data(json.loads(line)))
            except Exception as e:
                logger.error(traceback.format_exc())
                print(f"named pipe受信エラー: {e}")
                time.sleep(1)
        print("named pipe受信スレッド終了")

    def dump_named_pipe_receive(self, line):
        """named pipeで受けた生データを切り分け用に保存"""
        try:
            os.makedirs("log", exist_ok=True)
            payload = {
                "time": datetime.datetime.now().isoformat(),
                "line": line,
            }
            with open(os.path.join("log", "oraja_helper_pipe_receive.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            logger.error(traceback.format_exc())

    def handle_oraja_helper_event(self, data):
        """lr2orajaから受け取ったイベントを処理"""
        event = data.get("event")
        scene = data.get("scene")
        if scene in ("select", "play", "result"):
            self.apply_game_state(scene, "named pipe")

        if event == "song_result":
            result = self.create_result_from_pipe_event(data)
            if result and result.is_valid():
                self.populate_previous_record(result)
                self.database_accessor.manage_results.add_result(result)
                self.database_accessor.manage_results.update_stats()
                self.database_accessor.manage_results.save()
                self.database_accessor.manage_results.write_history_xml()
                self.database_accessor.manage_results.write_updates_xml()
                self.post_to_gui(self.update_stats_gui)
                self.database_accessor.reload_db()
                self.request_nexus_skill_update()

        if event == "song_play_end" and data.get("playEndMetrics"):
            self.apply_play_end_metrics(data)

        if scene in ("select", "play", "result"):
            self.write_current_song_history(data)

    def normalize_pipe_data(self, value):
        """libGDX Jsonのclass/value形式を通常のJSON値へ戻す"""
        if isinstance(value, dict):
            if set(value.keys()) == {"class", "value"}:
                return self.normalize_pipe_data(value.get("value"))
            return {k: self.normalize_pipe_data(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.normalize_pipe_data(v) for v in value]
        return value

    def create_result_from_pipe_event(self, data):
        """named pipeのsong_resultイベントをOneResultへ変換"""
        judges = data.get("judges", {})
        judge = [
            int(judges.get("epg", 0)) + int(judges.get("lpg", 0)),
            int(judges.get("egr", 0)) + int(judges.get("lgr", 0)),
            int(judges.get("egd", 0)) + int(judges.get("lgd", 0)),
            int(judges.get("ebd", 0)) + int(judges.get("lbd", 0)),
            int(judges.get("epr", 0)) + int(judges.get("lpr", 0)),
            int(judges.get("ems", 0)) + int(judges.get("lms", 0)),
        ]
        sha256 = data.get("sha256") or ""
        md5 = data.get("md5") or ""
        notes = sum(judge[:5])
        difficulties = self.search_difficulties_from_hashes(sha256, md5) or [""]
        return OneResult(
            title=data.get("title") or "",
            difficulties=difficulties,
            score=int(data.get("score", 0)),
            score_rate=f"{float(data.get('scoreRate', 0.0)):.2f}",
            lamp=self.clear_lamp_id_from_event(data),
            bp=int(data.get("missCount", 0)),
            judge=judge,
            sha256=sha256,
            date=int(datetime.datetime.now().timestamp()),
            notes=notes,
            option=self.format_option(data),
        )

    def populate_previous_record(self, result):
        """named pipeの正式リザルトに前回自己ベストを補完する"""
        previous_results = [
            r for r in self.database_accessor.manage_results.all_results
            if r.is_valid() and r.sha256 == result.sha256 and int(r.lamp or 0) > 0
        ]
        if not previous_results:
            return

        result.pre_score = max(int(r.score or 0) for r in previous_results)
        result.pre_lamp = max(int(r.lamp or 0) for r in previous_results)
        result.pre_bp = min(int(r.bp or 999999) for r in previous_results)

    def apply_play_end_metrics(self, data):
        """named pipeのプレー終了メトリクスを統計へ反映"""
        try:
            judge = self.play_end_judge_from_event(data)
            played_notes = sum(judge[:5]) if judge is not None else int(data.get("playedNotes", 0))
            elapsed_seconds = int(data.get("elapsedSeconds", 0))
        except (TypeError, ValueError):
            logger.warning(f"invalid play end metrics: {data}")
            return

        self.play_end_metrics_received_for_current_play = True
        self.play_st = None
        self.database_accessor.manage_results.add_play_end_metrics(
            played_notes,
            elapsed_seconds,
            int(datetime.datetime.now().timestamp()),
            judge,
        )
        self.database_accessor.manage_results.write_history_xml()
        self.database_accessor.manage_results.write_updates_xml()
        self.post_to_gui(self.update_stats_gui)
        logger.info(
            f"play end metrics applied: notes={played_notes}, elapsedSeconds={elapsed_seconds}, "
            f"quickRetry={data.get('quickRetry')}"
        )

    def play_end_judge_from_event(self, data):
        """song_play_endの判定内訳をリザルトと同じ形式へ変換する"""
        judges = data.get("judges")
        if isinstance(judges, dict):
            return [
                int(judges.get("epg", 0)) + int(judges.get("lpg", 0)),
                int(judges.get("egr", 0)) + int(judges.get("lgr", 0)),
                int(judges.get("egd", 0)) + int(judges.get("lgd", 0)),
                int(judges.get("ebd", 0)) + int(judges.get("lbd", 0)),
                int(judges.get("epr", 0)) + int(judges.get("lpr", 0)),
                int(judges.get("ems", 0)) + int(judges.get("lms", 0)),
            ]
        return None

    def search_difficulties_from_hashes(self, *hashes):
        difficulties = []
        seen = set()
        for hash_value in hashes:
            for difficulty in self.database_accessor.difftable.search_from_hash(hash_value):
                if difficulty not in seen:
                    difficulties.append(difficulty)
                    seen.add(difficulty)
        return difficulties

    def clear_lamp_id_from_event(self, data):
        """clearLampIdが無い場合もclearLamp文字列からランプIDを補完する"""
        try:
            return int(data.get("clearLampId", 0) or 0)
        except (TypeError, ValueError):
            pass

        lamp_name = str(data.get("clearLamp") or "").strip().lower().replace(" ", "").replace("-", "")
        lamp_ids = {
            "failed": 1,
            "assistclear": 3,
            "easyclear": 4,
            "easy": 4,
            "clear": 5,
            "normalclear": 5,
            "hardclear": 6,
            "hard": 6,
            "exhardclear": 7,
            "exhard": 7,
            "fullcombo": 8,
            "fullcomboclear": 8,
            "perfect": 9,
            "max": 10,
        }
        return lamp_ids.get(lamp_name, 0)

    def format_option(self, data):
        """表示・保存用のオプション文字列を作る"""
        option = data.get("option") or "?"
        placement = data.get("randomPlacement") or ""
        if placement:
            option = f"{option} {placement}"

        option2p = data.get("option2P") or ""
        placement2p = data.get("randomPlacement2P") or ""
        if option2p:
            if placement2p:
                option2p = f"{option2p} {placement2p}"
            option = f"{option} / {option2p}"

        return option

    def write_current_song_history(self, data, outfile='history_cursong.json'):
        """現在曲と、その曲のoraja_helper内プレーログ履歴を書き出す"""
        data = data or {}
        self.current_song_data = data
        sha256 = data.get("sha256") or ""
        md5 = data.get("md5") or ""
        difficulties = self.search_difficulties_from_hashes(sha256, md5)
        results = [
            r for r in self.database_accessor.manage_results.all_results
            if r.is_valid() and r.sha256 == sha256 and int(r.lamp or 0) > 0
        ]
        results.sort(reverse=True)

        lamps = ['', '', '', '', 'E', 'C', 'H', 'EXH', 'FC', 'P', 'MAX']
        history = []
        for r in results[:20]:
            lamp = int(r.lamp) if r.lamp is not None else 0
            history.append({
                "title": r.title or "",
                "difficulty": ", ".join(r.difficulties or []),
                "score": int(r.score or 0),
                "scoreRate": float(r.score_rate or 0),
                "lamp": lamps[lamp] if 0 <= lamp < len(lamps) else str(lamp),
                "lampId": lamp,
                "bp": int(r.bp or 0),
                "option": getattr(r, "option", "?") or "?",
                "timestamp": datetime.datetime.fromtimestamp(r.date).strftime("%Y/%m/%d %H:%M:%S") if r.date else "",
            })

        best = self.current_song_best_info(results, lamps)
        nexus = self.current_song_nexus_info(sha256, md5)

        output = {
            "scene": data.get("scene") or "",
            "event": data.get("event") or "",
            "title": data.get("title") or "",
            "artist": data.get("artist") or "",
            "sha256": sha256,
            "md5": md5,
            "difficulty": ", ".join(difficulties),
            "difficulties": difficulties,
            "option": self.format_option(data) if data.get("scene") in ("play", "result") else "",
            "optionRaw": data.get("option") or "",
            "optionId": data.get("optionId", ""),
            "randomPlacement": data.get("randomPlacement") or "",
            "option2PRaw": data.get("option2P") or "",
            "option2PId": data.get("option2PId", ""),
            "randomPlacement2P": data.get("randomPlacement2P") or "",
            "best": best,
            "nexus": nexus,
            "history": history,
        }
        with open(outfile, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        js = "window.__ORAJA_HELPER_CURRENT_SONG__ = " + json.dumps(output, ensure_ascii=False) + ";\n"
        with open(os.path.splitext(outfile)[0] + "_data.js", 'w', encoding='utf-8') as f:
            f.write(js.replace("</script", "<\\/script"))

    def current_song_best_info(self, results, lamps):
        if not results:
            return None

        best_lamp_id = max(int(r.lamp or 0) for r in results)
        best_score_result = max(results, key=lambda r: int(r.score or 0))
        best_bp_result = min(results, key=lambda r: int(r.bp if r.bp is not None else 999999))
        best_score = int(best_score_result.score or 0)
        best_bp = int(best_bp_result.bp if best_bp_result.bp is not None else 0)
        return {
            "lamp": lamps[best_lamp_id] if 0 <= best_lamp_id < len(lamps) else str(best_lamp_id),
            "lampId": best_lamp_id,
            "score": best_score,
            "rate": float(best_score_result.score_rate or 0),
            "bp": best_bp,
            "bestScoreOption": getattr(best_score_result, "option", "?") or "?",
            "bestBpOption": getattr(best_bp_result, "option", "?") or "?",
        }

    def current_song_nexus_info(self, sha256, md5):
        try:
            if not sha256 and not md5:
                return None
            user_skill = self.database_accessor.manage_results.nexus_skill
            if user_skill is None:
                user_skill = self.nexus_calculator.load_cached_user_skill()
                if user_skill is not None and user_skill != 0:
                    self.database_accessor.manage_results.nexus_skill = user_skill
            if not self.nexus_calculator.skill_chart_index:
                self.nexus_calculator.get_skill_chart_index()
            nexus_info = self.nexus_calculator.get_cached_chart_nexus_info(
                user_skill, sha256, md5
            )
            if nexus_info:
                return nexus_info
            return self.nexus_calculator.get_cached_chart_skill_difficulties(sha256, md5)
        except Exception:
            logger.error(traceback.format_exc())
            return None

    def apply_game_state(self, new_state, source):
        """ゲーム状態変更時の共通処理"""
        if new_state == self.current_game_state:
            return

        if self.current_game_state:
            self.execute_obs_trigger(f"{self.current_game_state}_end")

        self.update_playtime(self.current_game_state, new_state)

        if new_state:
            self.execute_obs_trigger(f"{new_state}_start")
            if new_state == "play":
                self.play_end_metrics_received_for_current_play = False

        self.current_game_state = new_state
        self.post_to_gui(self.update_game_state_display)
        print(f"ゲーム状態変化（{source}）: {self.current_game_state}")
    
    def start_db_monitoring(self):
        """ファイル監視スレッドを開始"""
        if self.db_monitoring_thread is None or not self.db_monitoring_thread.is_alive():
            self.db_monitoring_thread = threading.Thread(target=self.db_monitoring_worker, daemon=True)
            self.db_monitoring_thread.start()
            print("ファイル監視スレッドを開始しました")
    
    def start_screen_monitoring(self):
        """画面監視スレッドを開始"""
        if self.screen_monitoring_thread is None or not self.screen_monitoring_thread.is_alive():
            self.screen_monitoring_thread = threading.Thread(target=self.screen_monitoring_worker, daemon=True)
            self.screen_monitoring_thread.start()
            print("画面監視スレッドを開始しました")
    
    def db_monitoring_worker(self):
        """dbfile監視専用ワーカースレッド"""
        print("dbfile監視スレッド開始")
        while self.is_running:
            try:
                if self.database_accessor.is_valid():
                    if self.database_accessor.reload_db():
                        self.update_db_status()
                        self.database_accessor.read_one_result()
                        self.database_accessor.manage_results.update_stats()
                        self.database_accessor.manage_results.save()
                        self.database_accessor.manage_results.write_history_xml()
                        self.database_accessor.manage_results.write_updates_xml()
                        logger.info(f"added! len(all_results):{len(self.database_accessor.manage_results.all_results)}, len(today_results):{len(self.database_accessor.manage_results.today_results)}")
                        self.update_stats_gui()
                        self.request_nexus_skill_update()
                        logger.info(f"added! len(all_results):{len(self.database_accessor.manage_results.all_results)}, len(today_results):{len(self.database_accessor.manage_results.today_results)}")
                    
                else:
                    self.file_exists = False
                
            except Exception as e:
                print(f"ファイル監視エラー: {e}")
                # self.root.after(0, lambda: self.status_var.set(f"ファイル監視エラー: {e}"))
            # 
            time.sleep(1)
        
        print("ファイル監視スレッド終了")
    
    def screen_monitoring_worker(self):
        """画面監視専用ワーカースレッド"""
        print("画面監視スレッド開始")
        while self.is_running:
            try:
                # OBSWebSocket設定がされている場合のみ実行
                if (self.config.enable_websocket and 
                    self.obs_manager.is_connected):
                    
                    # 画像認識が有効な場合：OBSスクリーンショットによる判定
                    if self.config.enable_register_conditions:
                        screenshot_data = self.get_obs_screenshot()
                        if screenshot_data:
                            self.detect_game_state_from_screenshot(screenshot_data)
                    
                    # 画像認識が無効な場合：ファイルベースの判定
                    else:
                        self.detect_game_state_from_file()
                
                # 1秒間隔で実行
                time.sleep(1)
                
            except Exception as e:
                print(f"画面監視エラー: {e}")
                # エラー時は少し長めに待機
                time.sleep(5)
        
        print("画面監視スレッド終了")
    
    def get_obs_screenshot(self):
        """OBSからスクリーンショットを取得"""
        if not PIL_AVAILABLE:
            return None
            
        try:
            # OBSの現在のプログラム出力のスクリーンショットを取得
            result = self.obs_manager.get_screenshot()
            
            if result and hasattr(result, 'image_data'):
                # Base64デコードして画像データを返す
                image_data_str = result.image_data
                if image_data_str.startswith('data:image/'):
                    image_data_str = image_data_str.split(',')[1]
                
                image_data = base64.b64decode(image_data_str)
                image = Image.open(io.BytesIO(image_data))
                return image
            
        except Exception as e:
            print(f"OBSスクリーンショット取得エラー: {e}")
            
        return None

    def update_playtime(self, old_state, new_state):
        """プレイ時間を更新する共通メソッド"""
        current_time = datetime.datetime.now()
        
        if new_state == 'play':
            self.play_st = current_time
        elif old_state == 'play' and self.play_st is not None:
            if self.play_end_metrics_received_for_current_play:
                self.play_st = None
                return
            # プレイ終了時に時間を加算
            play_duration = current_time - self.play_st
            self.database_accessor.manage_results.playtime += play_duration
            print(f"プレイ時間を追加: {play_duration}, 累計: {self.database_accessor.manage_results.playtime}")
            self.play_st = None

    def detect_game_state_from_screenshot(self, screenshot_image):
        """スクリーンショットからゲーム状態を判定"""
        if not IMAGEHASH_AVAILABLE:
            return
            
        try:
            # 画像認識データを読み込み
            recognition_data = ImageRecognitionData()
            
            new_state = None
            detected_states = []
            
            # 各画面タイプの判定を実行
            for screen_type in ["select", "play", "result"]:
                condition = recognition_data.get_condition(screen_type)
                if condition and self.check_screen_match(screenshot_image, condition):
                    detected_states.append(screen_type)
            
            # 複数の状態が検出された場合は優先度で決定（プレー > リザルト > 選曲）
            if "play" in detected_states:
                new_state = "play"
            elif "result" in detected_states:
                new_state = "result"
            elif "select" in detected_states:
                new_state = "select"
            
            self.apply_game_state(new_state, "画像認識")
                
        except Exception as e:
            print(f"ゲーム状態判定エラー: {e}")
    
    def check_screen_match(self, screenshot_image, condition):
        """スクリーンショットが指定された画面条件にマッチするかチェック"""
        try:
            # 座標情報を取得
            coords = condition.get("coordinates", {})
            x1, y1 = coords.get("x1", 0), coords.get("y1", 0)
            x2, y2 = coords.get("x2", 100), coords.get("y2", 100)
            
            # 座標を正規化
            left, top = min(x1, x2), min(y1, y2)
            right, bottom = max(x1, x2), max(y1, y2)
            
            # スクリーンショットのサイズチェック
            img_width, img_height = screenshot_image.size
            if right > img_width or bottom > img_height:
                return False
            
            # スクリーンショットから該当範囲を切り出し
            cropped = screenshot_image.crop((left, top, right, bottom))
            
            # ハッシュを計算
            current_hash = imagehash.average_hash(cropped)
            
            # 設定されたハッシュと比較
            reference_hash = imagehash.hex_to_hash(condition.get("hash", ""))
            threshold = condition.get("threshold", 10)
            
            # ハッシュの差分を計算
            hash_diff = current_hash - reference_hash
            
            # しきい値以下なら一致とみなす
            return hash_diff <= threshold
            
        except Exception as e:
            print(f"画面マッチング判定エラー: {e}")
            return False
    
    def detect_game_state_from_file(self):
        """ファイルベースのゲーム状態判定"""
        try:
            target_file = self.config.get_target_file_path()
            
            # ファイルが存在する場合のみ判定
            if target_file and self.file_exists:
                # ファイル名や内容から状態を判定
                if "select" in target_file.lower():
                    new_state = "select"
                elif "play" in target_file.lower():
                    new_state = "play"  
                elif "result" in target_file.lower():
                    new_state = "result"
                else:
                    new_state = None
                
                self.apply_game_state(new_state, "ファイルベース")
                    
        except Exception as e:
            print(f"ファイルベースゲーム状態判定エラー: {e}")
    
    def update_stats_gui(self):
        """db監視スレッドから呼び出す最低限のGUI更新メソッド
        """
        self.oraja_path_var.set(self.config.oraja_path or "未設定")
        self.playcount_var.set(str(self.database_accessor.manage_results.playcount))
        self.notes_var.set(str(self.database_accessor.manage_results.notes))
        self.score_rate_var.set(f"{self.database_accessor.manage_results.score_rate:.2f}%")

    def update_config_display(self):
        """設定情報の表示を更新"""
        self.oraja_path_var.set(self.config.oraja_path or "未設定")
        
        # 設定の更新
        self.config.load_config()
        self.obs_manager.set_config(self.config)
        logger.info(f"added! len(all_results):{len(self.database_accessor.manage_results.all_results)}, len(today_results):{len(self.database_accessor.manage_results.today_results)}")
        self.database_accessor.set_config(self.config, reload_db=not self.use_named_pipe)
        logger.info(f"added! len(all_results):{len(self.database_accessor.manage_results.all_results)}, len(today_results):{len(self.database_accessor.manage_results.today_results)}")
        self.update_db_status()
        self.root.after(100, self.request_nexus_skill_update)

        # 設定画面で更新される可能性があるため、DataBaseAccessorをリロードしておく
        self.database_accessor.manage_results.load()
        self.database_accessor.manage_results.write_history_xml()
        self.database_accessor.manage_results.write_updates_xml()

        self.playcount_var.set(str(self.database_accessor.manage_results.playcount))
        self.notes_var.set(str(self.database_accessor.manage_results.notes))
        self.score_rate_var.set(f"{self.database_accessor.manage_results.score_rate:.2f}%")
        
        # 現在のOBSステータスを取得して表示
        status_message, is_connected = self.obs_manager.get_status()
        self.obs_status_var.set(status_message)
        
        # 接続状態に応じて色を変更
        if is_connected:
            self.obs_status_label.config(foreground="green")
        elif "無効" in status_message or "インストール" in status_message:
            self.obs_status_label.config(foreground="gray")
        else:
            self.obs_status_label.config(foreground="red")
        
        # WebSocket連携が有効になった場合は自動接続を開始
        if self.config.enable_websocket and not self.obs_manager.should_reconnect:
            self.obs_manager.start_auto_reconnect()
        elif not self.config.enable_websocket:
            self.obs_manager.stop_auto_reconnect()
            self.obs_manager.disconnect()
    
    def update_db_status(self):
        """dbfile状態の表示を更新"""
        try:
            if self.use_named_pipe:
                self.file_status_var.set("PIPE")
                self.file_status_label.config(foreground="green")
                return

            if self.database_accessor.is_valid():
                self.file_status_var.set("OK")
                self.file_status_label.config(foreground="blue")
            else:
                self.file_status_var.set("NG")
                self.file_status_label.config(foreground="red")
        except Exception:
            pass
    
    def update_game_state_display(self):
        """ゲーム状態表示を更新"""
        state_names = {
            "select": "選曲画面",
            "play": "プレー画面",
            "result": "リザルト画面",
            None: "未判定"
        }
        
        state_text = state_names.get(self.current_game_state, "未判定")
        self.game_state_var.set(state_text)
        
        # 状態に応じて色を変更
        if self.current_game_state == "play":
            self.game_state_label.config(foreground="pink")
        elif self.current_game_state == "result":
            self.game_state_label.config(foreground="purple")
        elif self.current_game_state == "select":
            self.game_state_label.config(foreground="green")
        else:
            self.game_state_label.config(foreground="gray")
    
    def on_obs_status_changed(self, status_message: str, is_connected: bool):
        """OBS WebSocket接続状態変更時のコールバック"""
        def update_ui():
            self.obs_status_var.set(status_message)
            
            # 接続状態に応じて色を変更
            if is_connected:
                self.obs_status_label.config(foreground="green")
                self.status_var.set("OBS WebSocket接続完了")
            else:
                # 詳細な状態による色分け
                if "無効" in status_message or "インストール" in status_message:
                    self.obs_status_label.config(foreground="gray")
                    self.status_var.set("OBS WebSocket機能無効")
                elif "接続中" in status_message:
                    self.obs_status_label.config(foreground="orange")
                    self.status_var.set("OBS WebSocket接続試行中...")
                elif "タイムアウト" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続タイムアウト")
                elif "接続拒否" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続拒否 (OBS未起動?)")
                elif "失われました" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続が失われました")
                elif "エラー" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続エラー")
                else:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket切断")
        
        # メインスレッドでUI更新を実行
        self.post_to_gui(update_ui)
    
    def restore_window_position(self):
        """ウィンドウ位置を復元"""
        try:
            # 設定されたウィンドウ位置を取得
            x = self.config.main_window_x
            y = self.config.main_window_y
            width = self.config.main_window_width
            height = self.config.main_window_height
            
            # ウィンドウサイズと位置を設定
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            
        except Exception as e:
            print(f"ウィンドウ位置復元エラー: {e}")
            # エラーの場合はデフォルト位置
            self.root.geometry("550x350+100+100")
    
    def save_window_position(self):
        """現在のウィンドウ位置を保存"""
        try:
            # ウィンドウが最小化されている場合は保存しない
            if self.root.state() == 'iconic':
                return
            
            # 現在の位置とサイズを取得
            geometry = self.root.geometry()
            # 形式: "widthxheight+x+y"
            size_pos = geometry.split('+')
            width_height = size_pos[0].split('x')
            
            width = int(width_height[0])
            height = int(width_height[1])
            x = int(size_pos[1])
            y = int(size_pos[2])
            
            # 設定に保存
            self.config.save_window_position(x, y, width, height)
            
        except Exception as e:
            print(f"ウィンドウ位置保存エラー: {e}")
    
    def update_display(self):
        """表示の定期更新"""
        # 経過時間の更新
        elapsed = datetime.datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # 1秒後に再実行
        self.root.after(1000, self.update_display)

    def execute_obs_trigger(self, trigger: str):
        """OBS制御トリガーを実行"""
        try:
            # OBS制御ウィンドウが作成されていなくても設定は実行できるよう、
            # 直接設定データを読み込んで実行
            from obs_control import OBSControlData
            
            control_data = OBSControlData()
            control_data.set_config(self.config)
            settings = control_data.get_settings_by_trigger(trigger)
            
            if not settings:
                return  # 該当する設定がない場合は何もしない
            
            if not self.obs_manager.is_connected:
                print(f"OBS未接続のため、トリガー '{trigger}' をスキップ")
                return
            
            for setting in settings:
                try:
                    action = setting["action"]
                    
                    if action == "switch_scene":
                        target_scene = setting.get("target_scene")
                        if target_scene:
                            self.obs_manager.change_scene(target_scene)
                            print(f"シーンを切り替え: {target_scene}")
                    
                    elif action == "show_source":
                        scene_name = setting.get("scene_name")
                        source_name = setting.get("source_name")
                        if scene_name and source_name:
                            scene_item_id = self._get_scene_item_id(scene_name, source_name)
                            if scene_item_id:
                                self.obs_manager.enable_source(scene_name, scene_item_id)
                                print(f"ソースを表示: {scene_name}/{source_name} (id:{scene_item_id})")
                    
                    elif action == "hide_source":
                        scene_name = setting.get("scene_name")
                        source_name = setting.get("source_name")
                        if scene_name and source_name:
                            scene_item_id = self._get_scene_item_id(scene_name, source_name)
                            if scene_item_id:
                                self.obs_manager.send_command("set_scene_item_enabled",
                                                            scene_name=scene_name,
                                                            scene_item_id=scene_item_id,
                                                            scene_item_enabled=False)
                                self.obs_manager.disable_source(scene_name, scene_item_id)
                                print(f"ソースを非表示: {scene_name}/{source_name} (id:{scene_item_id})")
                                
                except Exception as e:
                    print(f"制御実行エラー (trigger: {trigger}, setting: {setting}): {e}")
                    
        except Exception as e:
            print(traceback.format_exc())
            print(f"トリガー実行エラー ({trigger}): {e}")
    
    def _get_scene_item_id(self, scene_name: str, source_name: str) -> int:
        """シーンアイテムIDを取得"""
        try:
            result = self.obs_manager.send_command("get_scene_item_id", 
                                                 scene_name=scene_name, 
                                                 source_name=source_name)
            return result.scene_item_id if result else 0
        except Exception as e:
            print(f"シーンアイテムID取得エラー: {e}")
            return 0
    
    def open_settings(self):
        """設定ダイアログを開く"""
        self.database_accessor.manage_results.save()
        settings_window = SettingsWindow(self.root, self.config, self.update_config_display)
    
    def open_obs_control(self):
        """OBS制御設定ダイアログを開く"""
        if not self.obs_manager.is_connected:
            messagebox.showwarning("OBS未接続", 
                                 "OBS制御設定を開くには、まずOBSに接続してください。\n"
                                 "「設定」→「基本設定」からWebSocket接続を有効にしてください。")
            return
        
        try:
            self.database_accessor.manage_results.save()
            obs_control = OBSControlWindow(self.root, self.obs_manager, self.config, self.update_config_display)
        except Exception as e:
            messagebox.showerror("エラー", f"OBS制御設定ウィンドウの起動に失敗しました。\n{str(e)}")
    
    def on_closing(self):
        """アプリケーション終了時の処理"""
        print("アプリケーション終了処理開始")

        # xml出力
        self.database_accessor.manage_results.save()
        self.database_accessor.manage_results.write_history_xml()
        self.database_accessor.manage_results.write_updates_xml()

        # tweet
        if self.config.enable_autotweet:
            self.sync_nexus_skill_to_manage_results()
            self.database_accessor.manage_results.tweet_summary()
        
        # ウィンドウ位置を保存
        self.save_window_position()
        
        # アプリ終了時のOBS制御実行
        self.execute_obs_trigger("app_end")
        
        # スレッド停止フラグを設定
        self.is_running = False
        
        # OBS WebSocket接続を停止
        if hasattr(self, 'obs_manager'):
            self.obs_manager.stop_auto_reconnect()
            self.obs_manager.disconnect()
        
        # スレッドの終了を待機
        if self.db_monitoring_thread and self.db_monitoring_thread.is_alive():
            print("ファイル監視スレッドの終了を待機中...")
            self.db_monitoring_thread.join(timeout=2)

        if self.named_pipe_thread and self.named_pipe_thread.is_alive():
            print("named pipe受信スレッドの終了を待機中...")
            self.named_pipe_thread.join(timeout=1)
        
        if self.screen_monitoring_thread and self.screen_monitoring_thread.is_alive():
            print("画面監視スレッドの終了を待機中...")
            self.screen_monitoring_thread.join(timeout=2)
        
        # アプリケーションロックを解放
        if hasattr(self, 'app_lock'):
            self.app_lock.release_lock()
        
        print("アプリケーション終了処理完了")
        self.root.destroy()
        logger.info('closed')

    def sync_nexus_skill_to_manage_results(self):
        try:
            value = self.nexus_skill_var.get()
            if value and value != "-":
                skill = float(value.replace("★", "").strip())
                if skill != 0:
                    self.database_accessor.manage_results.nexus_skill = skill
        except Exception:
            logger.error(traceback.format_exc())
    
    def run(self):
        """アプリケーションを実行"""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except Exception as e:
            print(f"アプリケーション実行エラー: {e}")
        finally:
            # 確実にロックを解放
            if hasattr(self, 'app_lock'):
                self.app_lock.release_lock()

if __name__ == "__main__":
    # app = MainWindow() # debug
    # app.run()
    try:
        app = MainWindow()
        app.run()
    except SystemExit:
        # 二重起動による正常終了
        pass
    except Exception as e:
        print(f"アプリケーション起動エラー: {e}")
        print(traceback.format_exc())
        logger.error(traceback.format_exc())
        messagebox.showerror("エラー", f"アプリケーションの起動に失敗しました。\n{str(e)}")
