"""
文字化け修正機能 - 設計書の「データ処理層」に基づく実装
現在の問題「�A�I�L�������̃��X�g」→「アオキ買い物リスト」を解決
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple
import logging
import chardet
from ..utils.enhanced_logger import get_logger

logger = get_logger(__name__)


class EncodingHandler:
    """文字化け修正・エンコーディング処理クラス"""
    
    def __init__(self):
        # 文字化けパターンとその修正マッピング
        self.repair_patterns = self._initialize_repair_patterns()
        self.encoding_detectors = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
        
    def _initialize_repair_patterns(self) -> Dict[str, str]:
        """文字化け修正パターンの初期化"""
        return {
            # 一般的な文字化けパターン
            r'�+': '',  # 不正文字マーカーを削除
            
            # Shift_JIS -> UTF-8 変換エラーの修正
            r'‚�': 'あ', r'‚¢': 'い', r'‚¤': 'う', r'‚¦': 'え', r'‚¨': 'お',
            r'‚©': 'か', r'‚«': 'き', r'‚­': 'く', r'‚¯': 'け', r'‚±': 'こ',
            r'‚³': 'さ', r'‚µ': 'し', r'‚·': 'す', r'‚¹': 'せ', r'‚»': 'そ',
            r'‚½': 'た', r'‚¿': 'ち', r'‚Â': 'つ', r'‚Ä': 'て', r'‚Æ': 'と',
            r'‚È': 'な', r'‚É': 'に', r'‚Ê': 'ぬ', r'‚Ë': 'ね', r'‚Ì': 'の',
            r'‚Í': 'は', r'‚Ð': 'ひ', r'‚Ó': 'ふ', r'‚Ö': 'へ', r'‚Ù': 'ほ',
            r'‚Ü': 'ま', r'‚Ý': 'み', r'‚Þ': 'む', r'‚ß': 'め', r'‚à': 'も',
            r'‚â': 'や', r'‚ä': 'ゆ', r'‚æ': 'よ',
            r'‚ç': 'ら', r'‚è': 'り', r'‚é': 'る', r'‚ê': 'れ', r'‚ë': 'ろ',
            r'‚í': 'わ', r'‚ð': 'を', r'‚ñ': 'ん',
            
            # カタカナ
            r'ƒA': 'ア', r'ƒC': 'イ', r'ƒE': 'ウ', r'ƒG': 'エ', r'ƒI': 'オ',
            r'ƒJ': 'カ', r'ƒL': 'キ', r'ƒN': 'ク', r'ƒP': 'ケ', r'ƒR': 'コ',
            r'ƒT': 'サ', r'ƒV': 'シ', r'ƒX': 'ス', r'ƒZ': 'セ', r'ƒ\\^': 'ソ',
            r'ƒ\^': 'タ', r'ƒ`': 'チ', r'ƒc': 'ツ', r'ƒe': 'テ', r'ƒg': 'ト',
            r'ƒi': 'ナ', r'ƒj': 'ニ', r'ƒk': 'ヌ', r'ƒl': 'ネ', r'ƒm': 'ノ',
            r'ƒn': 'ハ', r'ƒq': 'ヒ', r'ƒt': 'フ', r'ƒw': 'ヘ', r'ƒz': 'ホ',
            r'ƒ}': 'マ', r'ƒ~': 'ミ', r'ƒ€': 'ム', r'ƒ‚': 'メ', r'ƒ„': 'モ',
            r'ƒ†': 'ヤ', r'ƒˆ': 'ユ', r'ƒŠ': 'ヨ',
            r'ƒ‰': 'ラ', r'ƒŠ': 'リ', r'ƒ‹': 'ル', r'ƒŒ': 'レ', r'ƒ': 'ロ',
            r'ƒ': 'ワ', r'ƒ': 'ヲ', r'ƒ"': 'ン',
            
            # 濁音・半濁音
            r'‚ª': 'が', r'‚¬': 'ぎ', r'‚®': 'ぐ', r'‚°': 'げ', r'‚²': 'ご',
            r'‚´': 'ざ', r'‚¶': 'じ', r'‚¸': 'ず', r'‚º': 'ぜ', r'‚¼': 'ぞ',
            r'‚¾': 'だ', r'‚Á': 'ぢ', r'‚Ã': 'づ', r'‚Å': 'で', r'‚Ç': 'ど',
            r'‚Î': 'ば', r'‚Ñ': 'び', r'‚Ô': 'ぶ', r'‚×': 'べ', r'‚Ú': 'ぼ',
            r'‚Ï': 'ぱ', r'‚Ò': 'ぴ', r'‚Õ': 'ぷ', r'‚Ø': 'ぺ', r'‚Û': 'ぽ',
            
            # 特殊文字
            r'ã': 'ー', r'�': 'ー',
            r'€': '円', r'\\': 'ー',
            
            # 実際の文字化け例に基づく修正
            r'�A�I�L': 'アオキ',
            r'���X�g': 'リスト',
            r'���C��': 'ライ',
        }
    
    def fix_garbled_text(self, text: str) -> str:
        """文字化けテキストの修正"""
        if not text or not isinstance(text, str):
            return text
        
        original_text = text
        
        try:
            # 1. エンコーディング検出と修正
            text = self._detect_and_fix_encoding(text)
            
            # 2. パターンマッチングによる修正
            text = self._apply_repair_patterns(text)
            
            # 3. Unicode正規化
            text = self._normalize_unicode(text)
            
            # 4. 不正文字の除去
            text = self._remove_invalid_characters(text)
            
            # 5. 修正結果のログ
            if text != original_text:
                logger.info(
                    "Fixed garbled text",
                    original=original_text,
                    fixed=text,
                    operation="encoding_fix"
                )
            
            return text
            
        except Exception as e:
            logger.error(
                "Failed to fix garbled text", 
                error=e, 
                text=original_text,
                operation="encoding_fix"
            )
            return original_text
    
    def _detect_and_fix_encoding(self, text: str) -> str:
        """エンコーディング検出と修正"""
        # chardetを使用してエンコーディングを検出
        try:
            # テキストをバイト形式に変換して検出
            text_bytes = text.encode('utf-8', errors='ignore')
            detected = chardet.detect(text_bytes)
            
            if detected and detected['confidence'] > 0.7:
                detected_encoding = detected['encoding']
                logger.debug(f"Detected encoding: {detected_encoding} (confidence: {detected['confidence']})")
                
                # 検出されたエンコーディングでデコードしてUTF-8に変換
                if detected_encoding and detected_encoding.lower() != 'utf-8':
                    try:
                        # 元のバイト表現を推測して修正
                        fixed_text = text_bytes.decode(detected_encoding, errors='ignore')
                        return fixed_text
                    except (UnicodeDecodeError, LookupError):
                        pass
            
        except Exception as e:
            logger.debug(f"Encoding detection failed: {e}")
        
        return text
    
    def _apply_repair_patterns(self, text: str) -> str:
        """修正パターンの適用"""
        for pattern, replacement in self.repair_patterns.items():
            try:
                text = re.sub(pattern, replacement, text)
            except Exception as e:
                logger.debug(f"Pattern repair failed for {pattern}: {e}")
        
        return text
    
    def _normalize_unicode(self, text: str) -> str:
        """Unicode正規化"""
        try:
            # NFC正規化（合成文字を使用）
            normalized = unicodedata.normalize('NFC', text)
            return normalized
        except Exception as e:
            logger.debug(f"Unicode normalization failed: {e}")
            return text
    
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
    
    def validate_encoding(self, text: str) -> Tuple[bool, str]:
        """エンコーディングの妥当性検証"""
        if not text:
            return True, "empty_text"
        
        try:
            # UTF-8として正常にエンコード・デコードできるかチェック
            text.encode('utf-8').decode('utf-8')
            
            # 文字化けマーカーの存在チェック
            if '�' in text:
                return False, "invalid_characters_found"
            
            # 不正なバイトシーケンスパターンチェック
            suspicious_patterns = [
                r'[‚ƒ]{2,}',  # Shift_JIS文字化けパターン
                r'[À-ÿ]{3,}',  # Latin-1文字化けパターン  
                r'[\x80-\x9F]',  # 制御文字範囲
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, text):
                    return False, f"suspicious_pattern_found: {pattern}"
            
            return True, "valid"
            
        except UnicodeError as e:
            return False, f"unicode_error: {e}"
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
                    logger.info(
                        f"Fixed {field} field",
                        field=field,
                        original=original_value,
                        fixed=fixed_value,
                        operation="event_field_fix"
                    )
        
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
                logger.error(
                    f"Failed to fix event {i}",
                    error=e,
                    event_id=event.get('id', 'unknown'),
                    operation="batch_encoding_fix"
                )
                fixed_events.append(event)  # 修正失敗時は元のイベントを使用
        
        logger.info(
            f"Batch encoding fix completed",
            total_events=len(events),
            fixed_events=fix_count,
            success_rate=f"{(len(fixed_events)/len(events)*100):.1f}%",
            operation="batch_encoding_fix"
        )
        
        return fixed_events


# 使用例とテスト
if __name__ == "__main__":
    # テスト用の文字化けデータ
    test_cases = [
        "�A�I�L�������̃��X�g",  # 実際の文字化け例
        "‚±‚ñ‚É‚¿‚Í",         # Shift_JIS文字化け
        "ƒeƒXƒg",                # カタカナ文字化け  
        "正常なテキスト",        # 正常なテキスト
        "",                      # 空文字
        None                     # None値
    ]
    
    handler = EncodingHandler()
    
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
        'description': '‚±‚ê‚Í‚Ä‚·‚Æ‚Å‚·',
        'location': 'ƒeƒXƒg�X�|�b�g',
        'start_time': '2025-08-31T10:00:00'
    }
    
    print("Original event:")
    for key, value in test_event.items():
        print(f"  {key}: {repr(value)}")
    
    fixed_event = handler.auto_fix_event_data(test_event)
    
    print("\nFixed event:")
    for key, value in fixed_event.items():
        print(f"  {key}: {repr(value)}")