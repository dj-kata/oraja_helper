import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import tempfile
import sys
from datetime import datetime, timedelta
from config import Config
from settings import SettingsWindow
from obssocket import OBSWebSocketManager
from obs_control import OBSControlWindow

class ApplicationLock:
    """アプリケーションの二重起動防止クラス"""
    def __init__(self, app_name="file_monitor_app"):
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
        self.app_lock = ApplicationLock("file_monitor_app")
        if not self.app_lock.acquire_lock():
            messagebox.showerror(
                "起動エラー", 
                "アプリケーションは既に起動しています。\n"
                "複数のインスタンスを同時に実行することはできません。"
            )
            sys.exit(1)
        
        self.root = tk.Tk()
        self.config = Config()
        self.start_time = datetime.now()
        self.file_exists = False
        self.monitoring_thread = None
        self.is_running = True
        
        # OBS WebSocket管理クラス初期化
        self.obs_manager = OBSWebSocketManager(status_callback=self.on_obs_status_changed)
        self.obs_manager.set_config(self.config)
        
        # OBS制御管理クラス初期化
        self.obs_control = None
        
        # ゲーム状態管理
        self.current_game_state = None  # None, "select", "play", "result"
        
        self.setup_ui()
        self.start_monitoring()
        self.update_display()
        
        # WebSocket自動接続開始
        if self.config.enable_websocket:
            self.obs_manager.start_auto_reconnect()
        
        # アプリ起動時のOBS制御実行
        self.execute_obs_trigger("app_start")
    
    def setup_ui(self):
        """UIの初期設定"""
        self.root.title("ファイルモニタリングシステム")
        self.root.geometry("500x300")
        
        # メニューバー
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 設定メニュー
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="設定", menu=settings_menu)
        settings_menu.add_command(label="基本設定", command=self.open_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="OBS制御設定", command=self.open_obs_control)
        
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 経過時間表示
        ttk.Label(main_frame, text="起動からの経過時間:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.elapsed_time_var = tk.StringVar(value="00:00:00")
        ttk.Label(main_frame, textvariable=self.elapsed_time_var, font=("Arial", 12, "bold")).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 監視対象フォルダ表示
        ttk.Label(main_frame, text="監視対象フォルダ:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.oraja_path_var = tk.StringVar()
        ttk.Label(main_frame, textvariable=self.oraja_path_var, wraplength=300).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ファイル存在状況表示
        ttk.Label(main_frame, text="ファイル存在状況:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.file_status_var = tk.StringVar(value="確認中...")
        self.file_status_label = ttk.Label(main_frame, textvariable=self.file_status_var, font=("Arial", 12, "bold"))
        self.file_status_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 最終確認時刻表示
        ttk.Label(main_frame, text="最終確認時刻:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.last_check_var = tk.StringVar(value="未確認")
        ttk.Label(main_frame, textvariable=self.last_check_var).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # OBS WebSocket連携状況表示
        ttk.Label(main_frame, text="OBS WebSocket:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.obs_status_var = tk.StringVar()
        self.obs_status_label = ttk.Label(main_frame, textvariable=self.obs_status_var, wraplength=300)
        self.obs_status_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
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
    
    def update_config_display(self):
        """設定情報の表示を更新"""
        self.oraja_path_var.set(self.config.oraja_path or "未設定")
        
        # OBS WebSocket設定の更新
        self.obs_manager.set_config(self.config)
        
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
            time.sleep(1)
        elif not self.config.enable_websocket:
            self.obs_manager.stop_auto_reconnect()
            self.obs_manager.disconnect()
    
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
        self.root.after(0, update_ui)

    def start_monitoring(self):
        """ファイル監視スレッドを開始"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self.file_monitoring_worker, daemon=True)
            self.monitoring_thread.start()
    
    def file_monitoring_worker(self):
        """ファイル監視を行うワーカースレッド（スケルトンコード）"""
        while self.is_running:
            try:
                # 実際のファイル監視処理をここに実装
                target_file = self.config.get_target_file_path()
                
                if target_file:
                    file_exists_now = os.path.exists(target_file)
                    
                    # ファイル存在状態が変化した場合の処理
                    if file_exists_now != self.file_exists:
                        self.file_exists = file_exists_now
                        
                        # ここでゲーム状態を判定（実装例）
                        if self.file_exists:
                            # ファイルが検出された → ゲーム状態の変化を検出
                            # 実際の実装では、ファイル内容を解析してゲーム状態を判定
                            self.detect_game_state_change(target_file)
                        
                    # WebSocket連携処理もここに実装予定
                    if self.config.enable_websocket:
                        # TODO: WebSocket送信処理
                        pass
                else:
                    self.file_exists = False
                
                # メインスレッドでUI更新をスケジュール
                self.root.after(0, self.update_file_status)
                
            except Exception as e:
                print(f"監視エラー: {e}")
                self.root.after(0, lambda: self.status_var.set(f"監視エラー: {e}"))
            
            # 5秒間隔で監視
            time.sleep(5)
    
    def detect_game_state_change(self, file_path):
        """ゲーム状態の変化を検出してOBS制御を実行（スケルトンコード）"""
        try:
            # ここで実際のファイル内容を解析してゲーム状態を判定
            # 以下は実装例（実際にはファイル形式に応じて実装）
            
            # 例：ファイル名や内容から状態を判定
            if "select" in file_path.lower():
                new_state = "select"
            elif "play" in file_path.lower():
                new_state = "play"  
            elif "result" in file_path.lower():
                new_state = "result"
            else:
                new_state = None
            
            # 状態が変化した場合
            if new_state != self.current_game_state:
                # 前の状態の終了処理
                if self.current_game_state:
                    self.execute_obs_trigger(f"{self.current_game_state}_end")
                
                # 新しい状態の開始処理
                if new_state:
                    self.execute_obs_trigger(f"{new_state}_start")
                
                self.current_game_state = new_state
                print(f"ゲーム状態変化: {self.current_game_state}")
                
        except Exception as e:
            print(f"ゲーム状態検出エラー: {e}")
    
    def execute_obs_trigger(self, trigger: str):
        """OBS制御トリガーを実行"""
        try:
            # OBS制御ウィンドウが作成されていなくても設定は実行できるよう、
            # 直接設定データを読み込んで実行
            from obs_control import OBSControlData
            
            settings = self.control_data.get_settings_by_trigger(trigger)
            
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
                            self.obs_manager.set_current_scene(target_scene)
                            print(f"シーンを切り替え: {target_scene}")
                    
                    elif action == "show_source":
                        scene_name = setting.get("scene_name")
                        source_name = setting.get("source_name")
                        if scene_name and source_name:
                            scene_item_id = self._get_scene_item_id(scene_name, source_name)
                            if scene_item_id:
                                self.obs_manager.send_command("set_scene_item_enabled", 
                                                            scene_name=scene_name,
                                                            scene_item_id=scene_item_id,
                                                            scene_item_enabled=True)
                                print(f"ソースを表示: {scene_name}/{source_name}")
                    
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
                                print(f"ソースを非表示: {scene_name}/{source_name}")
                                
                except Exception as e:
                    print(f"制御実行エラー (trigger: {trigger}, setting: {setting}): {e}")
                    
        except Exception as e:
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
    
    def update_file_status(self):
        """ファイル状況の表示を更新"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_check_var.set(current_time)
        
        if self.file_exists:
            self.file_status_var.set("存在します")
            self.file_status_label.config(foreground="green")
            self.status_var.set("ファイルが見つかりました")
        else:
            self.file_status_var.set("存在しません")
            self.file_status_label.config(foreground="red")
            self.status_var.set("ファイルが見つかりません")
    
    def update_display(self):
        """表示の定期更新"""
        # 経過時間の更新
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # 1秒後に再実行
        self.root.after(1000, self.update_display)
    
    def open_obs_control(self):
        """OBS制御設定ダイアログを開く"""
        if not self.obs_manager.is_connected:
            messagebox.showwarning("OBS未接続", 
                                 "OBS制御設定を開くには、まずOBSに接続してください。\n"
                                 "「設定」→「基本設定」からWebSocket接続を有効にしてください。")
            return
        
        try:
            obs_control = OBSControlWindow(self.root, self.obs_manager)
        except Exception as e:
            messagebox.showerror("エラー", f"OBS制御設定ウィンドウの起動に失敗しました。\n{str(e)}")

    def open_settings(self):
        """設定ダイアログを開く"""
        def on_settings_close():
            # 設定が更新されたら表示を更新
            self.update_config_display()
        
        settings_window = SettingsWindow(self.root, self.config, on_settings_close)
    
    def on_closing(self):
        """アプリケーション終了時の処理"""
        # アプリ終了時のOBS制御実行
        self.execute_obs_trigger("app_end")
        
        self.is_running = False
        
        # OBS WebSocket接続を停止
        if hasattr(self, 'obs_manager'):
            self.obs_manager.stop_auto_reconnect()
            self.obs_manager.disconnect()
        
        # ファイル監視スレッドを停止
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1)
        
        # アプリケーションロックを解放
        if hasattr(self, 'app_lock'):
            self.app_lock.release_lock()
            
        self.root.destroy()
    
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
    try:
        app = MainWindow()
        app.run()
    except SystemExit:
        # 二重起動による正常終了
        pass
    except Exception as e:
        print(f"アプリケーション起動エラー: {e}")
        messagebox.showerror("エラー", f"アプリケーションの起動に失敗しました。\n{str(e)}")