# oraja_helperとは？
beatorajaのプレーログ及び、その日に叩いたノーツ数をOBSで表示するツールです。  
ゲーム画面のキャプチャではなく、beatorajaのdbファイルを監視してデータを取得しています。  

リザルトからノーツ数を割り出しているので、選曲画面での空打ちがカウントされず、正確なノーツ数が出ます。  
(pg+gr+gd+bd+見逃しprのみ加算)

OBSにこういう感じのやつが出せます。  
<img width="558" alt="Image" src="https://github.com/user-attachments/assets/3b032369-8eb9-49a4-84f2-6735e1685803" />

OBSソースの自動制御を行うこともできます。  
選曲画面/プレイ画面/リザルト画面のキャプチャ画像を登録することで、どんなスキンを使っていてもシーン検出ができます。  
(~~それどころか、beatoraja以外の音ゲーでも動く気がします~~)  
詳しくは[wiki](https://github.com/dj-kata/oraja_helper/wiki/OBS%E9%80%A3%E6%90%BA%E6%A9%9F%E8%83%BD%E3%81%AE%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参照してください。

配信画面風ビュー(whole_layout.html)、成果まとめビュー(receipt.html)、OBS自動制御の動作例(動画)  
https://x.com/cold_planet_/status/1964573250895434226

# 設定方法
1. [releaseページ](https://github.com/dj-kata/oraja_helper/releases)から一番上のoraja_helper.zipをDLし、好きなフォルダに解凍する
2. oraja_helper.exeを実行する
3. メニューバー->settingsよりbeatorajaのパス(本体、プレーヤーフォルダ)を指定する
4. 必要に応じて、beatorajaの過去ログを取得する。(月のノーツ数計算などに利用可能だが、連奏した曲などは取得不可)
5. 必要に応じて、ツイート設定を変更する。
6. 必要に応じて、難易度表選択の欄で表示したくない難易度表のチェックを外す。
7. OBSに情報表示用HTMLをドラッグ&ドロップで挿入する。(ソース→追加→ブラウザからでも出来ます)  - 配信画面を想定したレイアウトを使いたい場合はwhole_layout.htmlを利用(幅1920，高さ1080)
  - プレーログ表示を追加する場合はtoday_result.htmlを利用(幅2000,高さ1500)
  - 統計情報ビューを追加する場合はinfo_detailed.htmlまたはinfo_grid.htmlを利用
  - その日の成果まとめビューを追加する場合はreceipt.htmlを利用(幅2400，高さ3000)
7. シーン(選曲、プレー、リザルト)ごとにOBSソースやシーンを自動制御したい場合は[wiki](https://github.com/dj-kata/oraja_helper/wiki/OBS%E9%80%A3%E6%90%BA%E6%A9%9F%E8%83%BD%E3%81%AE%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参考に設定する。一度上記設定を行っていれば、それ以降はoraja_helper.exeを実行するだけでOKですメイン画面に```db state: OK```と出ていれば動いています。  
<img width="546" alt="Image" src="https://github.com/user-attachments/assets/4d13ade7-aa34-4e66-8e12-5d0e7bf0aa76" />

beatorajaのパス設定は以下のようになっていればOKです。
playerフォルダはdbファイルが入っているフォルダを指定してください。  
<img width="591" alt="Image" src="https://github.com/user-attachments/assets/405c5d73-de60-41e7-81be-790acf61df70" />

自動ツイート設定により、oraja_helper終了時にブラウザ上で以下のようなツイート画面が出ます。  
こちらの機能は```メニューバー内のTweet->daily```からも利用できます。  
※playtime(プレイ画面のみの合計時間)はOBS制御設定からプレイ画面の判定条件を登録した場合のみ表示されます。
<img width="588" alt="Image" src="https://github.com/user-attachments/assets/6d1de99d-d022-4f6f-97ec-eda0c6c0d56b" />

各ビューで表示対象とする難易度表を指定することもできます。
<img width="432" alt="Image" src="https://github.com/user-attachments/assets/2a726cfc-793f-4385-9264-4615c63bef39" />

# 各HTMLファイルについて
仕様上、OBSのブラウザソース以外では表示できないので注意。
各ファイルのサンプルを以下に示す。推奨サイズを記載するが、配信画面のレイアウトに合わせて変えるとよいです。

各HTMLファイルではカスタムCSS経由でカスタマイズすることができます。  
対応するソースをダブルクリックしてプロパティを開き、カスタムCSSの欄に記載してください。  
(1行目の```body{ background-color: rgba(0, 0, 0, 0); margin: 0px auto; overflow: hidden; }```は自動で挿入されています。)
<img width="1060" height="916" alt="image" src="https://github.com/user-attachments/assets/7534d532-dc6a-4867-b631-7ccf9b044a48" />

## today_result.html (プレーログ)
幅2000，高さ1500
<img width="557" alt="Image" src="https://github.com/user-attachments/assets/a917bad9-dfe5-4f7c-b410-3fa817184ab9" />

以下のプロパティを設定することで、表示する曲数を変更できます。  
ランプ、スコア、BPが一切更新されなかったプレイを非表示にするための設定も可能です。  
ヘッダ部分(青い部分)の非表示設定も可能です。

```css
:root{
    /*   最大表示曲数を20曲に制限   */
    --num: 20;

    /*   更新のないログを表示しない   */
    --skip-no-update: 1;

    /* 1なら日付、ノーツ数などのヘッダ部を表示、0なら表示しない */
    --enable-header: 1;
}
```

## receipt.html (成果まとめ)
幅2400，高さ3000
<img width="613" alt="Image" src="https://github.com/user-attachments/assets/6b122384-c17b-4aeb-86b4-d93493ddc6fd" />

以下のプロパティを設定することで、ヘッダ部分(青い部分)の非表示設定が可能です。
```css
:root{
    /* 1なら日付、ノーツ数などのヘッダ部を表示、0なら表示しない */
    --enable-header: 1;
}
```

## whole_layout.html (配信画面風レイアウト)
幅1920，高さ1080
<img width="1590" alt="Image" src="https://github.com/user-attachments/assets/01e3111f-3d40-4ae5-a5a7-1b0ae185768a" />

注意:OBS制御設定からプレー画面の登録をしないとplaytime及びpaceが0のままになります。
(0のときはgridを消すように変更する予定)

以下のプロパティを設定することで、右上の時計が指定時刻に光る機能を利用できます。  
```css
:root{
  --enable-flash:1; /* 1なら指定時刻に光る機能を有効にする、0なら無効 */

  /* デフォルトでは23時56分に光るように設定されている。変更したい場合は変更する */
  --flash-hh: 23;
  --flash-mm: 56;
}
```

## info_grid.html (情報ビュー、サイバー調)
幅1920，高さ200(横6列時)
<img width="1308" alt="Image" src="https://github.com/user-attachments/assets/0a6be005-80be-4000-bc6a-ad0e98750c23" />

## info_detailed.html (情報ビュー、シンプルな見た目)
幅1920，高さ160
<img width="1356" alt="Image" src="https://github.com/user-attachments/assets/2add8d33-1227-4192-8e22-08f4e97e0aeb" />

以下のプロパティを設定することで、1行に表示するパネルの数を変更できます。  
```css
:root{
  /* デフォルトでは1行に6列分表示 */
  --grid-columns: 6;
}
```

# その他
今後追加するかもしれない機能
- リザルト画像の自動保存
