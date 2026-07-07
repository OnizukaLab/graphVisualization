# graphVisualization

Wikipedia を起点に social graph を構築するためのサブプロジェクトです。

## Structure

- `src/`
  - 俳優データと政治家データのクロール・グラフ構築用スクリプト
- `data/actor/`
  - 俳優グラフ用の出力データ
- `data/politician/`
  - 政治家グラフ用の出力データ

## Entry Points

- `src/build_actor_graph.py`
- `src/build_politician_graph.py`

## Outputs

各データセットで主に次のファイルを出力します。

- `nodes.csv`
- `edges.csv`
- `manifest.json`

## Notes

- `data/**/cache/` はローカルキャッシュであり、Git には含めません。
- `data/**/outputs/` は生成済み成果物として保持します。
