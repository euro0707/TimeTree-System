/**
 * TimeTree Notifier v3.0 - Google Apps Script Integration
 * 
 * 機能:
 * - TimeTree同期データの受信
 * - Google Assistant/Google Home音声通知
 * - スケジュール管理の自動化
 */

/**
 * Webhook エンドポイント - GitHub ActionsからのPOSTを受信
 */
function doPost(e) {
  try {
    Logger.log('=== TimeTree GAS Integration Webhook Started ===');
    
    // リクエストデータの解析
    const requestData = JSON.parse(e.postData.contents);
    Logger.log(`Request received: ${JSON.stringify(requestData, null, 2)}`);
    
    // テストリクエストの場合
    if (requestData.test) {
      return ContentService
        .createTextOutput(JSON.stringify({
          status: 'success',
          message: 'GAS webhook test successful',
          timestamp: new Date().toISOString()
        }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    
    // メイン処理実行
    const result = processTimeTreeNotification(requestData);
    
    Logger.log('=== TimeTree GAS Integration Completed ===');
    
    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    Logger.log(`ERROR in doPost: ${error.message}`);
    Logger.log(`Stack: ${error.stack}`);
    
    // エラー通知
    sendErrorNotification(error);
    
    return ContentService
      .createTextOutput(JSON.stringify({
        status: 'error',
        message: error.message,
        timestamp: new Date().toISOString()
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * TimeTree通知データの処理メイン関数
 */
function processTimeTreeNotification(requestData) {
  const events = requestData.events || [];
  const targetDate = new Date(requestData.target_date || new Date());
  const voiceEnabled = requestData.voice_enabled !== false;
  
  Logger.log(`Processing ${events.length} events for ${targetDate.toDateString()}`);
  
  const result = {
    status: 'success',
    processed_events: events.length,
    notifications_sent: 0,
    timestamp: new Date().toISOString()
  };
  
  // 音声通知が有効な場合
  if (voiceEnabled && events.length > 0) {
    const voiceResult = sendVoiceNotification(events, targetDate);
    result.voice_notification = voiceResult;
    if (voiceResult.success) {
      result.notifications_sent++;
    }
  }
  
  // Googleカレンダーとの追加同期（オプション）
  if (requestData.sync_calendar) {
    const syncResult = syncWithGoogleCalendar(events, targetDate);
    result.calendar_sync = syncResult;
  }
  
  // 成功通知をSlackに送信（オプション）
  if (requestData.notify_success) {
    sendSuccessNotification(result);
  }
  
  return result;
}

/**
 * Google Assistant/Google Home 音声通知
 */
function sendVoiceNotification(events, targetDate) {
  try {
    Logger.log('Sending voice notification...');
    
    // 日付フォーマット
    const dateFormatter = Utilities.formatDate(targetDate, 'Asia/Tokyo', 'M月d日');
    const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
    const weekday = weekdays[targetDate.getDay()];
    
    // 音声メッセージ作成
    let voiceMessage = '';
    let ssmlMessage = '<speak>';
    
    if (events.length === 0) {
      voiceMessage = `${dateFormatter}${weekday}曜日の予定はありません。ゆっくりお過ごしください。`;
      ssmlMessage += `<prosody rate="medium">${voiceMessage}</prosody>`;
    } else {
      voiceMessage = `${dateFormatter}${weekday}曜日の予定は${events.length}件です。`;
      ssmlMessage += `<prosody rate="medium">${voiceMessage}</prosody><break time="1s"/>`;
      
      // 予定の詳細（最大5件まで）
      const maxEvents = Math.min(events.length, 5);
      for (let i = 0; i < maxEvents; i++) {
        const event = events[i];
        const timeStr = formatEventTimeForVoice(event);
        const eventText = `${timeStr}、${event.title}`;
        
        voiceMessage += `\n${eventText}`;
        ssmlMessage += `<prosody rate="slow">${eventText}</prosody><break time="0.5s"/>`;
      }
      
      if (events.length > maxEvents) {
        const remaining = events.length - maxEvents;
        const remainingText = `他${remaining}件の予定があります。`;
        voiceMessage += `\n${remainingText}`;
        ssmlMessage += `<prosody rate="medium">${remainingText}</prosody>`;
      }
    }
    
    ssmlMessage += '</speak>';
    
    // Google Assistant API を使用した音声通知
    // 注意: 実際の実装では適切なGoogle Assistant APIまたはNotification APIを使用
    const voiceConfig = getVoiceNotificationConfig();
    
    if (voiceConfig.enabled) {
      // Google Home デバイスへの通知送信
      const notificationResult = sendToGoogleHome(voiceMessage, ssmlMessage);
      
      Logger.log(`Voice notification sent: ${voiceMessage}`);
      
      return {
        success: true,
        message: voiceMessage,
        ssml: ssmlMessage,
        device_response: notificationResult
      };
    } else {
      Logger.log('Voice notification disabled in configuration');
      return {
        success: false,
        reason: 'Voice notification disabled'
      };
    }
    
  } catch (error) {
    Logger.log(`Error in voice notification: ${error.message}`);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * イベント時刻を音声用にフォーマット
 */
function formatEventTimeForVoice(event) {
  if (event.is_all_day) {
    return '終日';
  }
  
  if (event.start_time) {
    const startTime = new Date(event.start_time);
    const timeStr = Utilities.formatDate(startTime, 'Asia/Tokyo', 'H時mm分');
    
    if (event.end_time) {
      const endTime = new Date(event.end_time);
      const endTimeStr = Utilities.formatDate(endTime, 'Asia/Tokyo', 'H時mm分');
      return `${timeStr}から${endTimeStr}まで`;
    } else {
      return `${timeStr}から`;
    }
  }
  
  return '';
}

/**
 * Google Home デバイスへの通知送信
 * 
 * 注意: この機能を使用するには、Google Assistant SDK または
 * Google Cloud Text-to-Speech API の設定が必要です
 */
function sendToGoogleHome(message, ssml) {
  try {
    const config = getVoiceNotificationConfig();
    
    // Google Assistant API またはカスタム通知システムを使用
    // 以下は疑似コード - 実際の実装は使用するAPIに依存します
    
    if (config.use_text_to_speech) {
      // Google Cloud Text-to-Speech API を使用
      return callTextToSpeechAPI(ssml);
    } else if (config.use_assistant_api) {
      // Google Assistant API を使用
      return callAssistantAPI(message);
    } else {
      // カスタム通知システム（例: Androidアプリ経由）
      return callCustomNotificationAPI(message);
    }
    
  } catch (error) {
    Logger.log(`Error sending to Google Home: ${error.message}`);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Googleカレンダーとの追加同期
 */
function syncWithGoogleCalendar(events, targetDate) {
  try {
    Logger.log('Syncing with Google Calendar...');
    
    const calendar = CalendarApp.getDefaultCalendar();
    
    // 既存のTimeTree同期イベントをクリア
    clearTimeTreeEvents(calendar, targetDate);
    
    let syncedCount = 0;
    
    // 新しいイベントを追加
    events.forEach(event => {
      try {
        const calendarEvent = createCalendarEvent(calendar, event);
        if (calendarEvent) {
          syncedCount++;
        }
      } catch (error) {
        Logger.log(`Failed to create calendar event: ${error.message}`);
      }
    });
    
    Logger.log(`Synced ${syncedCount} events to Google Calendar`);
    
    return {
      success: true,
      synced_events: syncedCount,
      total_events: events.length
    };
    
  } catch (error) {
    Logger.log(`Error in calendar sync: ${error.message}`);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * TimeTree由来のイベントをクリア
 */
function clearTimeTreeEvents(calendar, date) {
  const startTime = new Date(date);
  startTime.setHours(0, 0, 0, 0);
  
  const endTime = new Date(date);
  endTime.setHours(23, 59, 59, 999);
  
  const events = calendar.getEvents(startTime, endTime);
  
  events.forEach(event => {
    if (event.getTitle().includes('📱') || event.getDescription().includes('TimeTree')) {
      event.deleteEvent();
      Logger.log(`Deleted TimeTree event: ${event.getTitle()}`);
    }
  });
}

/**
 * カレンダーイベント作成
 */
function createCalendarEvent(calendar, event) {
  const title = `📱 ${event.title}`;
  const description = `TimeTree同期イベント\n\n${event.description || ''}`;
  
  if (event.is_all_day) {
    return calendar.createAllDayEvent(title, new Date(event.start_time), {
      description: description,
      location: event.location || ''
    });
  } else {
    const startTime = new Date(event.start_time);
    const endTime = event.end_time ? new Date(event.end_time) : new Date(startTime.getTime() + 60 * 60 * 1000);
    
    return calendar.createEvent(title, startTime, endTime, {
      description: description,
      location: event.location || ''
    });
  }
}

/**
 * 設定値取得
 */
function getVoiceNotificationConfig() {
  const properties = PropertiesService.getScriptProperties();
  
  return {
    enabled: properties.getProperty('VOICE_NOTIFICATION_ENABLED') === 'true',
    use_text_to_speech: properties.getProperty('USE_TEXT_TO_SPEECH') === 'true',
    use_assistant_api: properties.getProperty('USE_ASSISTANT_API') === 'true',
    voice_speed: properties.getProperty('VOICE_SPEED') || 'medium',
    voice_pitch: properties.getProperty('VOICE_PITCH') || 'medium',
    max_events_voice: parseInt(properties.getProperty('MAX_EVENTS_VOICE') || '5')
  };
}

/**
 * エラー通知送信
 */
function sendErrorNotification(error) {
  try {
    const subject = '⚠️ TimeTree GAS Integration Error';
    const body = `TimeTree GAS統合でエラーが発生しました。\n\n` +
                `時刻: ${new Date().toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'})}\n` +
                `エラー: ${error.message}\n\n` +
                `詳細: ${error.stack}`;
    
    GmailApp.sendEmail(Session.getActiveUser().getEmail(), subject, body);
    Logger.log('Error notification sent via Gmail');
    
  } catch (gmailError) {
    Logger.log(`Failed to send error notification: ${gmailError.message}`);
  }
}

/**
 * 成功通知送信
 */
function sendSuccessNotification(result) {
  try {
    Logger.log(`Success notification: ${JSON.stringify(result)}`);
    
    // 必要に応じてSlackやDiscordに成功通知を送信
    const webhookUrl = PropertiesService.getScriptProperties().getProperty('SUCCESS_NOTIFICATION_WEBHOOK');
    
    if (webhookUrl) {
      const payload = {
        text: `✅ TimeTree GAS Integration Success\n` +
              `Events processed: ${result.processed_events}\n` +
              `Notifications sent: ${result.notifications_sent}\n` +
              `Time: ${result.timestamp}`
      };
      
      UrlFetchApp.fetch(webhookUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        payload: JSON.stringify(payload)
      });
    }
    
  } catch (error) {
    Logger.log(`Error sending success notification: ${error.message}`);
  }
}

/**
 * セットアップ用関数 - 初回実行時に手動で呼び出し
 */
function setupGASIntegration() {
  const properties = PropertiesService.getScriptProperties();
  
  properties.setProperties({
    'VOICE_NOTIFICATION_ENABLED': 'true',
    'USE_TEXT_TO_SPEECH': 'false',  // Google Cloud Text-to-Speech使用時はtrue
    'USE_ASSISTANT_API': 'false',   // Google Assistant API使用時はtrue
    'VOICE_SPEED': 'medium',
    'VOICE_PITCH': 'medium',
    'MAX_EVENTS_VOICE': '5',
    'SUCCESS_NOTIFICATION_WEBHOOK': '' // SlackやDiscordのWebhook URL
  });
  
  Logger.log('GAS Integration setup completed');
}