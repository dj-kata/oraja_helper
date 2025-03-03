# oraja_helperとは？
beatorajaのプレーログ及び、その日に叩いたノーツ数をOBSで表示するツールです。  
ゲーム画面のキャプチャではなく、beatorajaのdbファイルを監視してデータを取得しています。  

リザルトからノーツ数を割り出しているので、選曲画面での空打ちがカウントされず、正確なノーツ数が出ます。  
(pg+gr+gd+bd+見逃しprのみ加算)

OBSにこういう感じのやつが出せます。
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/0f597d3c-27cf-48bb-8f08-5314028c195b)

v.1.0.6からOBSソースの自動制御にも対応しました。  
選曲画面などのキャプチャ画像を登録することで、どんなスキンを使っていてもシーン検出ができます。  
(~~それどころか、beatoraja以外の音ゲーでも動く気がします~~)  
詳しくは[wiki](https://github.com/dj-kata/oraja_helper/wiki/OBS%E9%80%A3%E6%90%BA%E6%A9%9F%E8%83%BD%E3%81%AE%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参照してください。

プレーログ(today_result.html)+統計情報(info.html)+OBS制御の動作例(動画)  
https://x.com/cold_planet_/status/1791741023158460618

# 設定方法
1. [releaseページ](https://github.com/dj-kata/oraja_helper/releases)から一番上のoraja_helper.zipをDLし、好きなフォルダに解凍する
2. oraja_helper.exeを実行する
3. メニューバー->settingsよりbeatorajaのパス(本体、プレーヤーフォルダ)を指定する
5. 必要に応じて、```終了時にツイート画面を開く```をチェックする。
4. 必要に応じて、表示したい難易度表のURLを追加することもできます。reloadボタンを押すことで反映されます。
5. OBSにtoday_result.html(プレーログ表示)をD&Dする (-> 幅2000,高さ1500)
6. 必要に応じてOBSにinfo.html(統計情報表示)をD&Dする (-> 幅1200,高さ162)
7. シーン(選曲、プレー、リザルト)ごとにOBSソースやシーンを自動制御したい場合は[wiki](https://github.com/dj-kata/oraja_helper/wiki/OBS%E9%80%A3%E6%90%BA%E6%A9%9F%E8%83%BD%E3%81%AE%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参考に設定する。

初期設定後に一度再起動しないとdbの変更が取得されないかもしれません(調査中)

※一度上記設定を行っていれば、それ以降はoraja_helper.exeを実行するだけでOKです

メイン画面にOKと出ていれば動いています。  
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/7acb4c0f-2039-42d8-8bfc-1390a830df85)

beatorajaのパス設定は以下のようになっていればOKです。
playerフォルダはdbファイルが入っているフォルダを指定してください。  
![image](https://github.com/dj-kata/ytlive_helper/assets/61326119/6f7ee76e-77a6-4635-ac02-a3ecc102f403)

自動ツイート設定をすると、oraja_helper終了時にブラウザ上で以下のようなツイート画面が出ます。  
こちらの機能は```メニューバー内のTool->ノーツ数をTweet```からも利用できます。  
![image](https://github.com/user-attachments/assets/b30eb7f1-6740-4321-88e6-0e218a734269)  
※playtime(プレイ画面のみの合計時間)はOBS制御設定からプレイ画面の判定条件を登録した場合のみ表示されます。

また、OBSでtoday_result.htmlのカスタムCSSに以下のプロパティを設定することで、表示する曲数を変更できます。

```
:root{
--num: 20;
}
```

today_result.htmlは幅2000,高さ1500ぐらいを想定しています。
(高さはもっと大きくすることもできます)

info.htmlでは以下のような情報が表示されます。  
幅1200,高さ162ぐらいを想定しています。  
(幅はレイアウトに応じて変更してください)
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/fda9ce59-a35f-498f-b1cd-3e015520283e)

# その他
OBS連携機能も追加するかもしれません  
- リザルト自動保存
- OBSソースの表示・非表示自動制御
  - 選曲画面、プレー画面、リザルト画面の条件(マッチングに使う画像と領域)をユーザが登録する形を想定
