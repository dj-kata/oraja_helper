"""
cx_Freeze
"""

import sys
from cx_Freeze import setup, Executable
import os
from pathlib import Path

include_files = []
    
# アイコンファイル
if os.path.exists('src/icon.ico'):
    include_files.append(('src/icon.ico', 'src/icon.ico'))

# ビルドオプション
build_exe_options = {
    # 含めるパッケージ
    "packages": [
        "obsws_python",  # OBS WebSocket連携に必要
        "websocket",     # obsws_pythonの依存関係（websocket-client）
        "http",
        "PIL",
        "numpy",
        "imagehash",
        "pickle",
        "bz2",
        "json",
        "traceback",
        "logging",
        "logging.handlers",
        "hashlib",
        "math",
        "datetime",
        "time",
        "threading",
        "os",
        "sys",
        "enum",
        "bs4",
        "html",
        "typing",
        "ctypes",
        "ctypes.wintypes",
        "tkinter",      # GUIに必要
        "winsound",     # サウンド再生に必要
    ],
    
    # 含めるモジュール
    "includes": [
        "icon",
        "config",
        "dataclass",
        "obs_control",
        "pickle_converter",
        "tooltip",
        "settings",
        # ctypes関連（Windows APIアクセスに必要）
        "ctypes",
        "ctypes.wintypes",
        "ctypes.util",
        # GUI/サウンド関連
        "tkinter",
        "winsound",
        # obsws_pythonはpackagesで指定
        "obsws_python.events", 
        "obsws_python.subs",
        # "obsws_python.base"
        # 認識用
    ],
    
    # 除外するパッケージ（サイズ削減のため）
    "excludes": [
        # 認証情報の平文版は除外（暗号化版を使用）
        "src.credentials",
        "credentials",
        # 以下既存の除外設定
        # tkinterとwinsoundは必要なので除外しない
        "matplotlib",
        # "scipy",
        # "pandas",
        "test",
        "unittest",
        "email",
        "html",
        "http",
        # "urllib",
        # "xml",
        # "pydoc",
        "distutils",
        "setuptools",
        "pip",
        # obsws_pythonの存在しないサブモジュール（エラー回避）
        "obsws_python.requests",
        "obsws_python.events",
    ],
    
    # 含めるファイル
    "include_files": include_files,
    
    # MSVCランタイムを含める
    "include_msvcr": True,
    
    # zip圧縮の設定
    # zip圧縮を完全に無効化
    "zip_include_packages": [],  # 全て展開
    "zip_exclude_packages": ["obsws_python"],
    
    # 最適化レベル（2が最大）
    "optimize": 2,
    
    # ビルドディレクトリ名
    "build_exe": "oraja_helper",
}

# ベースの設定
base = None
if sys.platform == "win32":
    # Windowsの場合、コンソールを非表示にする
    base = "Win32GUI"
elif sys.platform == "darwin":
    # macOSの場合
    base = None

# 実行ファイルの設定
executables = [
    Executable(
        script="oraja_helper.pyw",
        base=base,
        target_name="oraja_helper.exe" if sys.platform == "win32" else "IIDXHelper",
        icon='src/icon.ico',  # アイコンファイルがあれば指定: "resources/icon.ico"
        shortcut_name="oraja_helper",
        shortcut_dir="DesktopFolder",
    )
]

# セットアップ
setup(
    name="oraja helper",
    version="1.0.0",
    description="OBS連携による自動リザルト保存アプリケーション",
    options={
        "build_exe": build_exe_options,
    },
    executables=executables,
)