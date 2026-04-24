import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import StringIO

# 都道府県リストを定義（並び替え時に使用）
prefectures_order = [
    "北海道","青森","岩手","宮城","秋田","山形","福島","茨城","栃木","群馬","埼玉","千葉","東京","神奈川",
    "新潟","富山","石川","福井","山梨","長野","岐阜","静岡","愛知","三重","滋賀","京都","大阪","兵庫","奈良",
    "和歌山","鳥取","島根","岡山","広島","山口","徳島","香川","愛媛","高知","福岡","佐賀","長崎","熊本","大分",
    "宮崎","鹿児島","沖縄"
]

# 列番号を指定して数値のみを取り出す関数
def extract_numeric_by_column(df, column_number):
    column_name = df.columns[column_number]
    # 1行目に'%'が含まれているかどうかで、パーセント表示か判定
    if df[column_name].str.contains('%').iloc[0]:
        parsent = True
    else:
        parsent = False
    # 正規表現を使って数値を検索
    df[column_name] = df[column_name].apply(lambda x: re.search(r'[-+]?\d+(?:,\d+)*(\.\d+)?', str(x)))
    # 数値データをfloatとして適用
    df[column_name] = df[column_name].apply(lambda x: float(x.group().replace(',', '')) if x else None)
    # 整数の場合はintに変換
    df[column_name] = df[column_name].apply(lambda x: extract_numeric(x, parsent))

# 数値を抽出する関数
def extract_numeric(value, parsent_flag):
    try:
        numeric_value = float(value)
        if parsent_flag:
            # %表記の場合は100で割った小数に変換
            return format(numeric_value / 100, '.4f')
        elif numeric_value.is_integer():
            # 値が整数の場合は整数に変換
            return int(numeric_value)
        else:
            # 値が小数の場合はそのまま
            return numeric_value
    except (ValueError, TypeError):
        # 数値以外の場合は None を返す
        return None

def main():
    st.title('とどらんデータ抽出Webアプリ')
    st.write('URLを入力し、「Submit」ボタンを押すと、対象ページのテーブルを抽出・表示します。')

    # URL入力欄とボタンを横並びに配置
    col1, col2 = st.columns([4,1])
    with col1:
        url = st.text_input('URLを入力してください', 'https://todo-ran.com/t/kiji/16326')
    with col2:
        submitted = st.button("Submit")

    if submitted:
        try:
            # データを取得
            response = requests.get(url)
            response.raise_for_status()

            # BeautifulSoupでパース
            soup = BeautifulSoup(response.text, 'html.parser')

            # ページタイトル（記事タイトル）を取得
            table_title_div = soup.find('div', {'class': 'kiji_title'})
            if table_title_div and table_title_div.contents:
                table_name = table_title_div.contents[0].get_text(strip=True)
            else:
                table_name = 'タイトル取得失敗'

            st.subheader('アクセスしたページのタイトル')
            st.write(table_name)

            # テーブルを指定
            table = soup.find('div', {'id': 'kiji_table_swap'})
            if not table:
                st.error('テーブルが見つかりませんでした。URLを確認してください。')
                return

            # データフレームに変換
            df = pd.read_html(StringIO(str(table)))[0]

            # 列名の準備
            df_1 = df.columns.values
            columns_l = []

            # 列名を整える
            if len(df_1) == 5:
                # 5列の場合、総数と人口10万人あたりを分離
                for i in range(len(df_1)):
                    if df.columns.values[i][0] == df.columns.values[i][1]:
                        columns_l.append(df.columns.values[i][0])
                    else:
                        text1 = str(df.columns.values[i][0])
                        text2 = str(df.columns.values[i][1])
                        columns_l.append(text1 + '_' + text2)
            else:
                # それ以外の場合はそのまま
                for i in range(len(df_1)):
                    text1 = str(df.columns.values[i][0])
                    columns_l.append(text1)

            # スペースを除去
            columns_l = [re.sub(r'\s', '', word) for word in columns_l]
            # 列名を適用
            df.columns = columns_l

            # 順位のデータ型をintに変換
            df['順位'] = pd.to_numeric(df['順位'], errors='coerce').fillna(0).astype(int)

            # 列番号を指定して数値のみを取り出す（3列以上ある想定）
            # 2列目（インデックス2）が数値系
            extract_numeric_by_column(df, 2)

            # 3列目が偏差値でなければ数値抽出
            if df.columns[3] != '偏差値':
                extract_numeric_by_column(df, 3)

            # 47都道府県を抜き出し（上から47行が都道府県データ想定）
            output_df = df.iloc[0:47, :].copy()

            # 都道府県順 or 順位順を選択させる
            sort_order = st.radio("表示順を選択してください", ("順位順", "都道府県順"))

            # 2列目が都道府県名と想定して並び替え
            prefecture_col_name = output_df.columns[1]  # 例: '都道府県'
            if sort_order == "都道府県順":
                # カテゴリ型に変換してソート
                output_df[prefecture_col_name] = pd.Categorical(
                    output_df[prefecture_col_name],
                    categories=prefectures_order,
                    ordered=True
                )
                output_df = output_df.sort_values(prefecture_col_name).reset_index(drop=True)
            else:
                # 順位順
                output_df = output_df.sort_values('順位').reset_index(drop=True)

            st.subheader('抽出結果（47都道府県）')
            st.dataframe(output_df)

            # CSV出力ボタン
            csv_data = output_df.to_csv(index=False).encode('utf-8-sig')
            filename = f'{table_name}.csv'
            st.download_button(
                label='CSVファイルをダウンロード',
                data=csv_data,
                file_name=filename,
                mime='text/csv'
            )

        except requests.exceptions.RequestException as e:
            st.error(f'URLリクエストでエラーが発生しました: {e}')
        except Exception as e:
            st.error(f'エラーが発生しました: {e}')

if __name__ == '__main__':
    main()
