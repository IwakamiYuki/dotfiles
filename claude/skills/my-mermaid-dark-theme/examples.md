# Mermaid ダークテーマ 実践例集

実装パターン別の Mermaid コード例を集めました。

## システム設計例

### マイクロサービスアーキテクチャ図

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347', 'lineColor': '#666666'}}}}%%
flowchart TB
  Client["🌐 クライアント"]

  subgraph API["API Gateway"]
    GW["ゲートウェイ"]
  end

  subgraph Services["マイクロサービス"]
    Auth["認証サービス"]:::auth
    User["ユーザーサービス"]:::service
    Order["注文サービス"]:::service
    Payment["決済サービス"]:::payment
  end

  subgraph DB["データストア"]
    AuthDB["認証DB"]
    UserDB["ユーザーDB"]
    OrderDB["注文DB"]
  end

  Client --> GW
  GW --> Auth
  GW --> User
  GW --> Order
  Auth --> AuthDB
  User --> UserDB
  Order --> OrderDB
  Order --> Payment

  classDef auth fill:#4DABF7,stroke:#339AF0,color:#000000,font-weight:bold
  classDef service fill:#FF8C00,stroke:#FFB347,color:#FFFFFF,font-weight:bold
  classDef payment fill:#51CF66,stroke:#40C057,color:#000000,font-weight:bold
```

### デプロイメントパイプライン

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
flowchart LR
  Code["コード提交"]:::code
  Test["テスト実行"]:::test
  Build["ビルド"]:::build
  Stage["ステージング"]:::deploy
  Review{"レビュー通過?"}:::decision
  Prod["本番環境"]:::prod
  Monitor["監視"]:::monitor

  Code --> Test
  Test --> Build
  Build --> Stage
  Stage --> Review
  Review -->|Yes| Prod
  Review -->|No| Code
  Prod --> Monitor
  Monitor -->|異常| Rollback["ロールバック"]:::error
  Rollback --> Code

  classDef code fill:#4DABF7,stroke:#339AF0,color:#000000
  classDef test fill:#FFD700,stroke:#FFC107,color:#000000
  classDef build fill:#51CF66,stroke:#40C057,color:#000000
  classDef deploy fill:#FF8C00,stroke:#FFB347,color:#FFFFFF
  classDef prod fill:#FF6B6B,stroke:#EE5A52,color:#FFFFFF
  classDef decision fill:#FFA500,stroke:#FFB347,color:#000000
  classDef monitor fill:#4DABF7,stroke:#339AF0,color:#000000
  classDef error fill:#FF6B6B,stroke:#EE5A52,color:#FFFFFF
```

---

## ワークフロー例

### ユーザー登録フロー

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
sequenceDiagram
  actor User
  participant Frontend as フロントエンド
  participant Backend as バックエンド
  participant Auth as 認証サービス
  participant Email as メール送信

  User->>Frontend: 登録フォーム入力
  Frontend->>Backend: POST /register
  activate Backend

  Backend->>Auth: ユーザー作成
  activate Auth
  Auth-->>Backend: ユーザーID返却
  deactivate Auth

  Backend->>Email: 確認メール送信
  activate Email
  Email-->>Backend: 送信完了
  deactivate Email

  Backend-->>Frontend: 登録成功
  deactivate Backend

  Frontend->>User: 確認ページ表示
```

### 注文処理フロー

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
flowchart TD
  Start["注文開始"]
  CartCheck{"カート内容確認"}
  AddressInput["配送先入力"]
  PaymentInput["支払い情報入力"]
  ReviewOrder["注文確認"]
  ProcessPayment["支払い処理"]
  PaymentSuccess{"支払い成功?"}
  CreateOrder["注文作成"]
  SendEmail["確認メール送信"]
  ShipmentPrepare["発送準備"]
  End["完了"]
  Error["エラー処理"]

  Start --> CartCheck
  CartCheck -->|OK| AddressInput
  CartCheck -->|NG| Error
  AddressInput --> PaymentInput
  PaymentInput --> ReviewOrder
  ReviewOrder --> ProcessPayment
  ProcessPayment --> PaymentSuccess
  PaymentSuccess -->|Yes| CreateOrder
  PaymentSuccess -->|No| Error
  CreateOrder --> SendEmail
  SendEmail --> ShipmentPrepare
  ShipmentPrepare --> End
  Error -->|Retry| Start
  Error -->|Cancel| End

  classDef start fill:#51CF66,stroke:#40C057,color:#000000,font-weight:bold
  classDef process fill:#FF8C00,stroke:#FFB347,color:#FFFFFF,font-weight:bold
  classDef decision fill:#FFA500,stroke:#FFB347,color:#000000,font-weight:bold
  classDef error fill:#FF6B6B,stroke:#EE5A52,color:#FFFFFF,font-weight:bold
  classDef end fill:#4DABF7,stroke:#339AF0,color:#000000,font-weight:bold

  class Start start
  class End end
  class PaymentSuccess decision
  class Error error
  class CartCheck decision
```

---

## データベーススキーマ例

### E-R 図（クラス図で表現）

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
classDiagram
  class Users {
    int id PK
    string email UK
    string name
    string password_hash
    datetime created_at
    datetime updated_at
  }

  class Orders {
    int id PK
    int user_id FK
    decimal total_amount
    string status
    datetime created_at
  }

  class OrderItems {
    int id PK
    int order_id FK
    int product_id FK
    int quantity
    decimal price
  }

  class Products {
    int id PK
    string name
    text description
    decimal price
    int stock
  }

  Users "1" --> "*" Orders : has
  Orders "1" --> "*" OrderItems : contains
  OrderItems "*" --> "1" Products : references
```

---

## リアルタイムシステムの状態遷移

### WebSocket チャットの状態管理

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
stateDiagram-v2
  [*] --> 接続前

  接続前 --> 接続中: connect() 呼び出し

  接続中 --> 接続済み: WebSocket 確立
  接続中 --> 接続失敗: 失敗

  接続失敗 --> 再接続待機: wait(3s)
  再接続待機 --> 接続中: retry

  接続済み --> メッセージ送信: user types
  接続済み --> メッセージ受信: message arrive

  メッセージ送信 --> 接続済み: sent
  メッセージ受信 --> 接続済み: processed

  接続済み --> 切断処理: close()
  切断処理 --> [*]

  接続済み --> エラー: connection lost
  エラー --> 再接続待機: reconnect
```

---

## テスト戦略図

### テストピラミッド構成

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
flowchart TD
  Base["📊 テストピラミッド"]

  subgraph Unit["単体テスト（Unit Tests）"]
    U1["関数単位のテスト"]
    U2["300+ テスト"]
  end

  subgraph Integration["統合テスト（Integration Tests）"]
    I1["複数コンポーネント間"]
    I2["50-100 テスト"]
  end

  subgraph E2E["E2E テスト（E2E Tests）"]
    E1["ユーザーシナリオ"]
    E2["10-20 テスト"]
  end

  Base --> Unit
  Unit --> Integration
  Integration --> E2E

  classDef unit fill:#51CF66,stroke:#40C057,color:#000000,font-weight:bold
  classDef integration fill:#FF8C00,stroke:#FFB347,color:#FFFFFF,font-weight:bold
  classDef e2e fill:#FF6B6B,stroke:#EE5A52,color:#FFFFFF,font-weight:bold

  class U1,U2 unit
  class I1,I2 integration
  class E1,E2 e2e
```

---

## インフラストラクチャ設計

### CI/CD パイプライン（ガントチャート）

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'fontSize': '12px'}}}}%%
gantt
  title CI/CD パイプライン実行タイムライン
  dateFormat HH:mm:ss
  axisFormat %H:%M:%S

  section Stage
  git push :s1, 00:00:00, 5s
  lint check :s2, 00:00:05, 10s
  unit test :s3, 00:00:15, 20s
  build docker :s4, 00:00:35, 30s
  push registry :s5, 00:01:05, 10s
  deploy staging :s6, 00:01:15, 15s
  integration test :s7, 00:01:30, 20s
  smoke test :s8, 00:01:50, 10s
  ready :crit, s8, 00:02:00, 1s
```

---

## ドキュメント構造

### プロジェクトドキュメン構成図

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'primaryColor': '#FF8C00', 'primaryBorderColor': '#FFB347'}}}}%%
mindmap
  root((プロジェクトドキュメント))
    📖 ガイド
      インストール
      クイックスタート
      チュートリアル
    🏗️ アーキテクチャ
      システム設計
      モジュール構成
      データフロー
    🔧 API
      REST エンドポイント
      Webhook
      認証
    🧪 テスト
      ユニットテスト
      統合テスト
      E2E テスト
    🚀 デプロイ
      環境構築
      本番運用
      トラブルシューティング
```

---

## カスタマイズテンプレート

任意のテーマカラーで使いたい場合のテンプレート：

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'primaryColor': '#YOUR_HEX_COLOR',
    'primaryTextColor': '#FFFFFF',
    'primaryBorderColor': '#YOUR_BORDER_HEX',
    'lineColor': '#666666',
    'secondBkgColor': '#2D2D2D',
    'fontSize': '14px'
  }
}}%%
flowchart TD
  A[カスタム色] --> B[自由に変更]
```

ファイル内のすべての `#FF8C00` を目的の色に置換してください。
