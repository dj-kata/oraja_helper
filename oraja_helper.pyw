import sqlite3, json
import webbrowser, urllib, requests, traceback, re, os, datetime
import time, sys
import pandas as pd
from bs4 import BeautifulSoup
from settings import *
from obssocket import *
import PySimpleGUI as sg
from enum import Enum
import logging, logging.handlers
from functools import partial
from tkinter import filedialog
import threading
import subprocess

FONT = ('Meiryo',12)
FONTs = ('Meiryo',8)
par_text = partial(sg.Text, font=FONT)
par_btn = partial(sg.Button, pad=(3,0), font=FONT, enable_events=True, border_width=0)
sg.theme('SystemDefault')

os.makedirs('log', exist_ok=True)
os.makedirs('out', exist_ok=True)
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
lamp = ['NO PLAY', 'FAILED', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO']

class gui_mode(Enum):
    init = 0
    main = 1
    settings = 2

try:
    with open('version.txt', 'r') as f:
        SWVER = f.readline().strip()
except Exception:
    SWVER = "v?.?.?"

class Misc:
    SONGDATA = '/mnt/d/bms/beatoraja/songdata.db'
    SONGINFO = '/mnt/d/bms/beatoraja/songinfo.db'
    SCORELOG = '/mnt/d/bms/beatoraja/player/player1/scorelog.db'
    SCOREDATALOG = '/mnt/d/bms/beatoraja/player/player1/scoredatalog.db'
    SCORE    = '/mnt/d/bms/beatoraja/player/player1/score.db'
    def __init__(self):
        self.gui_mode = gui_mode.init
        self.window = None
        self.settings = BmsMiscSettings()
        self.difftable = []
        self.update_db_settings()
        self.load()
        self.start_time = datetime.datetime.now()
        self.last = (datetime.datetime.now() - datetime.timedelta(minutes=0)).timestamp()
        self.result_log = []
        self.notes = 0
        self.last_notes = 0
        self.ico=self.ico_path('icon.ico')
        self.write_xml()
        logger.debug('constructor end')

    def ico_path(self, relative_path:str):
        """アイコン表示用

        Args:
            relative_path (str): アイコンファイル名

        Returns:
            str: アイコンファイルの絶対パス
        """
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

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

    def update_text(self, src, txt):
        """sg.Textの更新用

        Args:
            src (str): ソース名
            txt (str): 変更後の文字列
        """
        ret = False
        try:
            if src in self.window.key_dict.keys():
                self.window[src].update(txt)
                ret = True
        except Exception:
            logger.debug(traceback.format_exc())
        return ret
    
    def reload_score(self):
        """プレーヤーのdbを一通りリロード
        """
        conn = sqlite3.connect(self.settings.db_scorelog)
        self.df_log =pd.read_sql('SELECT * FROM scorelog', conn)
        conn = sqlite3.connect(self.settings.db_score)
        self.df_sc =pd.read_sql('SELECT * FROM score', conn)
        conn = sqlite3.connect(self.settings.db_scoredatalog)
        self.df_data =pd.read_sql('SELECT * FROM scoredatalog', conn)

    def load(self):
        """DB(スコア、曲情報)及び難易度表を読み込む
        """
        if os.path.exists('difftable.pkl'):
            with open('difftable.pkl', 'rb') as f:
                self.difftable = pickle.load(f)
        if self.settings.is_valid():
            conn = sqlite3.connect(self.settings.db_songdata)
            self.df_song =pd.read_sql('SELECT * FROM song', conn)
            self.df_folder =pd.read_sql('SELECT * FROM folder', conn)

            conn = sqlite3.connect(self.settings.db_songinfo)
            self.df_info =pd.read_sql('SELECT * FROM information', conn)

            self.reload_score()

    def check_url(self, url):
        flag = True
        try:
            f = urllib.request.urlopen(url)
            f.close()
        except urllib.error.URLError:
            print('Not found:', url)
            flag = False
        except urllib.request.HTTPError:
            print('Not found:', url)
            flag = False
        except ValueError:
            print('Not found:', url)
            flag = False

        return flag

    def get_header_filename(self, url):
        ret = False
        if self.check_url(url):
            tmp = urllib.request.urlopen(url).read()
            soup = BeautifulSoup(tmp, 'html.parser')
            metas = soup.find_all('meta')
            for m in metas:
                if 'name' in m.attrs.keys():
                    if m.attrs['name'] == 'bmstable':
                        ret = m.attrs['content']
        return ret

    def read_table_json(self, url):
        ret = False
        #print(url, 'check_url:',self.check_url(url))
        if self.check_url(url):
            tmp = urllib.request.urlopen(url).read()
            ret = json.loads(tmp)
        return ret

    # 1曲分のjsonデータを受け取ってdownload
    def get_onesong(self, js):
        #print(js)
        print(f"{self.symbol}{js['level']} {js['sha256']}")
        print(js['title'], js['artist'])
        if js['url']:
            print(js['url'], end='')
        if js['url_diff']:
            print(f"\njs['url_diff']")
        else:
            print(f" (同梱譜面)")

    def update_table(self):
        difftable = []
        for url in self.settings.table_url:
            logger.debug(f'getting: {url}')
            try:
                header_filename = self.get_header_filename(url)
                if ('http://' in header_filename) or ('https://' in header_filename):
                    url_header = header_filename
                else:
                    url_header = re.sub(url.split('/')[-1], header_filename, url)
                ### header情報から難易度名などを取得
                info = self.read_table_json(url_header)
                if ('http://' in info['data_url']) or ('https://' in info['data_url']):
                    url_dst = info['data_url']
                else:
                    url_dst = re.sub(url.split('/')[-1], info['data_url'], url)
                self.songs = self.read_table_json(url_dst)
                #print(f'url_header = {url_header}')
                #print(f'url_dst = {url_dst}')

                self.name = info['name']
                self.symbol = info['symbol']
                #print(f"name:{self.name}, symbol:{self.symbol}")

                for s in self.songs:
                    has_sabun = ''
                    if s['url_diff'] != "":
                        has_sabun = '○'
                    if 'proposer' in s.keys():
                        proposer = s['proposer']
                    else:
                        proposer = ''
                    if 'sha256' in s.keys():
                        hashval = s['sha256']
                    elif 'md5' in s.keys():
                        hashval = s['md5']
                    else:
                        hashval = ''
                    onesong = [self.symbol+s['level'], s['title'], s['artist'], has_sabun, proposer, hashval]
                    difftable.append(onesong)
                #self.window['table'].update(data)
                #self.update_info(f'難易度表読み込み完了。({self.name})')
            except: # URLがおかしい
                traceback.print_exc()
                #self.update_info('存在しないURLが入力されました。ご確認をお願いします。')
        self.difftable = difftable
        logger.debug('end')
        with open('difftable.pkl', 'wb') as f:
            pickle.dump(difftable, f)
        return difftable

    def parse(self, tmpdat):
        if type(tmpdat['sha256']) == str:
            hsh = tmpdat['sha256']
        else:
            hsh=tmpdat['sha256'].values[0]
        tmpsc = self.df_sc[self.df_sc['sha256'] == hsh].tail(1)
        tmp = self.df_log[self.df_log['sha256'] == hsh].tail(1)
        #pre_score = tmp.oldscore.values[0]
        pre_score = (tmpsc.epg.values[0]+tmpsc.lpg.values[0])*2+(tmpsc.egr.values[0]+tmpsc.lgr.values[0])
        notes = tmpsc.notes.values[0]
        info = self.df_song[self.df_song['sha256'] == hsh].tail(1)
        title = info.title.values[0]
        lampid = tmpdat.clear#.values[0]
        judge = [
            tmpdat.epg+tmpdat.lpg,
            tmpdat.egr+tmpdat.lgr,
            tmpdat.egd+tmpdat.lgd,
            tmpdat.ebd+tmpdat.lbd,
            tmpdat.epr+tmpdat.lpr,
            tmpdat.ems+tmpdat.lms,
        ]
        score = judge[0]*2+judge[1]
        score_rate = f"{score/notes*100/2:.2f}"
        return title, lampid, score, pre_score, score_rate, tmpdat.date, judge

    def get_new_update(self, num):
        """df_dataから指定された個数の最新リザルトをreadして返す

        Args:
            num (int): いくつ読み込むか

        Returns:
            list: 1エントリが[難易度,タイトル,ランプ,スコア,スコア更新分,スコアレート,日付,判定内訳]のリスト
        """
        ret = []
        for i in range(num):
            try:
                idx = len(self.df_data) - num + i
                tmp = self.df_data.loc[idx, :]
                title, lampid, score, pre_score, score_rate, date, judge = self.parse(tmp)
                d,t = self.get_difficulty(tmp.sha256, title)
                if d == None:
                    d = ''
                ret.append([d, title, lamp[lampid], score, score-pre_score, score_rate, date, judge])
            except Exception:
                logger.debug(traceback.format_exc())
        return ret

    def get_difficulty(self, sha256, title):
        """self.df_logのidxを受けて、その譜面の難易度を返す

        Args:
            idx (int): インデックス
        Returns:
            difficulty (str): 難易度(sl1とか)
            title (str): 曲名
        """
        ans = None
        md5 = '' # 初期化しておく
        for s in self.difftable:
            md5 = self.df_song[self.df_song['sha256']==sha256].tail(1).md5.values[0]
            if s[-1] in (sha256, md5):
                ans = s[0]
                break
        logger.debug(f'sha256={sha256}, md5={md5}, ans={ans}, title={title}')
        return (ans, title)
    
    def write_xml(self):
        if self.settings.is_valid():
            with open('history.xml', 'w', encoding='utf-8') as f:
                f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
                f.write("<Items>\n")
                f.write(f"    <date>{self.start_time.year}/{self.start_time.month:02d}/{self.start_time.day:02d}</date>\n")
                f.write(f'    <notes>{self.notes}</notes>\n')
                f.write(f'    <last_notes>{self.last_notes}</last_notes>\n')
                for r in self.result_log:
                    title_esc = r[1].replace('&', '&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&apos;')
                    f.write(f'    <Result>\n')
                    f.write(f'        <lv>{r[0]}</lv>\n')
                    f.write(f'        <title>{title_esc}</title>\n')
                    f.write(f'        <lamp>{r[2]}</lamp>\n')
                    f.write(f'        <score>{r[3]}</score>\n')
                    f.write(f'        <diff>{r[4]:+}</diff>\n')
                    f.write(f'        <score_rate>{float(r[5]):.2f}</score_rate>\n')
                    f.write('    </Result>\n')
                f.write("</Items>\n")

    def check_db(self):
        if not self.settings.is_valid():
            logger.debug('設定ファイルが読み込めません')
            if self.update_text('db_state', '見つかりません。beatoraja設定を確認してください。'):
                self.window['db_state'].update(text_color='#ff0000')
        update_time = os.path.getmtime(self.settings.db_score)
        if update_time > self.last: # 1曲プレーした時に通る
            logger.debug('dbfile updated')
            self.reload_score()
            self.last = update_time
            tmp = self.get_new_update(1)
            for t in tmp:
                if t not in self.result_log:
                    logger.debug(f'added: {t}')
                    self.result_log.append(t)
                    judge = t[-1]
                    self.notes += judge[0] + judge[1] + judge[2]
                    self.last_notes = judge[0] + judge[1] + judge[2]
                    self.write_xml()

    def update_settings(self, ev, val):
        """GUIから値を取得し、設定の更新を行う。

        Args:
            ev (str): sgのイベント
            val (dict): sgの各GUIの値
        """
        self.settings.lx = self.window.current_location()[0]
        self.settings.ly = self.window.current_location()[1]
        if self.gui_mode == gui_mode.main:
            pass
        elif self.gui_mode == gui_mode.settings:
            pass
            #self.settings['host'] = val['input_host']
            #self.settings['obs_port'] = val['obs_port']
            #self.settings['obs_password'] = val['obs_password']
            #self.settings['on_memory'] = val['on_memory']

    def update_db_settings(self):
        """orajaとplayerのフォルダ情報を元に各dbファイルのパスを決定
        """
        if (self.settings.dir_oraja != '') and (self.settings.dir_player != ''):
            #self.settings.db_songdata = os.path.join(self.settings.dir_oraja, 'songdata.db')
            self.settings.db_songdata = self.settings.dir_oraja + '/songdata.db'
            self.settings.db_songinfo = os.path.join(self.settings.dir_oraja, 'songinfo.db')
            self.settings.db_score = os.path.join(self.settings.dir_player, 'score.db')
            self.settings.db_scorelog = os.path.join(self.settings.dir_player, 'scorelog.db')
            self.settings.db_scoredatalog = os.path.join(self.settings.dir_player, 'scoredatalog.db')
            print(self.settings.dir_oraja, self.settings.dir_player)
        if self.settings.is_valid():
            print('dbファイル登録成功')
            logger.debug('dbファイル登録成功')
        else:
            print('Error! dbファイル登録失敗')

    def gui_settings(self):
        self.gui_mode = gui_mode.settings
        if self.window:
            self.window.close()
        layout = [
            [par_text('beatorajaインストール先'), sg.Button('変更', key='btn_dir_oraja')],
            [sg.Text(self.settings.dir_oraja, key='txt_dir_oraja')],
            [par_text('playerフォルダ'), sg.Button('変更', key='btn_dir_player')],
            [sg.Text(self.settings.dir_player, key='txt_dir_player')],
            [par_text('難易度表URL'), sg.Input('', key='input_url', size=(50,1))],
            [sg.Listbox(self.settings.table_url, key='list_url', size=(50,4)), sg.Column([[par_btn('add', key='add_url'), par_btn('del', key='del_url'), par_btn('reload', key='reload_table')]])],
        ]
        self.window = sg.Window('oraja_helper', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico,location=(self.settings.lx, self.settings.ly))

    def gui_main(self):
        self.gui_mode = gui_mode.main
        if self.window:
            self.window.close()
        menuitems = [
            ['file',['settings', 'アップデートを確認', 'exit']]
        ]
        layout = [
            [sg.Menubar(menuitems, key='menu')],
            [par_text('playdata:'), par_text('OOO', key='db_state')],
            [par_text('date:'), par_text(f"{self.start_time.year}/{self.start_time.month:02d}/{self.start_time.day:02d}")],
            [par_text('notes:'), par_text(self.notes, key='notes')],
        ]
        self.window = sg.Window('oraja_helper', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico,location=(self.settings.lx, self.settings.ly))
        if self.settings.is_valid():
            self.update_text('db_state', 'OK')
            self.window['db_state'].update(text_color='#0000ff')
        else:
            self.update_text('db_state', '見つかりません。beatoraja設定を確認してください。')
            self.window['db_state'].update(text_color='#ff0000')


    def main(self):
        self.gui_main()
        self.window.write_event_value('アップデートを確認', " ")
        self.th = threading.Thread(target=self.check, daemon=True)
        self.th.start()
        while True:
            ev,val = self.window.read()
            self.update_settings(ev, val)
            self.settings.save()
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'exit'):
                # 終了
                if self.gui_mode == gui_mode.main:
                    print('quit!')
                    #self.save_settings()
                    break
                else:
                    self.update_db_settings()
                    self.gui_main()
            elif ev == 'settings':
                self.gui_settings()
            elif ev == 'btn_dir_oraja':
                tmp = filedialog.askdirectory()
                if tmp != '':
                    self.settings.dir_oraja = tmp
                    self.window['txt_dir_oraja'].update(tmp)
            elif ev == 'btn_dir_player':
                tmp = filedialog.askdirectory()
                if tmp != '':
                    self.settings.dir_player = tmp
                    self.window['txt_dir_player'].update(tmp)
            
            elif ev == 'add_url': # 難易度表追加
                self.settings.table_url.append(val['input_url'])
                self.settings.table_url = sorted(list(set(self.settings.table_url)))
                self.window['list_url'].update(self.settings.table_url)
            elif ev == 'del_url': # 難易度表削除
                idx = self.settings.table_url.index(val['list_url'][0])
                self.settings.table_url.pop(idx)
                self.window['list_url'].update(self.settings.table_url)
            elif ev == 'reload_table':
                self.update_table()

            elif ev == 'アップデートを確認':
                ver = self.get_latest_version()
                if ver != SWVER:
                    print(f'現在のバージョン: {SWVER}, 最新版:{ver}')
                    ans = sg.popup_yes_no(f'アップデートが見つかりました。\n\n{SWVER} -> {ver}\n\nアプリを終了して更新します。', icon=self.ico)
                    if ans == "Yes":
                        #self.control_obs_sources('quit')
                        if os.path.exists('update.exe'):
                            logger.info('アップデート確認のため終了します')
                            res = subprocess.Popen('update.exe')
                            break
                        else:
                            sg.popup_error('update.exeがありません', icon=self.ico)
                else:
                    print(f'お使いのバージョンは最新です({SWVER})')

    def check(self):
        while True:
            self.check_db()
            self.update_text('notes', self.notes)
            time.sleep(1)

a = Misc()
if a.settings.is_valid():
    x = a.get_new_update(3)
    for xx in x:
        print(xx)
#
#tmpdat = a.df_data.tail(1)
#hsh=tmpdat.sha256.values[0]
#tmp=a.df_log[a.df_log['sha256']==hsh].tail(1)
#tmpsc=a.df_sc[a.df_sc['sha256']==hsh].tail(1)

#a.do()
a.main()
