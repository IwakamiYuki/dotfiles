# Mermaid Guardian - リファレンスガイド

詳細な検証ルール、エラーパターン、修正ロジックを記載します。

## 目次

1. [エラーカテゴリー](#エラーカテゴリー)
2. [検証ルール](#検証ルール)
3. [エラーパターン詳解](#エラーパターン詳解)
4. [修正ロジック](#修正ロジック)

---

## エラーカテゴリー

Mermaid エラーは 3 つの根本原因に分類されます。

### カテゴリー 1：構文エラー

**症状**：「SyntaxError」「Unexpected token」

**原因**：
- 括弧・括選の不一致
- キーワードのタイプミス
- 不正なシンボル（矢印の形式など）

**修正難度**：🟢 低

**例**：
```
❌ sequenceDiagram
   A->>B メッセージ  ← ":" が抜けている

✅ sequenceDiagram
   A->>B: メッセージ
```

### カテゴリー 2：セマンティックエラー

**症状**：「Invalid syntax」「Unknown participant」「Invalid state transition」

**原因**：
- 図種に不適な要素（例：sequenceDiagram での状態遷移）
- 宣言されていない参加者の参照
- 矛盾する構造（例：デッドロック）

**修正難度**：🟡 中

**例**：
```
❌ sequenceDiagram
   participant A
   A->>B: メッセージ  ← B が宣言されていない

✅ sequenceDiagram
   participant A
   participant B
   A->>B: メッセージ
```

### カテゴリー 3：レンダリングエラー

**症状**：図が表示されない、崩れている、SVG がおかしい

**原因**：
- 複雑すぎて処理できない（ノード数、ネストレベル）
- 文法上は正しいが、Mermaid の内部状態管理が失敗
- ブラウザレンダリングエンジンの限界超過

**修正難度**：🔴 高

**例**：
```
❌ sequenceDiagram
   participant A
   participant B
   participant C
   A->>A: 自己メッセージ（内部処理）
   B->>B: 自己メッセージ（内部処理）
   rect rgb(200,100,100)
       C->>A: メッセージ
       A->>B: メッセージ
       B->>B: 自己メッセージ
       Note over A: 説明
   end
   ← レンダリング失敗。複数の自己メッセージと rect の組み合わせ

✅ sequenceDiagram
   participant A
   participant B
   participant C
   A->>B: メッセージ
   B->>C: メッセージ
   activate C
   Note over C: 内部処理
   C-->>B: 応答
   deactivate C
```

---

## 検証ルール

### Rule 1：Participant 数（sequenceDiagram）

**ルール**：4 人以下

**理由**：
- 5 人以上 = レイアウト計算が指数関数的に複雑化
- 参加者間の相互作用が可視化しきれない
- 画面幅を超過する可能性

**チェック**：
```
participant 宣言の数を数える
Expected: ≤ 4
```

**修正策**：
```
① グループ化（複数の Participant を 1 つに統合）
② 複数図に分割（フロー 1、フロー 2 など）
③ 重要な参加者のみに絞る
```

**例**：

```
❌ 5 人（エラー）
participant Client
participant Frontend
participant API
participant Database
participant Cache

✅ グループ化（推奨）
participant Client
participant Backend
participant Database
Note: Backend = Frontend + API + Cache
```

### Rule 2：自己メッセージの禁止（sequenceDiagram）

**ルール**：A->>A: メッセージは禁止。代わりに `Note over` を使用

**理由**：
- Mermaid が自己メッセージの垂直線をうまく処理できない
- 複数あるとレンダリング失敗の原因になる

**修正策**：
```
A->>A: 内部処理  →  Note over A: 内部処理
```

詳細なエラー例は [パターン 1](#パターン-1sequencediagram-での複数自己メッセージ) を参照

### Rule 3：activation/deactivate の明示化（sequenceDiagram）

**ルール**：関数呼び出しの深いネストには `activate`/`deactivate` を明示

**理由**：
- 暗黙の呼び出しスタックはレンダリング失敗につながる
- activation で処理フローが明確になる

### Rule 4：rect ブロックのシンプル化（sequenceDiagram）

**ルール**：rect 内は制御構造を混在させない。複雑になったら別の図に分割

**理由**：
- rect + Note + 複数メッセージ + 自己メッセージ = Mermaid が内部状態を失う
- 線形フロー + activate で十分表現できる

詳細な修正例は [パターン 2](#パターン-2rect-内での制御構造混在) を参照

### Rule 5：ノード数（graph TD/LR）

**ルール**：10 個以下

**理由**：
- 11+ ノード = グラフアルゴリズムの複雑性が指数増加
- ポジショニング計算（Sugiyama）が失敗しやすい
- 可読性が著しく低下

**チェック**：
```
ノード宣言の数を数える
Expected: ≤ 10
```

**修正策**：
```
① ノードを削除（本当に必要か再検討）
② グループ化（サブグラフ化）
③ 複数図に分割（フロー 1、フロー 2）
```

### Rule 6：ノード名の明確性（graph TD/LR）

**ルール**：曖昧な名前は禁止。具体的で 1～3 語

**理由**：
- 「超える」「影響」などの曖昧な名前は、状態なのか動作なのか不明確
- 図の意図が読み手に伝わらない
- 保守が困難

**チェック**：
```
各ノード名について：
1. 日本語 1 語で済むか？→ OK
2. 2 語で説明できるか？→ OK
3. 3 語以上必要か？→ 名前を短縮、説明は Node サブテキストで
4. 曖昧性あり？（「超える」「影響」）→ 具体化

Examples:
❌ 超える / 影響を受ける / 問題発生
✅ 制限超過 / 検証失敗 / トークン無効
```

**修正策**：
```
ノード名を具体的に、主語 + 述語で構成
Before: ["超える"]
After: ["時刻制限を超過"]
```

### Rule 7：エッジラベルの簡潔性（graph TD/LR）

**ルール**：1～2 語。3 語以上は不可

**理由**：
- 長いラベルは SVG を拡大させ、レイアウトを崩す
- 接続ロジックが複雑に見える

**チェック**：
```
各エッジラベルについて：
単語数を数える
Expected: ≤ 2 words
```

**修正策**：
```
長いラベル → 短縮 + 説明は外部テキストで補完
Before: "ユーザーが入力値を変更した場合"
After: "変更あり"（外部テキスト：「ユーザーが入力値を変更した場合」）
```

### Rule 8：DAG 構造（graph TD/LR）

**ルール**：単純な有向非環グラフ。複雑な循環は避ける

**理由**：
- 循環 = ポジショニング計算がオーバーフロー
- 複雑な多対多接続 = レイアウトが予測不可能

**チェック**：
```
1. サイクルがあるか検出
2. 入次数＆出次数を数える
Expected: 入次数 ≤ 2、出次数 ≤ 2
```

**修正策**：
```
① サイクルを削除（ワークフローに反映）
② 多対多接続をシンプルに（中間ノード挿入）
③ 複数図に分割
```

---

## エラーパターン詳解

### パターン 1：sequenceDiagram での複数自己メッセージ

**症状**：图無表示、または崩れた表示

**原因**：
```
sequenceDiagram
    participant A
    participant B
    A->>A: 処理 1
    A->>B: メッセージ
    B->>B: 処理 2
```

の場合、Mermaid が A->>A と B->>B の両方の垂直線を管理できない。

**修正**：

```
sequenceDiagram
    participant A
    participant B
    Note over A: 処理 1
    A->>B: メッセージ
    Note over B: 処理 2
```

**なぜ修正が正しいか**：
- Note over は「垂直線」ではなく「テキストボックス」
- レンダリングが単純化される
- 内部処理の意図が明確

### パターン 2：rect 内での制御構造混在

**症状**：`SyntaxError: Unexpected token` または図無表示

**原因**：
```
sequenceDiagram
    participant A
    participant B
    participant C
    rect rgb(100,200,100)
        Note over A: 説明
        A->>B: メッセージ 1
        B->>B: 自己メッセージ ← 問題1
        rect rgb(100,100,200) ← 問題2
            B->>C: メッセージ 2
        end
    end
```

ネストした rect + 自己メッセージ + Note = パーサーが混乱

**修正**：

```
sequenceDiagram
    participant A
    participant B
    participant C
    A->>B: メッセージ 1
    activate B
    Note over B: 内部処理
    B->>C: メッセージ 2
    C-->>B: 応答
    deactivate B
```

**なぜ修正が正しいか**：
- rect を削除 → 線形フロー化
- activate/deactivate で階層を表現 → Mermaid が確実に処理
- Note で説明を補足 → 視覚的情報量は維持

### パターン 3：graph での曖昧なノード設計

**症状**：図は表示されるが、意図が伝わらない。レビューで「このノード何？」と質問される

**原因**：
```
graph TD
    A["ユーザーが端末時刻を操作"]
    B["Time.realtimeSinceStartup"]
    C["超える"]
    D["TimeProvider が監視"]
    A -->|やっても| B
    B -->|戻らない| C
    C -->|ため| D
```

ノード C の「超える」が状態か動作か不明確。エッジラベルも曖昧（「戻らない」「ため」）。

**修正**：

```
graph TD
    A["ユーザーが時刻を改変"]
    B["Time.realtimeSinceStartup"]
    C["単調増加を保証"]
    A -->|やっても| B
    B -->|保証| C
```

**なぜ修正が正しいか**：
- ノード C を「超える」→「単調増加を保証」に明確化
- エッジラベルを「戻らない」→「保証」に単純化
- ノード数を削減（3 個 → 3 個ですっきり）
- 因果関係がシンプル

---

## よくある修正パターン集

### パターン 4：Participant 数が多すぎる

**症状**：図が横に広がりすぎて読みにくい、またはレンダリング失敗

**原因**：
```
sequenceDiagram
    participant Client
    participant Frontend
    participant API
    participant Database
    participant Cache
    participant Logger
```

6 人以上の参加者は Mermaid がレイアウトしきれない。

**修正**：グループ化
```
sequenceDiagram
    participant Client
    participant Backend
    participant DB

    Client->>Backend: リクエスト
    Backend->>DB: クエリ
    Note over Backend: キャッシュ確認、ログ出力
    DB-->>Backend: 結果
    Backend-->>Client: レスポンス
```

---

## トラブルシューティングガイド

図がレンダリングできないときの判断フロー：

```
1. エラーメッセージが出ている？
   ├→ Yes: エラーメッセージ索引を参照
   └→ No: 以下へ進む

2. 図が全く表示されていない？
   ├→ Yes: 以下を確認
   │   ├→ sequenceDiagram: Rule 1, 2 (参加者数、自己メッセージ)
   │   ├→ graph: Rule 5, 8 (ノード数、循環構造)
   │   └→ 状態図: Rule 9 (状態数)
   └→ No: 見た目が崩れている。以下へ

3. 見た目は表示されているが崩れている？
   ├→ sequenceDiagram なら rect, activate 確認
   ├→ graph なら ノード数やラベル長を確認
   └→ 修正がわからなければ /mermaid-guardian post-check で相談
```

---

## エラーメッセージ索引

| エラーメッセージ | 原因 | 対応 Rule |
|-----------------|------|----------|
| "Unexpected token" | 構文エラー（括弧不一致など） | 構文確認 |
| "Unknown participant" | 宣言されていない参加者 | Rule 1 |
| "Invalid state transition" | 状態遷移の定義ミス | Rule 9 |
| "Error rendering" | 図が複雑すぎる | Rule 1-9 全般 |
| （何も出ない、表示されない） | レンダリング失敗 | ノード数、自己メッセージ確認 |

---

## 詳細チェックリスト

### sequenceDiagram

- [ ] **Participant 数**: 4 人以下
- [ ] **自己メッセージ**: A->>A: がない（すべて Note over に置き換え）
- [ ] **activation/deactivate**: ネスト深が 2 以上なら明示している
- [ ] **rect ブロック**: 内部に異なる制御構造を混在させていない
- [ ] **メッセージ数**: 20 個以下

### graph TD/LR

- [ ] **ノード数**: 10 個以下
- [ ] **ノード名**: 1～3 語、具体的で曖昧でない
- [ ] **エッジラベル**: 1～2 語（3 語以上は不可）
- [ ] **構造**: DAG（有向非環グラフ）。複雑な循環がない
- [ ] **入出次数**: 各ノードの入次数・出次数が 2 以下（スパゲッティ化を避ける）

### stateDiagram-v2

- [ ] **状態数**: 7 個以下
- [ ] **状態名**: 明確で曖昧でない
- [ ] **遷移**: すべての遷移が実現可能で到達不可能な状態がない

---

## 参考リソース

- **Mermaid 公式ドキュメント**：https://mermaid.js.org/
- **Syntax 詳細**：https://mermaid.js.org/intro/
- **Live Editor**：https://mermaid.live/
