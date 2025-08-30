# データ設計最適化提案

## 🎯 現在の課題
- SQLiteを使った複雑な同期処理
- GitHub Actionsでのデータ永続化の難しさ
- 過度に複雑なイベント正規化

## 💡 最適化案: Simple JSON + Git Storage

### データモデル簡素化
```json
{
  "metadata": {
    "last_updated": "2025-08-31T06:00:00Z",
    "version": "3.1",
    "total_events": 15
  },
  "events": [
    {
      "id": "timetree_123456",
      "title": "アオキ買い物リスト",
      "start": "2025-08-31T06:30:00+09:00",
      "end": null,
      "all_day": false,
      "hash": "abc123def",
      "created_at": "2025-08-31T05:00:00Z"
    }
  ],
  "changes_log": [
    {
      "timestamp": "2025-08-31T06:00:00Z", 
      "type": "added",
      "event_id": "timetree_123456",
      "notified": true
    }
  ]
}
```

### 変更検知ロジック (O(n) 効率化)
```python
def detect_changes(previous_data: dict, new_events: List[Event]) -> EventChanges:
    """シンプルなハッシュベース差分検知"""
    
    # 前回のイベントハッシュマップ作成
    prev_events = {e['id']: e['hash'] for e in previous_data.get('events', [])}
    
    added, updated, deleted = [], [], []
    
    # 新しいイベントの処理
    current_ids = set()
    for event in new_events:
        current_ids.add(event.id)
        event_hash = generate_hash(event)
        
        if event.id not in prev_events:
            added.append(event)  # 新規追加
        elif prev_events[event.id] != event_hash:
            updated.append(event)  # 更新
    
    # 削除されたイベント
    deleted_ids = set(prev_events.keys()) - current_ids
    deleted = [{'id': id} for id in deleted_ids]
    
    return EventChanges(added=added, updated=updated, deleted=deleted)
```

## 🚀 GitHub Pages連携

### 自動デプロイ設定
```yaml
# .github/workflows/timetree-sync.yml
name: TimeTree Daily Sync

on:
  schedule:
    - cron: '0 21 * * *'  # 6:00 JST
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run TimeTree Sync
        run: |
          python src/main.py
          
      - name: Commit updated data
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add data/events.json
          git commit -m "Auto: Daily TimeTree sync $(date)" || exit 0
          git push
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./data
```

### Web Dashboard (Optional)
```html
<!-- GitHub Pages上でイベント表示 -->
<!DOCTYPE html>
<html>
<head>
    <title>TimeTree Events</title>
    <meta charset="utf-8">
</head>
<body>
    <div id="events-container"></div>
    
    <script>
    fetch('events.json')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('events-container');
            data.events.forEach(event => {
                const div = document.createElement('div');
                div.innerHTML = `
                    <h3>${event.title}</h3>
                    <p>${new Date(event.start).toLocaleString('ja-JP')}</p>
                `;
                container.appendChild(div);
            });
        });
    </script>
</body>
</html>
```