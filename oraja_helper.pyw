import sqlite3, json
import webbrowser, urllib, requests, traceback, re, os, datetime
import time, sys
import pandas as pd
from bs4 import BeautifulSoup
from settings import *
from obssocket import *
import PySimpleGUI as sg
from PIL import ImageDraw, Image
from enum import Enum
import logging, logging.handlers
from functools import partial
from tkinter import filedialog
import threading
import subprocess
import copy
import imagehash

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
    obs_control = 3
    register_scene = 4

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
        self.imgpath = os.getcwd()+'/out/capture.png'
        self.obs = None
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

    def connect_obs(self):
        if not self.settings.enable_obs_control:
            if self.obs != None:
                self.obs.close()
            self.obs = None
            return False
        if self.obs != None:
            self.obs.close()
            self.obs = None
        try:
            self.obs = OBSSocket(self.settings.host, self.settings.port, self.settings.passwd, self.settings.obs_source, self.imgpath)
            if self.gui_mode == gui_mode.main:
                self.update_text('obs_state', 'OK')
                self.window['obs_state'].update(text_color='#0000ff')
                logger.debug('OBSに接続しました')
            return True
        except:
            logger.debug(traceback.format_exc())
            self.obs = None
            logger.debug('obs websocket error!')
            if self.gui_mode == gui_mode.main:
                self.update_text('obs_state', '接続されていません')
                self.window['obs_state'].update(text_color='#ff0000')
            return False

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
        sum_judge = [0, 0, 0, 0, 0, 0]
        for t in self.result_log:
            judge = t[-1]
            for i in range(6):
                sum_judge[i] += judge[i]
        score_rate = 0 # total
        if (sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]) > 0:
            score_rate = 100*(sum_judge[0]*2+sum_judge[1]) / (sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]) / 2
        self.update_text('notes', self.notes)
        self.update_text('score_rate', f"{score_rate:.2f}")
        if self.settings.is_valid():
            with open('history.xml', 'w', encoding='utf-8') as f:
                f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
                f.write("<Items>\n")
                f.write(f"    <date>{self.start_time.year}/{self.start_time.month:02d}/{self.start_time.day:02d}</date>\n")
                f.write(f'    <notes>{self.notes}</notes>\n')
                f.write(f'    <total_score_rate>{score_rate:.2f}</total_score_rate>\n')
                f.write(f'    <playcount>{len(self.result_log)}</playcount>\n')
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
                    self.notes += judge[0] + judge[1] + judge[2] + judge[3] + judge[4]
                    self.last_notes = judge[0] + judge[1] + judge[2] + judge[3] + judge[4]
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
            #self.settings.log_offset = val['log_offset']
            self.settings.tweet_on_exit = val['tweet_on_exit']
            self.settings.enable_obs_control = val['enable_obs_control']
            self.settings.host = val['obs_host']
            self.settings.port = val['obs_port']
            self.settings.passwd = val['obs_passwd']
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

    def tweet(self):
        sum_judge = [0, 0, 0, 0, 0, 0]
        for t in self.result_log:
            judge = t[-1]
            for i in range(6):
                sum_judge[i] += judge[i]
        today_notes = sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]
        score_rate = 0
        if (sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]) > 0:
            score_rate = 100*(sum_judge[0]*2+sum_judge[1]) / (sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]) / 2
        msg = f"今日は{today_notes:,}ノーツ叩きました。スコアレート: {score_rate:.2f}%\n"
        msg += f"(PG: {sum_judge[0]:,}, GR: {sum_judge[1]:,}, GD: {sum_judge[2]:,}, BD: {sum_judge[3]:,}, PR: {sum_judge[4]:,}, MISS: {sum_judge[5]:,})\n"
        msg += '#oraja_helper\n'
        encoded_msg = urllib.parse.quote(msg)
        webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_msg}")

    def load_old_results(self):
        """過去のリザルト(指定オフセット時刻まで)を本日のリザルトとして登録
        """
        date_target = self.start_time - datetime.timedelta(hours=float(self.settings.log_offset))
        for _,row in self.df_data.iterrows():
            if datetime.datetime.fromtimestamp(row['date']) >= date_target:
                title, lampid, score, pre_score, score_rate, date, judge = self.parse(row)
                d,t = self.get_difficulty(row['sha256'], title)
                if d == None:
                    d = ''
                self.result_log.append([d, title, lamp[lampid], score, score-pre_score, score_rate, date, judge])
        sum_judge = [0, 0, 0, 0, 0, 0]
        for t in self.result_log:
            judge = t[-1]
            for i in range(6):
                sum_judge[i] += judge[i]
        self.notes = sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]
        self.update_text('notes', self.notes)
        self.write_xml()

    def gui_settings(self):
        self.gui_mode = gui_mode.settings
        if self.window:
            self.window.close()
        layout_obs = [
            [sg.Checkbox('OBS連携機能を利用する', key='enable_obs_control', default=self.settings.enable_obs_control, enable_events=True)],
            [par_text('OBS host: '), sg.Input(self.settings.host, font=FONT, key='obs_host', size=(20,20))],
            [par_text('OBS websocket port: '), sg.Input(self.settings.port, font=FONT, key='obs_port', size=(10,20))],
            [par_text('OBS websocket password'), sg.Input(self.settings.passwd, font=FONT, key='obs_passwd', size=(20,20), password_char='*')],
        ]
        layout = [
            [par_text('beatorajaインストール先'), sg.Button('変更', key='btn_dir_oraja')],
            [sg.Text(self.settings.dir_oraja, key='txt_dir_oraja')],
            [par_text('playerフォルダ'), sg.Button('変更', key='btn_dir_player')],
            [sg.Text(self.settings.dir_player, key='txt_dir_player')],
            #[par_text('起動時刻より前のリザルトも含める'), sg.Spin([i for i in range(25)],readonly=True, default_value=self.settings.log_offset,key='log_offset', enable_events=True, size=(4,1))],
            [sg.Checkbox('終了時にツイート画面を開く', key='tweet_on_exit', default=self.settings.tweet_on_exit, enable_events=True)],
            [par_text('難易度表URL'), sg.Input('', key='input_url', size=(50,1))],
            [sg.Listbox(self.settings.table_url, key='list_url', size=(50,4)), sg.Column([[par_btn('add', key='add_url'), par_btn('del', key='del_url'), par_btn('reload', key='reload_table')]])],
            [sg.Frame('OBS設定', layout=layout_obs, title_color='#000044')],
        ]
        self.window = sg.Window('oraja_helper', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico,location=(self.settings.lx, self.settings.ly))

    def build_layout_one_scene(self, name, LR=None):
        """OBS制御設定画面におけるシーン1つ分のGUIを出力する。

        Args:
            name (str): シーン名
            LR (bool, optional): 開始、終了があるシーンかどうかを指定。 Defaults to None.

        Returns:
            list: pysimpleguiで使うレイアウトを格納した配列。
        """
        if LR == None:
            sc = [
                    sg.Column([[par_text('表示する')],[sg.Listbox(self.settings.obs_enable[name], key=f'obs_enable_{name}', size=(20,4))], [par_btn('add', key=f'add_enable_{name}'),par_btn('del', key=f'del_enable_{name}')]]),
                    sg.Column([[par_text('消す')],[sg.Listbox(self.settings.obs_disable[name], key=f'obs_disable_{name}', size=(20,4))], [par_btn('add', key=f'add_disable_{name}'),par_btn('del', key=f'del_disable_{name}')]]),
                ]
        else:
            scL = [[
                    sg.Column([[par_text('表示する')],[sg.Listbox(self.settings.obs_enable[f'{name}0'], key=f'obs_enable_{name}0', size=(20,4))], [par_btn('add', key=f'add_enable_{name}0'),par_btn('del', key=f'del_enable_{name}0')]]),
                    sg.Column([[par_text('消す')],[sg.Listbox(self.settings.obs_disable[f'{name}0'], key=f'obs_disable_{name}0', size=(20,4))], [par_btn('add', key=f'add_disable_{name}0'),par_btn('del', key=f'del_disable_{name}0')]]),
                ]]
            scR = [[
                    sg.Column([[par_text('表示する')],[sg.Listbox(self.settings.obs_enable[f'{name}1'], key=f'obs_enable_{name}1', size=(20,4))], [par_btn('add', key=f'add_enable_{name}1'),par_btn('del', key=f'del_enable_{name}1')]]),
                    sg.Column([[par_text('消す')],[sg.Listbox(self.settings.obs_disable[f'{name}1'], key=f'obs_disable_{name}1', size=(20,4))], [par_btn('add', key=f'add_disable_{name}1'),par_btn('del', key=f'del_disable_{name}1')]]),
                ]]
            sc = [
                sg.Frame('開始時', scL, title_color='#440000'),sg.Frame('終了時', scR, title_color='#440000')
            ]
        layout_main = [
                par_text('シーン:')
                ,par_text(self.settings.obs_scene[name], size=(20, 1), key=f'obs_scene_{name}')
                ,par_btn('set', key=f'set_scene_{name}')
        ]
        if LR != None:
            layout_main.append(par_btn('シーン判定用画像登録', key=f'register_scene_{name}'))
        ret = [
            layout_main,
            sc
        ]
        return ret

    def gui_obs_control(self):
        """OBS制御設定画面のGUIを起動する。
        """
        if self.obs == None:
            sg.popup_error('OBSwebsocketの設定がされていません。\n設定画面を確認してください。')
            return -1
        self.gui_mode = gui_mode.init
        if self.window:
            self.window.close()
        obs_scenes = []
        obs_sources = []
        if self.obs != None:
            tmp = self.obs.get_scenes()
            tmp.reverse()
            for s in tmp:
                obs_scenes.append(s['sceneName'])
        layout_select = self.build_layout_one_scene('select', 0)
        layout_play = self.build_layout_one_scene('play', 0)
        layout_result = self.build_layout_one_scene('result', 0)
        layout_boot = self.build_layout_one_scene('boot')
        layout_quit = self.build_layout_one_scene('quit')
        layout_obs2 = [
            [par_text('シーンコレクション(起動時に切り替え):'), sg.Combo(self.obs.get_scene_collection_list(), key='scene_collection', size=(40,1), enable_events=True)],
            [par_text('シーン:'), sg.Combo(obs_scenes, key='combo_scene', size=(40,1), enable_events=True)],
            [par_text('ソース:'),sg.Combo(obs_sources, key='combo_source', size=(40,1))],
            [par_text('ゲーム画面:'), par_text(self.settings.obs_source, size=(20,1), key='obs_source'), par_btn('set', key='set_obs_source')],
            [sg.Frame('選曲画面',layout=layout_select, title_color='#000044')],
            [sg.Frame('プレー中',layout=layout_play, title_color='#000044')],
            [sg.Frame('リザルト画面',layout=layout_result, title_color='#000044')],
        ]
        layout_r = [
            [sg.Frame('oraja_helper起動時', layout=layout_boot, title_color='#000044')],
            [sg.Frame('oraja_helper終了時', layout=layout_quit, title_color='#000044')],
        ]

        col_l = sg.Column(layout_r)
        col_r = sg.Column(layout_obs2)

        layout = [
            [col_l, col_r],
            [sg.Text('', key='info', font=(None,9))]
        ]
        self.gui_mode = gui_mode.obs_control
        self.window = sg.Window(f"oraja_helper - OBS制御設定", layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico,location=(self.settings.lx, self.settings.ly))
        if self.settings.obs_scene_collection != '':
            self.window['scene_collection'].update(value=self.settings.obs_scene_collection)

    def update_preview(self):
        """シーン登録画面のプレビュー表示を更新する
        """
        self.preview = copy.copy(self.img_org)
        self.trimmed = None
        # 矩形を書き込む
        try:
            sx = int(self.window['sx'].get())
            sy = int(self.window['sy'].get())
            ex = int(self.window['ex'].get())
            ey = int(self.window['ey'].get())
            self.trimmed = self.img_org.crop((sx,sy,ex,ey))
            self.settings.obs_target_hash[self.register_scene_name] = imagehash.average_hash(self.trimmed)
            self.update_text('target_hash', self.settings.obs_target_hash[self.register_scene_name])
            print(f"{self.register_scene_name}: {self.settings.obs_target_hash[self.register_scene_name]}")
            draw = ImageDraw.Draw(self.preview)
            draw.rectangle([(sx,sy),(ex,ey)], outline=(255,0,0),width=4)
        except Exception:
            print('矩形描画時にエラー。スキップします。')

        # 縮小処理
        w,h=self.preview.size
        maxw=1200;maxh=900
        if w > maxw:
            h = int(maxw*h/w)
            w = maxw
        if h > maxh:
            w = int(maxh*w/h)
            h = maxh
        self.preview = self.preview.resize((w,h))
        # 出力
        bio = io.BytesIO()
        self.preview.save(bio, format='PNG')
        self.window['image_register'].update(bio.getvalue())

    def gui_register_scene(self, name):
        self.gui_mode = gui_mode.init
        self.register_scene_name = name # 記憶しておく
        if self.window:
            self.window.close()
        layout_trim = [
            [
                par_text('sx'), sg.Input(self.settings.obs_trim[name][0], size=(5,1), key='sx', enable_events=True),
                par_text('sy'), sg.Input(self.settings.obs_trim[name][1], size=(5,1), key='sy', enable_events=True),
                par_text('ex'), sg.Input(self.settings.obs_trim[name][2], size=(5,1), key='ex', enable_events=True),
                par_text('ey'), sg.Input(self.settings.obs_trim[name][3], size=(5,1), key='ey', enable_events=True),
            ]
        ]
        layout = [
            [
                par_btn('保存', key='save_scene'),
                par_btn('画像読み込み', key='read_image'),
                sg.Frame('トリミング範囲', layout=layout_trim, title_color='#000044'),
                par_text('hash:'),
                par_text(self.settings.obs_target_hash[name], key='target_hash'),
                par_text('判定しきい値'),
                sg.Combo([i for i in range(33)], default_value=self.settings.obs_hash_threshold[name], key='hash_threshold')
            ],
            [sg.Image(None, key='image_register')]
        ]
        self.gui_mode = gui_mode.register_scene
        self.window = sg.Window(f"oraja_helper - 判定用画像登録 (シーン:{name})", layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico,location=(self.settings.lx, self.settings.ly), modal=True)

    def gui_main(self):
        self.gui_mode = gui_mode.main
        if self.window:
            self.window.close()
        menuitems = [
            ['File',['settings', 'OBS制御設定', 'exit']],
            ['Tool',['ノーツ数をTweet', 'アップデートを確認']]
        ]
        layout = [
            [sg.Menubar(menuitems, key='menu')],
            [par_text('playdata:'), par_text('OOO', key='db_state'),par_text('OBS連携:'), par_text('接続されていません', key='obs_state')],
            [par_text('難易度表: '), par_text(str(len(self.settings.table_url))), par_text(f'({len(self.difftable):,}譜面)')],
            [par_text('date:'), par_text(f"{self.start_time.year}/{self.start_time.month:02d}/{self.start_time.day:02d}")],
            [par_text('notes:'), par_text(self.notes, key='notes')],
            [par_text('score_rate:'), par_text('0.00', key='score_rate'), par_text('%')],
        ]
        self.window = sg.Window(f'oraja_helper {SWVER}', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=self.ico,location=(self.settings.lx, self.settings.ly))
        if self.settings.is_valid():
            self.update_text('db_state', 'OK')
            self.window['db_state'].update(text_color='#0000ff')
        else:
            self.update_text('db_state', '見つかりません。beatoraja設定を確認してください。')
            self.window['db_state'].update(text_color='#ff0000')

    def main(self):
        self.gui_main()
        self.window.write_event_value('アップデートを確認', " ")
        self.connect_obs()
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
                    if self.settings.tweet_on_exit:
                        self.tweet()
                    #self.save_settings()
                    break
                elif self.gui_mode == gui_mode.register_scene:
                    self.gui_obs_control()
                else:
                    self.update_db_settings()
                    self.gui_main()
                    self.connect_obs()
            elif ev == 'settings':
                self.gui_settings()
            elif ev == 'OBS制御設定':
                self.gui_obs_control()
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

            elif ev.startswith('register_scene_'):
                key = ev.split('register_scene_')[-1]
                self.gui_register_scene(key)
            elif ev == 'read_image':
                tmp = filedialog.askopenfilename(filetypes=[(f'{self.register_scene_name}画面の判定用画像ファイル', "*.png;*.jpg;*.bmp")])
                if tmp != '':
                    self.img_org = Image.open(tmp)
                    self.update_preview()
            elif ev in ('sx', 'sy', 'ex', 'ey'):
                self.update_preview()
            elif ev == 'save_scene':
                sx = self.window['sx'].get()
                sy = self.window['sy'].get()
                ex = self.window['ex'].get()
                ey = self.window['ey'].get()
                if sx.strip() != '':
                    self.settings.obs_trim[self.register_scene_name][0] = sx
                if sy.strip() != '':
                    self.settings.obs_trim[self.register_scene_name][1] = sy
                if ex.strip() != '':
                    self.settings.obs_trim[self.register_scene_name][2] = ex
                if ey.strip() != '':
                    self.settings.obs_trim[self.register_scene_name][3] = ey
                hash = self.window['target_hash'].get()
                if hash != '':
                    self.settings.obs_target_hash[self.register_scene_name] = hash
                threshold = self.window['hash_threshold'].get()
                if threshold != '':
                    self.settings.obs_hash_threshold[self.register_scene_name] = threshold
            elif ev == 'combo_scene': # シーン選択時にソース一覧を更新
                if self.obs != None:
                    sources = self.obs.get_sources(val['combo_scene'])
                    self.window['combo_source'].update(values=sources)
            elif ev == 'set_obs_source':
                tmp = val['combo_source'].strip()
                if tmp != "":
                    self.settings.obs_source = tmp
                    self.window['obs_source'].update(tmp)
            elif ev.startswith('set_scene_'): # 各画面のシーンsetボタン押下時
                tmp = val['combo_scene'].strip()
                self.settings.obs_scene[ev.split('_')[-1]] = tmp
                self.window[ev.replace('set_scene', 'obs_scene')].update(tmp)
            elif ev.startswith('add_enable_') or ev.startswith('add_disable_'):
                table_key = ev.replace('add', 'obs') # GUI上の要素名
                tmp = val['combo_source'].strip() # play1みたいな識別子
                key = ev.split('_')[-1]
                if tmp != "":
                    if 'enable' in ev:
                        if tmp not in self.settings.obs_enable[key]:
                            self.settings.obs_enable[key].append(tmp)
                            self.window[table_key].update(self.settings.obs_enable[key])
                    else:
                        if tmp not in self.settings.obs_disable[key]:
                            self.settings.obs_disable[key].append(tmp)
                            self.window[table_key].update(self.settings.obs_disable[key])
            elif ev.startswith('del_enable_') or ev.startswith('del_disable_'):
                table_key = ev.replace('del', 'obs') # GUI上の要素名
                key = ev.split('_')[-1] # play1みたいな識別子
                if len(val[table_key]) > 0:
                    tmp = val[table_key][0]
                    if tmp != "":
                        if 'enable' in ev:
                            if tmp in self.settings.obs_enable[key]:
                                self.settings.obs_enable[key].pop(self.settings.obs_enable[key].index(tmp))
                                self.window[table_key].update(self.settings.obs_enable[key])
                        else:
                            if tmp in self.settings.obs_disable[key]:
                                self.settings.obs_disable[key].pop(self.settings.obs_disable[key].index(tmp))
                                self.window[table_key].update(self.settings.obs_disable[key])
            elif ev == 'set_obs_source':
                tmp = val['combo_source'].strip()
                if tmp != "":
                    self.settings.obs_source = tmp
                    self.window['obs_source'].update(tmp)
            elif ev == 'scene_collection': # シーンコレクションを選択
                self.settings.obs_scene_collection = val[ev]
                self.obs.set_scene_collection(val[ev]) # そのシーンコレクションに切り替え
                obs_scenes = []
                tmp = self.obs.get_scenes()
                tmp.reverse()
                for s in tmp:
                    obs_scenes.append(s['sceneName'])
                self.window['combo_scene'].update(values=obs_scenes) # シーン一覧を更新

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
            elif ev == 'ノーツ数をTweet':
                self.tweet()

    def check(self):
        while True:
            self.check_db()
            time.sleep(1)

a = Misc()
a.main()
