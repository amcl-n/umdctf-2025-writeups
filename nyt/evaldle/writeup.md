とりあえずncで接続してみると、`Guess: `という表示とともに入力を求められる。

```shell
% nc challs.umdctf.io 31601
Guess: a
Invalid guess.
Guess: aaaaaaaaaaa
Invalid guess.
Guess: AIUEO
⬛🟩⬛⬛⬛
🟥🟥🟥🟥🟥
Guess: ABCDE
⬛⬛⬛⬛⬛
🟥🟥🟥🟥🟥
Guess:
```

いわゆるwordleを模したゲームのようだ。pythonスクリプトが配布されているので覗いてみる。

```python
#!/usr/local/bin/python
f = open('flag.txt').read()

target = 'SIGMA'

while True:
    guess = input("Guess: ")
    if len(guess) != 5:
        print("Invalid guess.")
        continue
    for j in range(5):
        if target[j] == guess[j]:
            print('🟩', end='')
        elif guess[j] in target[j]:
            print('🟨', end='')
        else:
            print('⬛', end='')
    print('')
    try:
        exec(guess)
        print('🟩🟩🟩🟩🟩')
    except:
        print("🟥🟥🟥🟥🟥")
```

`SIGMA`という文字列を正解としたWordleになっているが、そこは本質ではない。

flagに関わる部分の挙動を要約すると、「標準入力で入れた5文字（以内）の文字列を`exec()`で評価するので、それを利用して変数`f`にstrとして格納されているflagを探れ」ということになる。

`print(f)`が実行できるなら即終了だが、もちろん文字数オーバー。

「`exec()`の評価時にエラーが起きるか否かはレスポンスから知ることができる」という重要な挙動を利用した策として、`f[50]`などを入れてIndexErrorが起きるか否かを観察することで、`f`の文字列長を知る、というのはすぐに思いつくが、それ以上の情報は得られそうにない。

5文字でできることなんてほとんどないので、一つずつ可能性を検討していくと、`a="U"`のような変数代入が可能であることに気づく。`while`文で代入結果は次に引き継がれるので、

```python
a= ""
b="U"
a=a+b
b="M"
a=a+b
b="D"
a=a+b
...
```

といった入力を繰り返していくことで、変数`a`に任意の文字列を格納できそうだ。

`a`に任意の文字列を入れられるなら、それを`f`と良い感じに比較することで`f`を特定できるのでは？という発想に至る。結論として、以下で`a`と`f`の大小関係を知ることができる。

```python
c=a<f  # 辞書順で a < f であるか否かが bool として c に格納される
1 / c  # bool は int のサブクラスなので、 ZeroDivisionErrorが発生するか否かで c の True/False を把握可能
```

ここまでくれば、後はflag文字列を前から順に総当たり的に決定していくスクリプトをゴリゴリ作っていけばOK。1回の評価のために何回もリクエストを送る必要があるのでやや時間がかかるが、最終的に以下のようなflagが得られる。

`UMDCTF{that_took_a_lot_more_than_six_guesses}`
