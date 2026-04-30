import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import StringIO

# 都道府県リストを定義（並び替え時に使用）
prefectures_order = [
    "北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島",
    "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川",
    "新潟", "富山", "石川", "福井", "山梨", "長野",
    "岐阜", "静岡", "愛知", "三重",
    "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山",
    "鳥取", "島根", "岡山", "広島", "山口",
    "徳島", "香川", "愛媛", "高知",
    "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄"
]


def normalize_prefecture_name(name):
    """
    都道府県名を並び替え用に整える
    例：
    東京都 → 東京
    大阪府 → 大阪
    北海道 → 北海道
    """
    name = str(name).strip()
    name = re.sub(r'\s', '', name)

    if name == "北海道":
        return "北海道"

    return re.sub(r'(都|府|県)$', '', name)


def extract_numeric(value, percent_flag):
    """
    数値・パーセントを整形する関数
    """
    try:
        numeric_value = float(value)

        if percent_flag:
            return format(numeric_value / 100, '.4f')
        elif numeric_value.is_integer():
            return int(numeric_value)
        else:
            return numeric_value

    except (ValueError, TypeError):
        return None


def extract_numeric_by_column(df, column_number):
    """
    指定した列から数値だけを取り出す関数
    """
    column_name = df.columns[column_number]

    first_value = str(df[column_name].iloc[0])
    percent_flag = '%' in first_value

    df[column_name] = df[column_name].apply(
        lambda x: re.search(r'[-+]?\d+(?:,\d+)*(\.\d+)?', str(x))
    )

    df[column_name] = df[column_name].apply(
        lambda x: float(x.group().replace(',', '')) if x else None
    )

    df[column_name] = df[column_name].apply(
        lambda x: extract_numeric(x, percent_flag)
    )


def sort_output_df(output_df, sort_order):
    """
    順位順・都道府県順に並び替える関数
    """
    output_df = output_df.copy()

    prefecture_col_name = output_df.columns[1]

    output_df['都道府県順キー'] = output_df[prefecture_col_name].apply(
        normalize_prefecture_name
    )

    if sort_order == "都道府県順":
        output_df['都道府県順キー'] = pd.Categorical(
            output_df['都道府県順キー'],
            categories=prefectures_order,
            ordered=True
        )

        output_df = output_df.sort_values('都道府県順キー').reset_index(drop=True)

    else:
        output_df = output_df.sort_values('順位').reset_index(drop=True)

    output_df = output_df.drop(columns=['都道府県順キー'])

    return output_df


def fetch_todoran_data(url):
    """
    todo-ran.comからデータを取得してDataFrameにする関数
    """
    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # ページタイトルを取得
    table_title_div = soup.find('div', {'class': 'kiji_title'})

    if table_title_div and table_title_div.contents:
        table_name = table_title_div.contents[0].get_text(strip=True)
    else:
        table_name = 'タイトル取得失敗'

    # テーブル部分を取得
    table = soup.find('div', {'id': 'kiji_table_swap'})

    if not table:
        raise ValueError('テーブルが見つかりませんでした。URLを確認してください。')

    # HTMLテーブルをDataFrameに変換
    df = pd.read_html(StringIO(str(table)))[0]

    # 列名の準備
    original_columns = df.columns.values
    columns_l = []

    # 列名を整える
    if len(original_columns) == 5:
        for i in range(len(original_columns)):
            if df.columns.values[i][0] == df.columns.values[i][1]:
                columns_l.append(df.columns.values[i][0])
            else:
                text1 = str(df.columns.values[i][0])
                text2 = str(df.columns.values[i][1])
                columns_l.append(text1 + '_' + text2)
    else:
        for i in range(len(original_columns)):
            text1 = str(df.columns.values[i][0])
            columns_l.append(text1)

    # 列名の空白を除去
    columns_l = [re.sub(r'\s', '', word) for word in columns_l]

    # 列名を適用
    df.columns = columns_l

    # 順位を数値に変換
    df['順位'] = pd.to_numeric(df['順位'], errors='coerce').fillna(0).astype(int)

    # 数値列を整形
    extract_numeric_by_column(df, 2)

    # 3列目が偏差値でなければ数値抽出
    if len(df.columns) > 3 and df.columns[3] != '偏差値':
        extract_numeric_by_column(df, 3)

    # 上から47行を都道府県データとして取得
    output_df = df.iloc[0:47, :].copy()

    return table_name, output_df


def main():
    st.title('とどらんデータ抽出Webアプリ')
    st.write('URLを入力し、「Submit」ボタンを押すと、対象ページのテーブルを抽出・表示します。')

    col1, col2 = st.columns([4, 1])

    with col1:
        url = st.text_input(
            'URLを入力してください',
            'https://todo-ran.com/t/kiji/16326'
        )

    with col2:
        submitted = st.button("Submit")

    # Submitが押されたときだけデータ取得
    if submitted:
        try:
            table_name, output_df = fetch_todoran_data(url)

            # 取得したデータをsession_stateに保存
            st.session_state['table_name'] = table_name
            st.session_state['output_df'] = output_df

        except requests.exceptions.RequestException as e:
            st.error(f'URLリクエストでエラーが発生しました: {e}')

        except Exception as e:
            st.error(f'エラーが発生しました: {e}')

    # session_stateにデータがある場合は常に表示
    if 'output_df' in st.session_state and 'table_name' in st.session_state:
        table_name = st.session_state['table_name']
        output_df = st.session_state['output_df'].copy()

        st.subheader('アクセスしたページのタイトル')
        st.write(table_name)

        sort_order = st.radio(
            "表示順を選択してください",
            ("順位順", "都道府県順")
        )

        sorted_df = sort_output_df(output_df, sort_order)

        st.subheader('抽出結果（47都道府県）')
        st.dataframe(sorted_df)

        # CSV出力
        csv_data = sorted_df.to_csv(index=False).encode('utf-8-sig')
        filename = f'{table_name}.csv'

        st.download_button(
            label='CSVファイルをダウンロード',
            data=csv_data,
            file_name=filename,
            mime='text/csv'
        )


if __name__ == '__main__':
    main()