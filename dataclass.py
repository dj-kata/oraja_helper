# 難易度表やdb周り
import json
import gzip
import glob
import datetime
import os
import sqlite3
import pandas as pd
from config import Config
from collections import defaultdict

import logging, logging.handlers
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
class DiffTable:
    """難易度表管理用クラス。table以下のgzfileのパースも行う。
    """
    def __init__(self):
        self.table_names = []
        self.nglist = ['BMS Search'] # 読まないテーブル一覧。名前を登録する。
        self.set_config()
        self.parse_bmtfiles()
        self.update_tables()
    
    def set_config(self, config:Config=Config()):
        """設定ファイルを読み込み、各dbfileのパスを更新する。

        Args:
            config (Config, optional): config情報。 Defaults to Config().
        """
        self.config = config
        self.nglist = list(set(self.nglist + config.difftable_nglist))

    def parse_gzfile_to_json(self, filepath) -> json:
        """bmt(gz)ファイルからjsonへパース

        Args:
            filepath (str): 入力ファイルのパス

        Returns:
            json: パース結果
        """
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            return json.load(f)

    def parse_bmtfiles(self):
        tables = [] 
        for f in glob.glob(self.config.oraja_path+'/table/*.bmt'):
            tmp = self.parse_gzfile_to_json(f)
            if 'BMS Search' not in tmp.get('name'):
                self.table_names.append(tmp.get('name'))
            if tmp.get('name') not in self.nglist:
                tables.append(tmp)
            else:
                print(f"parsing: {tables[-1].get('name') or ''}")
        self.tables = tables

    def add_nglist(self, ng:list):
        assert(type(ng) == list)
        for name in ng:
            if name not in self.nglist:
                self.nglist.append(name)
                self.parse_bmtfiles()
                self.update_tables()

    def update_tables(self):
        print(f'難易度表管理用dictを更新します')
        songtable = {} # hash to (difficulty,title)
        difftable = defaultdict(list)

        for t in self.tables:
            for f in t['folder']:
                for song in f['songs']:
                    md5 = song.get('sha256') or song.get('md5')
                    difftable[md5].append(f['name'])
                    songtable[md5] = (f['name'], song.get('title'))
        self.songtable = songtable
        self.difftable = difftable

    def search_from_hash(self, hash:str) -> list:
        return self.difftable.get(hash) or None

class OneResult: 
    def __init__(self, title=None, difficulties=None
                 ,one_difficulty=None
                 ,score=None, pre_score=0
                 ,bp=None, pre_bp=999999
                 ,lamp=None, pre_lamp = 0
                 ,score_rate=None, date=None, judge=None, sha256=None, length=None, notes=None
                ):
        self.title = title
        self.difficulties = difficulties
        self.one_difficulty = one_difficulty
        self.score = score
        self.pre_score = pre_score
        self.bp = bp
        self.pre_bp = pre_bp
        self.lamp = lamp
        self.pre_lamp = pre_lamp
        self.score_rate = score_rate
        self.date = date
        self.judge = judge
        self.sha256 = sha256
        self.length = float(length/1000) if length is not None else None
        self.notes = notes 
        self.density = self.notes / self.length if (self.notes is not None) and (self.length is not None) else None

    def __eq__(self, other):
        if not isinstance(other, OneResult):
            return NotImplemented
        diff_date = abs(self.date - other.date)
        if type(diff_date) is datetime.timedelta:
            diff_date = diff_date.total_seconds()
        return (self.title == other.title) and (self.sha256 == other.sha256) and (self.score == other.score) and (self.bp == other.bp) and (self.lamp == other.lamp) and (diff_date<10.0)
    
    def __lt__(self, other):
        if not isinstance(other, OneResult):
            return NotImplemented
        return self.date < other.date

    def disp(self):
        print(f"title:{self.title}", end=',')
        print(f"difficulties:{self.difficulties}", end=',')
        print(f"lamp:{self.lamp}, score:{self.score} ({self.score_rate}%)", end=',')
        print(f"bp:{self.bp}", end=',')
        print(f"notes:{self.notes}, density={self.density:.2f}", end='\n')

class TodayResults:
    """OneResultの配列を管理するクラス。xml出力とかもやる。
    """
    def __init__(self):
        self.results = []
        self.updates = [] # resultsは全て記録するが、こちらは同じ曲ならマージする
        self.start_time = datetime.datetime.now()
        self.playtime = datetime.timedelta(seconds=0)

    def merge_results(self, pre:OneResult, new:OneResult) -> OneResult:
        assert(pre.sha256 == new.sha256)
        ret = pre
        ret.lamp = max(pre.lamp, new.lamp)
        ret.bp = min(pre.bp, new.bp)
        if new.score > pre.score:
            ret.score = new.score
            ret.score_rate = new.score_rate
            ret.judge = new.judge
        return ret

    def add_result(self, result:OneResult):
        if result not in self.results:
            self.results.append(result)
            hashes = [tmp.sha256 for tmp in self.updates]
            if result.sha256 in hashes:
                pre = self.results.pop(hashes.index(result.sha256))
                new = self.merge_results(pre, result)
                self.updates.append(new)
            else:
                self.updates.append(result)

    def write_history_xml(self):
        sum_judge = [0, 0, 0, 0, 0, 0]
        for r in self.results:
            for i in range(6):
                sum_judge[i] += r.judge[i]
        score_rate = 0 # total
        notes = sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]
        if (notes) > 0:
            score_rate = 100*(sum_judge[0]*2+sum_judge[1]) / (sum_judge[0]+sum_judge[1]+sum_judge[2]+sum_judge[3]+sum_judge[4]) / 2
        with open('history.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Items>\n")
            f.write(f"    <date>{self.start_time.year}/{self.start_time.month:02d}/{self.start_time.day:02d}</date>\n")
            f.write(f'    <notes>{notes}</notes>\n')
            f.write(f'    <total_score_rate>{score_rate:.2f}</total_score_rate>\n')
            f.write(f'    <playcount>{len(self.results)}</playcount>\n')
            # f.write(f'    <last_notes>{self.last_notes}</last_notes>\n')
            if self.playtime.seconds == 0:
                f.write(f'    <playtime>0</playtime>\n') # HTML側で処理しやすくしている
                f.write(f'    <pace>0</pace>\n')
            else:
                f.write(f'    <playtime>{str(self.playtime).split(".")[0]}</playtime>\n')
                f.write(f'    <pace>{int(3600*self.notes/self.playtime.seconds)}</pace>\n')

            for r in self.results:
                title_esc = r.title.replace('&', '&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&apos;')
                f.write(f'    <Result>\n')
                # f.write(f'        <lv>{r.difficulties[0]}</lv>\n')
                f.write(f'        <lv>{",".join(r.difficulties)}</lv>\n')
                f.write(f'        <title>{title_esc}</title>\n')
                f.write(f'        <lamp>{r.lamp}</lamp>\n')
                f.write(f'        <pre_lamp>{r.pre_lamp}</pre_lamp>\n')
                f.write(f'        <score>{r.score}</score>\n')
                f.write(f'        <pre_score>{r.pre_score}</pre_score>\n')
                f.write(f'        <bp>{r.bp}</bp>\n')
                f.write(f'        <pre_bp>{r.pre_bp}</pre_bp>\n')
                if r.pre_score > 0:
                    f.write(f'        <diff_score>{r.score-r.pre_score:+}</diff_score>\n')
                else: # 初プレイ時は空白
                    f.write(f'        <diff_score></diff_score>\n')
                if r.pre_bp < 100000:
                    f.write(f'        <diff_bp>{r.bp-r.pre_bp:+}</diff_bp>\n')
                else: # 初プレイ時は空白
                    f.write(f'        <diff_bp></diff_bp>\n')
                f.write(f'        <score_rate>{float(r.score_rate):.2f}</score_rate>\n')
                f.write(f'        <date>{datetime.datetime.fromtimestamp(r.date)}</date>\n')
                f.write('    </Result>\n')
            f.write("</Items>\n")


    def write_updates_xml(self):
        pass

class DataBaseAccessor:
    def __init__(self):
        self.difftable = DiffTable() # 難易度情報を取得するために持っておく
        self.today_results = TodayResults()
        self.db_updated_date = {} # 各dbfileの最終更新日時を覚えておく、必要なものだけ読み込む
        self.set_config()
        self.reload_db()

    def is_valid(self):
        """すべての設定ファイルが存在すればTrue,無効な設定があればFalseを返す

        Returns:
            bool: 判定結果
        """
        ret = True
        ret &= os.path.exists(self.db_score)
        ret &= os.path.exists(self.db_scoredatalog)
        ret &= os.path.exists(self.db_scorelog)
        ret &= os.path.exists(self.db_songdata)
        ret &= os.path.exists(self.db_songinfo)
        return ret

    def set_config(self, config:Config=Config()):
        """設定ファイルを読み込み、各dbfileのパスを更新する。

        Args:
            config (Config, optional): config情報。 Defaults to Config().
        """
        self.config = config
        self.difftable.set_config(config)
        self.db_songdata     = os.path.join(self.config.oraja_path, 'songdata.db')
        self.db_songinfo     = os.path.join(self.config.oraja_path, 'songinfo.db')
        self.db_score        = os.path.join(self.config.player_path, 'score.db')
        self.db_scorelog     = os.path.join(self.config.player_path, 'scorelog.db')
        self.db_scoredatalog = os.path.join(self.config.player_path, 'scoredatalog.db')

    def load_one_dbfile(self, dbpath:str, dbname:str) -> pd.DataFrame:
        """1つのdbfileをロードする。最終更新時刻を用いて、更新のないものはスキップする。
        返り値は代入時に受け側でケアする必要がある。

        Args:
            dbpath (str): dbfileのパス
            dbname (str): dbfile内で対象とするtable名

        Returns:
            pd.DataFrame: 読み出した結果
        """
        current = os.path.getmtime(dbpath)
        last_updated_time = self.db_updated_date.get(dbname) or 0.0
        if current > last_updated_time:
            conn = sqlite3.connect(dbpath)
            self.db_updated_date[dbname] = current
            print(f"dbfile reloaded. (dbpath:{dbpath}, dbname:{dbname})")
            return pd.read_sql(f'SELECT * FROM {dbname}', conn)
        # else:
        #     print(f'dbfile is not updated! skipped.')

        """dbを一通りリロード
        """
    def reload_db(self) -> bool:
        """dbfileを一通りリロードする

        Returns:
            bool: score.dbに更新があった場合True
        """
        tmp_df_scorelog = self.load_one_dbfile(self.db_scorelog, 'scorelog')
        self.df_scorelog = tmp_df_scorelog if tmp_df_scorelog is not None else self.df_scorelog
        tmp_df_score = self.load_one_dbfile(self.db_score, 'score')
        self.df_score = tmp_df_score if tmp_df_score is not None else self.df_score
        tmp_df_scoredatalog = self.load_one_dbfile(self.db_scoredatalog, 'scoredatalog')
        self.df_scoredatalog = tmp_df_scoredatalog if tmp_df_scoredatalog is not None else self.df_scoredatalog

        tmp_df_songdata = self.load_one_dbfile(self.db_songdata, 'song')
        self.df_songdata = tmp_df_songdata if tmp_df_songdata is not None else self.df_songdata
        tmp_df_songinfo = self.load_one_dbfile(self.db_songinfo, 'information')
        self.df_songinfo = tmp_df_songinfo if tmp_df_songinfo is not None else self.df_songinfo

        #return (tmp_df_scorelog is not None) or (tmp_df_score is not None) or (tmp_df_scoredatalog is not None) or (tmp_df_songdata is not None) or (tmp_df_songinfo is not None)
        return tmp_df_score is not None

    def parse(self, tmpdat) -> OneResult:
        """df_dataの1エントリを受けてOneResultに格納して返す。難易度の取得もここで行う。

        Args:
            tmpdat (DataFrame): 1プレイ分のデータ。判定はepg,lpgなどに入っている。

        Returns:
            OneResult: parseの結果
        """
        if type(tmpdat['sha256']) == str:
            hsh = tmpdat['sha256']
        else:
            hsh=tmpdat['sha256'].iloc[0]
        tmpsc = self.df_score[self.df_score['sha256'] == hsh].tail(1)
        tmp = self.df_scorelog[self.df_scorelog['sha256'] == hsh].tail(1)
        #pre_score = tmp.oldscore.iloc[0]
        notes = tmpsc.notes.iloc[0]
        logger.debug(f'hsh:{hsh}\n')
        info = self.df_songdata[self.df_songdata['sha256'] == hsh].tail(1)
        logger.debug(f'type(info):{type(info)}')
        if type(info) == pd.DataFrame:
            logger.debug(f'info.shape:{info.shape}')
        if info.shape[0] > 0:
            title = info.title.iloc[0]
            length = info.length.iloc[0]
        else:
            title = info.title
            length = info.length
            logger.debug(f'shape[0]==0!!!, title={title}')
        lampid = tmpdat.clear#.iloc[0]
        judge = [
            tmpdat.epg+tmpdat.lpg,
            tmpdat.egr+tmpdat.lgr,
            tmpdat.egd+tmpdat.lgd,
            tmpdat.ebd+tmpdat.lbd,
            tmpdat.epr+tmpdat.lpr,
            tmpdat.ems+tmpdat.lms,
        ]
        score = judge[0]*2+judge[1]
        bp    = judge[3]+judge[4]+judge[5]
        bp   += (notes-judge[0]-judge[1]-judge[2]-judge[3]-judge[4]) # 完走していない場合は引く
        score_rate = f"{score/notes*100/2:.2f}"
        ret = OneResult(title=title, lamp=lampid, score=score, score_rate=score_rate, judge=judge, bp=bp, length=length, sha256=hsh, date=tmpdat.date, notes=notes)
        ret.difficulties = sorted(list(set(self.difftable.difftable[info.sha256.iloc[0]]+self.difftable.difftable[info.md5.iloc[0]])))
        if tmpdat['playcount'] > 1:
            ret.pre_score = tmp.oldscore.max()
            ret.pre_bp = tmp.oldminbp.min()
            ret.pre_lamp = tmp.oldclear.max()
        return ret
        #return title, lampid, score, pre_score, score_rate, tmpdat.date, judge

    def read_one_result(self):
        idx = len(self.df_scoredatalog) - 1
        tmp_song = self.df_scoredatalog.iloc[idx, :]
        tmp_result = self.parse(tmp_song)
        tmp_result.disp()
        self.today_results.add_result(tmp_result)

    def read_old_results(self):
        """起動前のリザルトをpushする
        """
        cur_time = datetime.datetime.now() - datetime.timedelta(hours=self.config.autoload_offset)
        print(cur_time)
        log = self.df_scoredatalog[self.df_scoredatalog['date'] > cur_time.timestamp()]
        for index,row in log.iterrows():
            tmp_result = self.parse(row)
            self.today_results.add_result(tmp_result)
            tmp_result.disp()

        
if __name__ == '__main__':
    acc = DataBaseAccessor()
    table_names = [t['name'] for t in acc.difftable.tables]
    acc.read_old_results()

    # num = 25 
    # for i in range(num):
    #     idx = len(acc.df_scoredatalog) - num + i
    #     scdatalog = acc.df_scoredatalog.iloc[idx, :]
    #     tmp_result = acc.parse(scdatalog)
    #     acc.today_results.add_result(tmp_result)
    #     tmp_result.disp()

    acc.today_results.write_history_xml()