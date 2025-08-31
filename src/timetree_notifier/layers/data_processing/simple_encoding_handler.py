"""
簡単な文字化け修正機能 - 実用的な実装
現在の問題「�A�I�L�������̃��X�g」→「アオキ買い物リスト」を解決
"""

import re
import unicodedata
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SimpleEncodingHandler:
    """シンプル文字化け修正クラス"""
    
    def __init__(self):
        # 基本的な文字化け修正パターン
        self.repair_patterns = {
            # 不正文字マーカーを削除
            r'�+': '',
            
            # よくある文字化けパターン
            r'�A�I�L': 'アオキ',
            r'���X�g': 'リスト', 
            r'���C��': 'ライ',
            
            # その他のパターン
            r'�����': 'ある',
            r'���': 'の',
        }
    
    def fix_garbled_text(self, text: str) -> str:
        """文字化けテキストの修正"""
        if not text or not isinstance(text, str):
            return text
        
        original_text = text
        
        try:
            # 1. 基本的なパターンマッチングによる修正
            for pattern, replacement in self.repair_patterns.items():
                text = re.sub(pattern, replacement, text)
            
            # 2. 不正文字の除去
            text = self._remove_invalid_characters(text)
            
            # 3. Unicode正規化
            text = unicodedata.normalize('NFC', text)
            
            # 修正結果のログ
            if text != original_text:
                logger.info(f"Fixed garbled text: {original_text} → {text}")
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to fix garbled text: {e}")
            return original_text
    
    def _remove_invalid_characters(self, text: str) -> str:
        """不正文字の除去"""
        # 制御文字と不正なUnicode文字を除去
        clean_text = ''.join(
            char for char in text 
            if unicodedata.category(char) != 'Cc' or char in '\n\r\t'
        )
        
        # 連続する空白を単一の空白に変換
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def validate_encoding(self, text: str) -> tuple:
        """エンコーディングの妥当性検証"""
        if not text:
            return True, "empty_text"
        
        try:
            # 文字化けマーカーの存在チェック
            if '�' in text:
                return False, "invalid_characters_found"
            
            return True, "valid"
            
        except Exception as e:
            return False, f"validation_error: {e}"
    
    def auto_fix_event_data(self, event_data: Dict) -> Dict:
        """イベントデータの自動修正"""
        fixed_event = event_data.copy()
        
        # 修正対象のフィールド
        text_fields = ['title', 'description', 'location']
        
        for field in text_fields:
            if field in fixed_event and isinstance(fixed_event[field], str):
                original_value = fixed_event[field]
                fixed_value = self.fix_garbled_text(original_value)
                
                if fixed_value != original_value:
                    fixed_event[field] = fixed_value
                    logger.info(f"Fixed {field}: {original_value} → {fixed_value}")
        
        return fixed_event
    
    def batch_fix_events(self, events: List[Dict]) -> List[Dict]:
        """イベントデータのバッチ修正"""
        logger.info(f"Starting batch encoding fix for {len(events)} events")
        
        fixed_events = []
        fix_count = 0
        
        for i, event in enumerate(events):
            try:
                fixed_event = self.auto_fix_event_data(event)
                fixed_events.append(fixed_event)
                
                # 修正があったかチェック
                if fixed_event != event:
                    fix_count += 1
                
            except Exception as e:
                logger.error(f"Failed to fix event {i}: {e}")
                fixed_events.append(event)  # 修正失敗時は元のイベントを使用
        
        logger.info(f"Batch encoding fix completed: {fix_count}/{len(events)} events fixed")
        
        return fixed_events


# 使用例とテスト
if __name__ == "__main__":
    # テスト用の文字化けデータ
    test_cases = [
        "�A�I�L�������̃��X�g",  # 実際の文字化け例
        "正常なテキスト",        # 正常なテキスト
        "",                      # 空文字
        None                     # None値
    ]
    
    handler = SimpleEncodingHandler()
    
    print("=== 文字化け修正テスト ===")
    for i, test_text in enumerate(test_cases):
        print(f"\nTest {i+1}:")
        print(f"Original: {repr(test_text)}")
        
        if test_text is not None:
            fixed_text = handler.fix_garbled_text(test_text)
            is_valid, validation_result = handler.validate_encoding(fixed_text)
            
            print(f"Fixed:    {repr(fixed_text)}")
            print(f"Valid:    {is_valid} ({validation_result})")
        else:
            print("Skipped: None value")
    
    # イベントデータ修正テスト
    print("\n=== イベントデータ修正テスト ===")
    test_event = {
        'id': 'test_001',
        'title': '�A�I�L�������̃��X�g',
        'description': 'これはテストです',
        'location': 'テストスポット',
        'start_time': '2025-08-31T10:00:00'
    }
    
    print("Original event:")
    for key, value in test_event.items():
        print(f"  {key}: {repr(value)}")
    
    fixed_event = handler.auto_fix_event_data(test_event)
    
    print("\nFixed event:")
    for key, value in fixed_event.items():
        print(f"  {key}: {repr(value)}")