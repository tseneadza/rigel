mod voice;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_global_shortcut::Builder::new().build())
    .manage(voice::tts::TtsState::default())
    .manage(voice::ListenerState::default())
    .invoke_handler(tauri::generate_handler![
      voice::tts::voice_speak,
      voice::tts::voice_stop_speaking,
      voice::tts::voice_list_tts_voices,
      voice::enroll::voice_enroll_wakeword,
      voice::enroll::voice_wakeword_status,
      voice::enroll::voice_clear_wakeword,
      voice::stt::voice_stt_model_status,
      voice::stt::voice_download_stt_model,
      voice::voice_set_enabled,
      voice::voice_is_enabled,
    ])
    .setup(|app| {
      // Logging is on in release builds too: the voice pipeline can only be
      // diagnosed from what it logs (wake-word scores, recording levels,
      // transcripts), and the installed /Applications copy is a release
      // build. Info-level, file only, at ~/Library/Logs/<bundle-id>/Rigel.log.
      app.handle().plugin(
        tauri_plugin_log::Builder::default()
          .level(log::LevelFilter::Info)
          .targets([
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir { file_name: None }),
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
          ])
          // Default cap is 40 KB, which the voice listener's status lines
          // fill in a few minutes — and the plugin then throws the whole
          // file away, taking enrollment/detection evidence with it.
          .max_file_size(20_000_000)
          .rotation_strategy(tauri_plugin_log::RotationStrategy::KeepSome(3))
          .build(),
      )?;
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
