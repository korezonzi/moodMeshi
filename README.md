# 🍽️ MoodMeshi

**気分を入力するだけで、AIが最適な食事を提案してくれるアプリ**

[![Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?logo=vercel)](https://moodmeshi.vercel.app)
[![Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?logo=render)](https://render.com)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Slack](https://img.shields.io/badge/Slack%20Bot-対応-4A154B?logo=slack)](https://api.slack.com/)
[![Slides](https://img.shields.io/badge/紹介スライド-GitHub%20Pages-ff6b35?logo=github)](https://korezonzi.github.io/moodMeshi/)

🔗 **本番 URL**: https://moodmeshi.vercel.app  
📊 **紹介スライド**: https://korezonzi.github.io/moodMeshi/

---

## 📖 目次

- [MoodMeshiとは？](#-moodmeshiとは)
- [紹介スライド](#-紹介スライド)
- [2つの使い方](#-2つの使い方)
- [システム全体像](#-システム全体像)
- [AIエージェントの仕組み](#-aiエージェントの仕組み)
- [Slackボットの仕組み](#-slackボットの仕組み)
- [技術スタック](#-技術スタック)
- [ディレクトリ構成](#-ディレクトリ構成)
- [ローカルでの起動方法](#-ローカルでの起動方法)
- [環境変数の設定](#-環境変数の設定)
- [デプロイ方法](#-デプロイ方法)
- [テストの実行](#-テストの実行)
- [データの流れ（詳細）](#-データの流れ詳細)
- [よくある質問](#-よくある質問)

---

## 🤔 MoodMeshiとは？

MoodMeshi は、**今の気分を伝えるだけで、AIが料理を提案してくれる**アプリです。

「疲れた」「元気いっぱい」「落ち込んでいる」など、気分を入力すると…

✅ 複数の AI エージェントが **並行して分析**  
✅ **栄養・季節・楽天レシピ**の3つの観点を組み合わせ  
✅ あなたの気分にぴったりな **6つのレシピ提案**を返します

> 💡 **初めての方へ**: このアプリは「WebサイトとSlackボット」の2種類の使い方があります。
> どちらも同じAIエンジンを使っています。

---

## 📊 紹介スライド

サービスの概要・アーキテクチャ・技術スタックをまとめた紹介スライドを公開しています。

👉 **https://korezonzi.github.io/moodMeshi/**

| スライド | 内容                               |
| -------- | ---------------------------------- |
| 01       | タイトル                           |
| 02       | 課題提起 — 「今日何食べよう」問題  |
| 03       | 解決策 — MoodMeshiとは             |
| 04       | Web入力画面（UIモック）            |
| 05       | Web結果画面（UIモック）            |
| 06       | Slackボット画面と使い方            |
| 07       | 3フェーズ処理アーキテクチャ        |
| 08       | 並行処理の仕組み（タイムライン図） |
| 09       | 技術スタック                       |
| 10       | 設計のこだわり3選                  |
| 11       | まとめ                             |

> ⌨️ `→` キーまたは `Space` で次のスライドへ。右上「🎬 発表モード」で全画面表示になります。

---

## 🌐 2つの使い方

### 1️⃣ Webアプリ（ブラウザで使う）

```
https://moodmeshi.vercel.app
```

気分を入力してボタンを押すだけ。リアルタイムで処理の進捗が表示されます。

```
┌─────────────────────────────────────┐
│   🍽️ MoodMeshi                      │
│                                     │
│  今日の気分を教えてください          │
│  ┌─────────────────────────────┐    │
│  │ 疲れていて甘いものが食べたい │    │
│  └─────────────────────────────┘    │
│                                     │
│  😮‍💨疲れた  💪元気  😔落ち込み ...  │
│                                     │
│  ┌──────────────────────────┐       │
│  │  料理を提案してもらう 🔍  │       │
│  └──────────────────────────┘       │
└─────────────────────────────────────┘
```

### 2️⃣ Slackボット（チームで使う）

Slackのチャンネルで `/meshi` コマンドを入力するだけで提案が届きます。

```
あなた: /meshi 疲れた
         ↓
MoodMeshi Bot:
┌─────────────────────────────────────┐
│ 🍽️ お疲れさまです！栄養をチャージ  │
│    できる料理をご提案します 🍲      │
│                                     │
│ 1位: 豚の生姜焼き                   │
│   ⏱ 20分 | 💰 300円以内            │
│   推奨理由: ビタミンB1が豊富で...   │
│   [レシピを見る ↗]                 │
│                                     │
│ 2位: なめこと豆腐の味噌汁           │
│   ...                               │
│  [他の3候補も見る ▼] [処理ログ 📋] │
└─────────────────────────────────────┘
```

---

## 🗺️ システム全体像

```mermaid
graph TB
    subgraph ユーザー側
        U1[👤 ブラウザユーザー]
        U2[👥 Slackユーザー]
    end

    subgraph デプロイ環境
        Vercel["☁️ Vercel\n(Webアプリ専用)"]
        Render["☁️ Render\n(Slackボット含む)"]
    end

    subgraph アプリケーション["FastAPI アプリケーション"]
        Web["🌐 Webルート\n/  /suggest"]
        Slack["💬 Slackエンドポイント\n/slack/events"]
    end

    subgraph AIエンジン["🤖 AI処理エンジン（共通）"]
        ORC["🎼 Orchestrator\n(指揮者)"]
        P1["Phase 1\n気分分析\nClaude Sonnet"]
        P2A["🔍 Recipe Hunter\nClaude Haiku"]
        P2B["🥗 Nutrition Advisor\nClaude Haiku"]
        P2C["🌸 Seasonal Sommelier\nClaude Haiku"]
        P3["Phase 3\n最終提案生成\nClaude Sonnet"]
    end

    subgraph 外部サービス
        Rakuten["🛒 楽天レシピAPI"]
        Claude["🧠 Anthropic Claude API"]
    end

    U1 -->|気分を入力| Vercel
    U2 -->|/meshi コマンド| Slack
    Vercel --> Web
    Render --> Web
    Render --> Slack
    Web --> ORC
    Slack --> ORC
    ORC --> P1 --> P2A & P2B & P2C --> P3
    P2A <-->|レシピ検索| Rakuten
    P1 & P3 <-->|テキスト生成| Claude
    P2A & P2B & P2C <-->|テキスト生成| Claude
```

---

## 🤖 AIエージェントの仕組み

MoodMeshiは「**3フェーズ処理**」という仕組みでレシピを提案します。

### 処理フロー

```
ユーザーの入力: "仕事で疲れた、胃に優しいものが食べたい"
                          │
                          ▼
╔══════════════════════════════════════════════════╗
║  Phase 1 │ 気分分析                              ║
║  Claude Sonnet が入力を解析                       ║
║  ─────────────────────────────                   ║
║  気分キーワード：["疲れた", "胃に優しい"]         ║
║  食材キーワード：["消化に良い", "柔らかい"]        ║
║  対象カテゴリ：汁物(33), おかず野菜(35)           ║
╚══════════════════════════╤═══════════════════════╝
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
╔══════════════╗  ╔══════════════╗  ╔══════════════╗
║ 🔍 Recipe    ║  ║ 🥗 Nutrition ║  ║ 🌸 Seasonal  ║
║   Hunter     ║  ║   Advisor    ║  ║  Sommelier   ║
║ ──────────── ║  ║ ──────────── ║  ║ ──────────── ║
║ 楽天APIで    ║  ║ 栄養素を     ║  ║ 季節の旬の   ║
║ レシピ検索   ║  ║ 分析・提案   ║  ║ 食材を推奨   ║
║   ↕API       ║  ║ Claude Haiku ║  ║ Claude Haiku ║
║ 楽天レシピ   ║  ╚══════════════╝  ╚══════════════╝
╚══════════════╝        │                 │
          │             │                 │
          └──────────────┴─────────────────┘
                          │
                          ▼
╔══════════════════════════════════════════════════╗
║  Phase 3 │ 最終提案生成                          ║
║  Claude Sonnet が3つの情報を統合                  ║
║  ─────────────────────────────                   ║
║  ✅ レシピ情報 + 栄養情報 + 季節情報              ║
║  ✅ 気分に合わせたパーソナライズ                  ║
║  ✅ 推奨理由・栄養ポイント・旬の食材を添えて      ║
║  → 6つのレシピ提案を生成                         ║
╚══════════════════════════════════════════════════╝
```

### Phase 2 は並行処理（同時に動く！）

3つのエージェントは**同時並行**で動くため、待ち時間が短くなっています。

```
時間の流れ →

Phase 1:  [気分分析──────]
                          ↓
Phase 2:  [レシピ検索─────────]
          [栄養分析────────]    ← 3つ同時に動く
          [季節分析────────]
                               ↓
Phase 3:                  [最終提案────────]
```

---

## 💬 Slackボットの仕組み

### コマンドの使い方

| 操作               | 方法                                        |
| ------------------ | ------------------------------------------- |
| 気分を指定して提案 | `/meshi 疲れた`                             |
| モーダルから入力   | `/meshi`（引数なし）                        |
| 残り3候補を表示    | 結果メッセージの「他の3候補も見る ▼」ボタン |
| 処理ログを見る     | 結果メッセージの「処理ログ 📋」ボタン       |

### Slackボットの処理フロー

```mermaid
sequenceDiagram
    participant User as 👤 Slackユーザー
    participant Slack as 💬 Slack
    participant Bot as 🤖 MoodMeshi Bot
    participant AI as 🧠 AIエンジン

    User->>Slack: /meshi 疲れた
    Slack->>Bot: イベント送信

    alt テキストあり
        Bot->>Slack: 処理中メッセージを投稿
        Bot->>AI: バックグラウンドで処理開始
        AI-->>Bot: 処理の進捗を通知
        Bot->>Slack: 進捗状況を更新（⏳→✅）
        AI-->>Bot: 最終結果
        Bot->>Slack: 結果メッセージに更新
    else テキストなし
        Bot->>Slack: 入力モーダルを表示
        User->>Slack: 気分を入力して送信
        Slack->>Bot: モーダル送信イベント
        Bot->>Slack: 処理中メッセージを投稿
        Bot->>AI: バックグラウンドで処理開始
        AI-->>Bot: 最終結果
        Bot->>Slack: 結果メッセージに更新
    end

    User->>Slack: 「他の3候補も見る ▼」クリック
    Slack->>Bot: ボタンアクション
    Bot->>Slack: 全6候補を表示に更新
```

### モーダルの入力画面（テキストなしで /meshi を実行）

```
┌─────────────────────────────────────────┐
│  今日の気分を教えて 🍽️               × │
├─────────────────────────────────────────┤
│                                         │
│  気分・今の状態                         │
│  ┌───────────────────────────────────┐  │
│  │ 例: 疲れているけど元気を出したい  │  │
│  └───────────────────────────────────┘  │
│  自由に入力してください                  │
│                                         │
│  または気分チップから選ぶ               │
│  ┌──────────────────────────────────┐   │
│  │ 気分を選ぶ（任意）       ▼      │   │
│  │  😫 疲れた                        │   │
│  │  😊 元気                          │   │
│  │  😟 落ち込んでいる                │   │
│  │  🥵 暑い  🥶 寒い                 │   │
│  │  🍰 甘いものが食べたい            │   │
│  └──────────────────────────────────┘   │
│                                         │
│  [キャンセル]      [提案してもらう 🔍]  │
└─────────────────────────────────────────┘
```

---

## 🛠️ 技術スタック

### 全体構成

```
┌─────────────────────────────────────────────────────┐
│                  フロントエンド                       │
│  Jinja2テンプレート + HTMX + CSS                     │
│  （チップUI・SSEリアルタイム進捗表示）                │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────▼────────────────────────────────┐
│                  バックエンド                         │
│  FastAPI (Python 3.12) + Uvicorn                     │
│  Pydantic v2 (データバリデーション)                  │
└──────┬────────────────────────────────┬──────────────┘
       │ httpx (非同期)                  │ slack-bolt
┌──────▼──────┐                 ┌───────▼──────────────┐
│  楽天       │                 │  Slack API           │
│  レシピAPI  │                 │  (Bolt Framework)    │
└─────────────┘                 └──────────────────────┘
       │                                │
┌──────▼────────────────────────────────▼──────────────┐
│                Anthropic Claude API                   │
│  Sonnet: Phase1(気分分析)・Phase3(最終提案生成)        │
│  Haiku:  Phase2の各エージェント（軽量・高速）          │
└──────────────────────────────────────────────────────┘
```

### 主要ライブラリ一覧

| カテゴリ              | ライブラリ              | 役割                    |
| --------------------- | ----------------------- | ----------------------- |
| **Webフレームワーク** | FastAPI + Uvicorn       | APIサーバー             |
| **LLM**               | anthropic >= 0.40       | Claude API クライアント |
| **Slackボット**       | slack-bolt >= 1.21      | Slack イベント処理      |
| **HTTPクライアント**  | httpx + aiohttp         | 非同期HTTP通信          |
| **テンプレート**      | Jinja2                  | HTMLレンダリング        |
| **バリデーション**    | Pydantic v2             | データ型チェック        |
| **設定管理**          | pydantic-settings       | 環境変数の読み込み      |
| **テスト**            | pytest + pytest-asyncio | テスト実行              |

### Claudeモデルの使い分け

```
Phase 1 (気分分析)           Claude Sonnet
Phase 3 (最終提案生成)   ──▶  ・高精度・複雑な推論が得意
                              ・コストは高め

Phase 2 (3つのエージェント)   Claude Haiku
  - Recipe Hunter        ──▶  ・軽量・高速・低コスト
  - Nutrition Advisor         ・シンプルなタスクに最適
  - Seasonal Sommelier
```

---

## 📁 ディレクトリ構成

```
moodMeshi/
│
├── 📄 README.md               # このファイル
├── 📄 requirements.txt        # Pythonパッケージ一覧
├── 📄 .env.example            # 環境変数のサンプル
├── 📄 vercel.json             # Vercelデプロイ設定
├── 📄 render.yaml             # Renderデプロイ設定
├── 📄 pytest.ini              # テスト設定
├── 📄 runtime.txt             # Pythonバージョン指定
│
├── 📂 api/
│   └── index.py               # Vercelエントリーポイント
│
├── 📂 app/                    # メインアプリケーション
│   ├── main.py                # FastAPIルート定義・アプリ起動
│   ├── config.py              # 環境変数管理（Pydantic Settings）
│   ├── slack_bot.py           # Slackボット（コマンド・モーダル・ボタン）
│   ├── slack_formatter.py     # Slack Block Kit ビルダー
│   │
│   ├── 📂 agents/             # AIエージェント群
│   │   ├── orchestrator.py    # 3フェーズ処理の指揮者
│   │   ├── recipe_hunter.py   # 楽天APIでレシピ検索（Haiku + Tool Use）
│   │   ├── nutrition_advisor.py  # 栄養アドバイス生成（Haiku）
│   │   ├── seasonal_sommelier.py # 旬の食材推奨（Haiku）
│   │   └── types.py           # Pydanticデータモデル定義
│   │
│   ├── 📂 tools/
│   │   └── rakuten_recipe.py  # 楽天レシピAPIクライアント
│   │
│   ├── 📂 templates/          # Jinja2 HTMLテンプレート
│   │   ├── base.html          # ベーステンプレート
│   │   ├── index.html         # トップページ（入力フォーム）
│   │   └── result.html        # 結果表示ページ
│   │
│   └── 📂 static/
│       └── style.css          # スタイルシート
│
├── 📂 tests/                  # テストスイート
│   ├── conftest.py            # テスト共通設定
│   ├── test_orchestrator.py   # Orchestratorのテスト
│   ├── test_recipe_hunter.py  # Recipe Hunterのテスト
│   ├── test_nutrition_advisor.py
│   ├── test_seasonal_sommelier.py
│   └── test_rakuten_api.py    # 楽天APIのテスト
│
├── 📂 scripts/
│   └── test_slack_endpoint.py # Slackエンドポイントの動作確認スクリプト
│
└── 📂 presentation/           # プレゼンテーション用
    ├── agent.py
    ├── generate.py
    └── 📂 slides/
        └── index.html         # 紹介スライド（GitHub Pages で公開中）
```

---

## 🚀 ローカルでの起動方法

### 必要なもの

事前に以下のアカウント・APIキーを取得してください。

| 必要なもの                        | 取得場所                                                      | 用途            |
| --------------------------------- | ------------------------------------------------------------- | --------------- |
| **Python 3.12+**                  | [python.org](https://www.python.org/)                         | 実行環境        |
| **Anthropic API Key**             | [console.anthropic.com](https://console.anthropic.com/)       | Claude AI       |
| **楽天アプリID**                  | [webservice.rakuten.co.jp](https://webservice.rakuten.co.jp/) | レシピ検索      |
| **Slack Bot Token** _(任意)_      | [api.slack.com](https://api.slack.com/apps)                   | Slackボット     |
| **Slack Signing Secret** _(任意)_ | 同上                                                          | Slackボット認証 |

> ⚠️ Slack関連の設定は省略可能です。設定しない場合、Webアプリのみ動作します。

---

### ① リポジトリをクローン

```bash
git clone https://github.com/korezonzi/moodMeshi.git
cd moodMeshi
```

### ② 仮想環境を作成・有効化

```bash
# 仮想環境を作成
python -m venv .venv

# 有効化（Mac/Linux）
source .venv/bin/activate

# 有効化（Windows）
.venv\Scripts\activate
```

### ③ 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### ④ 環境変数を設定

```bash
# サンプルをコピー
cp .env.example .env

# エディタで開いて各キーを設定
```

### ⑤ アプリを起動

```bash
uvicorn api.index:app --reload
```

ブラウザで http://localhost:8000 を開くとアプリが表示されます。

---

## 🔑 環境変数の設定

`.env` ファイルに以下を設定してください。

```env
# ── 必須 ──────────────────────────────────────
# Anthropic Claude API キー（Webアプリ・Slackボット共通）
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx

# 楽天Webサービス アプリID
RAKUTEN_APP_ID=xxxxxxxxxxxxxxxxxxxx

# 楽天Webサービス アクセスキー（ブラウザからのAPI呼び出し時のみ必要）
RAKUTEN_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxx

# ── 任意（Slackボットを使う場合のみ必要）──────
# Slack Bot Token（xoxb-で始まる文字列）
SLACK_BOT_TOKEN=xoxb-your-bot-token-here

# Slack Signing Secret（Slackアプリ設定画面で確認）
SLACK_SIGNING_SECRET=your-signing-secret-here
```

### 各キーの取得方法

<details>
<summary>📌 Anthropic API キーの取得方法（クリックで展開）</summary>

1. [console.anthropic.com](https://console.anthropic.com/) にアクセス
2. アカウント登録・ログイン
3. 「API Keys」メニューから新しいキーを作成
4. `sk-ant-...` から始まる文字列をコピー

</details>

<details>
<summary>📌 楽天アプリIDの取得方法（クリックで展開）</summary>

1. [webservice.rakuten.co.jp](https://webservice.rakuten.co.jp/) にアクセス
2. 楽天IDでログイン（なければ無料登録）
3. 「アプリ ID 発行」からアプリを作成
4. **「楽天レシピAPI」を APIスコープに追加** すること
5. 本番環境では「許可されたWebサイト」に `moodmeshi.vercel.app` を登録

> ⚠️ `echo` コマンドではなく `printf` でキーを設定してください。`echo` だと末尾に改行が入りエラーになることがあります。

</details>

<details>
<summary>📌 Slack Bot の設定方法（クリックで展開）</summary>

1. [api.slack.com/apps](https://api.slack.com/apps) にアクセスして新規アプリを作成
2. **「OAuth & Permissions」** でスコープを追加:
   - `commands`（スラッシュコマンド）
   - `chat:write`（メッセージ投稿）
3. **「Slash Commands」** で `/meshi` コマンドを作成
   - Request URL: `https://your-domain.com/slack/events`
4. **「Interactivity & Shortcuts」** を有効化
   - Request URL: `https://your-domain.com/slack/events`
5. ワークスペースにアプリをインストール
6. `Bot User OAuth Token`（`xoxb-...`）と `Signing Secret` をコピー

</details>

---

## ☁️ デプロイ方法

このアプリは **Vercel**（Webアプリ専用）と **Render**（Slackボット含む）の2通りのデプロイに対応しています。

### Vercel へのデプロイ（Webアプリのみ）

> Slackボット機能は Vercel のサーバーレス環境では動作しません。
> WebアプリだけをVercelで公開し、Slackボットは Render で動かすのが推奨構成です。

```bash
# Vercel CLI をインストール
npm i -g vercel

# プロジェクトをリンク
vercel link

# 環境変数を登録（printf を使うこと！echo は改行が入るため NG）
printf 'your_anthropic_key'  | vercel env add ANTHROPIC_API_KEY production
printf 'your_rakuten_app_id' | vercel env add RAKUTEN_APP_ID production
printf 'your_rakuten_key'    | vercel env add RAKUTEN_ACCESS_KEY production

# 本番デプロイ
vercel deploy --prod
```

GitHub と連携すれば `master` ブランチへのプッシュで自動デプロイされます:

```bash
vercel git connect
```

---

### Render へのデプロイ（Slackボット含む全機能）

`render.yaml` が用意されているので、以下の手順で簡単にデプロイできます。

```yaml
# render.yaml の内容（抜粋）
services:
  - type: web
    name: moodmeshi
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

1. [render.com](https://render.com) でアカウント作成
2. 「New Web Service」→ GitHubリポジトリを連携
3. 環境変数（`ANTHROPIC_API_KEY` など）をダッシュボードで設定
4. デプロイ完了後、SlackアプリのRequest URLを更新

---

## 🧪 テストの実行

```bash
# 全テストを実行
pytest

# 詳細な出力で実行
pytest -v

# 特定のファイルだけ実行
pytest tests/test_orchestrator.py
pytest tests/test_recipe_hunter.py

# 特定のテスト関数だけ実行
pytest tests/test_orchestrator.py::test_mood_analysis
```

---

## 📊 データの流れ（詳細）

各エージェントがどのようなデータをやり取りしているかを示します。

```
入力
─────────────────────────────────────────────────────────
raw_input: "仕事で疲れた、胃に優しいものが食べたい"

Phase 1 出力 (MoodAnalysis)
─────────────────────────────────────────────────────────
├── mood_keywords:     ["疲れた", "胃に優しい"]
├── food_keywords:     ["消化に良い", "柔らかい食材"]
├── target_categories: ["33", "35"]  ← 汁物・野菜おかず
└── constraints:
    ├── max_cooking_time: null
    ├── max_cost: null
    └── preference_notes: "消化に良い"

Phase 2 出力（並行処理）
─────────────────────────────────────────────────────────
RecipeHunterResult               NutritionAdvice
─────────────────                ───────────────
recipes:                         mood_based_nutrients:
  ├── recipe_title                  ["ビタミンB群", "亜鉛"]
  ├── recipe_url                 recommended_ingredients:
  ├── food_image_url                ["豆腐", "野菜", "魚"]
  ├── recipe_material            avoid_ingredients:
  ├── recipe_indication             ["脂っこい食材"]
  └── recipe_cost                advice_text: "..."

                                 SeasonalRecommendation
                                 ─────────────────────
                                 current_season: "春"
                                 seasonal_ingredients:
                                   ["タケノコ", "春キャベツ"]
                                 seasonal_dishes:
                                   ["竹の子ご飯", "春野菜炒め"]

Phase 3 出力 (FinalProposal)
─────────────────────────────────────────────────────────
greeting: "お疲れさまです！胃に優しい..."
proposals[6]:
  ├── rank: 1
  ├── recipe: { title, url, image, ... }
  ├── why_recommended: "気分にぴったりな理由..."
  ├── nutrition_point: "ビタミンB1が豊富で..."
  ├── seasonal_point: "旬の春キャベツを使った..."
  └── arrange_tip: "大根おろしを添えると..."
closing_message: "今日も美味しい食事をお楽しみください！"
```

---

## ❓ よくある質問

<details>
<summary>Q. Slackボットを使わずにWebアプリだけ使えますか？</summary>

**A. はい、使えます。**

`SLACK_BOT_TOKEN` と `SLACK_SIGNING_SECRET` を設定しなければ、Slackボット機能は無効になり、Webアプリとして動作します。楽天APIと Anthropic API のキーがあれば十分です。

</details>

<details>
<summary>Q. 楽天レシピAPIが使えない場合どうなりますか？</summary>

**A. AIが自動的に代替レシピを生成します。**

楽天APIのエラーや制限に引っかかった場合、Phase 3の Claude Sonnet が**架空の（でも実用的な）レシピ提案を生成**します。そのため、完全にエラーになることはありません。

</details>

<details>
<summary>Q. レスポンスに時間がかかるのはなぜですか？</summary>

**A. 複数のClaudeモデルを呼び出しているためです。**

Phase 1 → Phase 2（3並行）→ Phase 3 と合計5回のAI呼び出しが発生します。Vercelの場合はタイムアウトが60秒に設定されています。進捗状況はリアルタイムで画面に表示されます。

</details>

<details>
<summary>Q. 楽天APIのレート制限エラーが出ます</summary>

**A. 自動リトライ機能があります。**

楽天APIは約1リクエスト/秒の制限があります。アプリ内部では `RAKUTEN_RATE_LIMIT_SLEEP = 1.2秒` の待機と最大2回のリトライを実装しています。それでも失敗した場合は、しばらく待ってから再試行してください。

</details>

<details>
<summary>Q. Vercelで環境変数を設定するとき echo を使ってはいけないのはなぜ？</summary>

**A. `echo` は末尾に改行文字を追加するためです。**

APIキーの末尾に見えない改行文字 `\n` が付くと、API呼び出し時に認証エラーになります。`printf` を使うと改行なしで値を設定できます。

```bash
# ❌ NG（末尾に改行が入る）
echo 'sk-ant-xxx' | vercel env add ANTHROPIC_API_KEY production

# ✅ OK（改行なし）
printf 'sk-ant-xxx' | vercel env add ANTHROPIC_API_KEY production
```

</details>

---

## 📝 ライセンス

このプロジェクトは個人・学習目的で公開されています。

---

<div align="center">

**🍽️ 今日の気分に合った料理を、MoodMeshiで見つけよう**

[🌐 Webアプリを使う](https://moodmeshi.vercel.app) | [📊 紹介スライドを見る](https://korezonzi.github.io/moodMeshi/) | [📂 GitHubを見る](https://github.com/korezonzi/moodMeshi)

</div>
