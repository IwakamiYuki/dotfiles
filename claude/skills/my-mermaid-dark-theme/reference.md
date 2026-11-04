# Mermaid ダークテーマ リファレンスガイド

## Quick Copy-Paste テンプレート

各テンプレートをコピーして、必要に応じて内容を編集してください。

### 最小構成フローチャート

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryTextColor': '#FFFFFF', 'primaryBorderColor': '#FFB347', 'lineColor': '#666666', 'fontSize': '14px'}}}%%
flowchart TD
  A[ステップ1] --> B[ステップ2] --> C[終了]
```

### 意思決定フローチャート

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryTextColor': '#FFFFFF', 'primaryBorderColor': '#FFB347', 'lineColor': '#666666'}}}}%%
flowchart TD
  A{判定} -->|YES| B[分岐A]
  A -->|NO| C[分岐B]
  B --> D[結果]
  C --> D
```

### エラーハンドリングフロー

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
flowchart TD
  A[処理実行] --> B{成功?}
  B -->|Yes| C[完了]:::success
  B -->|No| D[エラー処理]:::error
  D --> E[ログ出力]:::warning

  classDef success fill:#51CF66,stroke:#40C057,color:#000000,font-weight:bold
  classDef error fill:#FF6B6B,stroke:#EE5A52,color:#FFFFFF,font-weight:bold
  classDef warning fill:#FFD700,stroke:#FFC107,color:#000000,font-weight:bold
```

### API 通信シーケンス

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryTextColor': '#FFFFFF', 'primaryBorderColor': '#FFB347', 'lineColor': '#666666', 'fontSize': '12px'}}}}%%
sequenceDiagram
  participant Front as フロントエンド
  participant API as API サーバー
  participant DB as データベース

  Front->>API: 1. リクエスト送信
  activate API
  API->>DB: 2. データ取得
  activate DB
  DB-->>API: 3. データ返却
  deactivate DB
  API-->>Front: 4. レスポンス返却
  deactivate API
```

### マイクロサービスアーキテクチャ

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
sequenceDiagram
  participant UI as User Interface
  participant GW as API Gateway
  participant Auth as Auth Service
  participant User as User Service
  participant Payment as Payment Service

  UI->>GW: ユーザー登録
  GW->>Auth: 認証確認
  GW->>User: ユーザー作成
  GW->>Payment: 決済初期化
```

### クラス継承関係

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
classDiagram
  class Animal {
    +String name
    +int age
    +void eat()
    +void sleep()
  }

  class Dog {
    +void bark()
  }

  class Cat {
    +void meow()
  }

  Animal <|-- Dog
  Animal <|-- Cat
```

### 注文処理のステートマシン

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
stateDiagram-v2
  [*] --> 注文待機
  注文待機 --> 注文確認: 注文作成
  注文確認 --> 支払待機: 確認完了
  支払待機 --> 発送準備: 支払完了
  発送準備 --> 発送完了: 発送
  発送完了 --> [*]
  支払待機 --> キャンセル: キャンセル
  キャンセル --> [*]
```

### プロジェクト3ヶ月計画

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'fontSize': '12px', 'gridLineStartPadding': '350'}}}}%%
gantt
  title Q1 プロジェクト計画
  dateFormat YYYY-01-DD
  section 計画
  リサーチ :a1, 2025-01-01, 14d
  設計 :a2, 2025-01-15, 14d
  section 開発
  バックエンド :crit, 2025-01-29, 30d
  フロントエンド :crit, 2025-01-29, 35d
  section QA
  統合テスト :a4, 2025-03-04, 14d
  リリース :a5, 2025-03-18, 7d
```

### アプリケーション構成図（マインドマップ）

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
mindmap
  root((アプリケーション))
    フロントエンド
      UI Component
      State Management
      API Client
    バックエンド
      API Server
      Database
      Cache
    インフラ
      Container
      Cloud Services
      Monitoring
```

---

## よくある質問 (FAQ)

### Q: 色がテンプレートと異なります
**A**: Markdown ビューアーの設定を確認してください。
- VS Code: テーマを「Dark」に設定
- GitHub: 自動ダークモード対応（ブラウザの設定確認）
- その他エディタ: 深色テーマを有効化

### Q: テキストが重なります
**A**: `fontSize` を減らしてください。
```yaml
'fontSize': '12px'  # デフォルト: 16px
```

### Q: グラデーション色を使いたい
**A**: ダークモード向けなので単色推奨。複数色が必要な場合は `classDef` で使い分け。

### Q: 外部スタイルシートを使えますか？
**A**: Mermaid 内の `%%{init: {...}}%%` のみで完結。外部 CSS は Mermaid レンダリングでは反映されません。

### Q: PNG/SVG でエクスポートするときはどうする?
**A**: ブラウザのスクリーンショット機能または Mermaid の CLI でエクスポート。色設定は Mermaid 図に埋め込まれます。

---

## カラー選択フローチャート

ノードの色を決める際：

```
目的は？
├─ 成功・完了状態 → #51CF66 (緑)
├─ エラー・失敗状態 → #FF6B6B (赤)
├─ 警告・注意状態 → #FFD700 (黄)
├─ 情報・参考 → #4DABF7 (青)
└─ 通常・メイン → #FF8C00 (オレンジ) ← dotfiles 統一色
```

---

## テーマ切り替え

### ライトモード（参考用）

```yaml
%%{init: {
  'theme': 'default',
  'themeVariables': {
    'primaryColor': '#FFE5CC',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#FF8C00',
    'fontSize': '16px'
  }
}}%%
```

> 注: このリポジトリはダークモード前提のため、ライトモードはサポート外です。

---

## パフォーマンス考慮事項

- **大規模フローチャート**: 30 ノード以上は複数図に分割推奨
- **シーケンス図**: 参加者が 10 人以上は複雑度が上がるため、複数図への分割を検討
- **複雑なガントチャート**: 15 タスク以上は描画が遅延することがあるため、期間で分割
