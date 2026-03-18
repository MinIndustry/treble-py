use std::collections::HashMap;

use serde::Deserialize;

fn default_sample_rate() -> f32 {
    44100.0
}
fn default_block_size() -> usize {
    512
}
fn default_waveform() -> String {
    "sine".to_string()
}
fn default_attack() -> f32 {
    0.01
}
fn default_decay() -> f32 {
    0.1
}
fn default_sustain() -> f32 {
    0.8
}
fn default_release() -> f32 {
    0.2
}

/// Top-level render request from Python.
#[derive(Debug, Deserialize)]
pub struct GraphSpec {
    /// MIDI note number (0–127). 60 = C4 (middle C).
    pub note: u8,
    /// Seconds from t=0 to note-on event.
    pub note_on: f32,
    /// Seconds from t=0 to note-off event.
    pub note_off: f32,
    /// Total render duration in seconds (must be >= note_off).
    pub duration: f32,
    /// Audio sample rate in Hz.
    #[serde(default = "default_sample_rate")]
    pub sample_rate: f32,
    /// Block size for System::run(). Lower = more timing precision, higher = faster.
    #[serde(default = "default_block_size")]
    pub block_size: usize,
    /// The single source (oscillator + ADSR).
    pub source: SourceSpec,
    /// Zero or more filters applied in sequence (linear chain, source → f0 → f1 → … → sink).
    #[serde(default)]
    pub filters: Vec<FilterSpec>,
}

/// Describes the monophonic source (one oscillator voice).
#[derive(Debug, Deserialize)]
pub struct SourceSpec {
    /// Waveform: "sine" | "square" | "sawtooth" | "triangle" | "whitenoise" | "pinknoise" | "blank"
    #[serde(default = "default_waveform")]
    pub waveform: String,
    /// How this tone's frequency relates to the MIDI note frequency.
    #[serde(default)]
    pub frequency_relation: FrequencyRelationSpec,
    /// Amplitude envelope — attack time in seconds.
    #[serde(default = "default_attack")]
    pub attack: f32,
    /// Amplitude envelope — decay time in seconds.
    #[serde(default = "default_decay")]
    pub decay: f32,
    /// Amplitude envelope — sustain level (0.0–1.0).
    #[serde(default = "default_sustain")]
    pub sustain: f32,
    /// Amplitude envelope — release time in seconds.
    #[serde(default = "default_release")]
    pub release: f32,
}

/// Describes one filter in the processing chain.
#[derive(Debug, Deserialize)]
pub struct FilterSpec {
    /// Filter type identifier:
    /// "lowpass" | "highpass" | "bandpass" | "resonant_bandpass" | "moving_average"
    /// | "gain" | "clipper" | "compressor" | "tremolo" | "delay" | "pan"
    #[serde(rename = "type")]
    pub filter_type: String,
    /// Filter-specific parameter overrides. Keys match the filter's `set_parameter` names.
    #[serde(default)]
    pub params: HashMap<String, serde_json::Value>,
}

/// Frequency relation of a tone relative to the base MIDI note frequency.
///
/// Accepted Python forms:
/// - `"identity"` — same as the played note
/// - `"harmonic:N"` — N-th harmonic (frequency * N)
/// - `"ratio:F"` — frequency * F
/// - `"semitones:I"` — frequency * 2^(I/12)
/// - `"offset:F"` — frequency + F Hz
/// - `{"harmonic": N}`, `{"ratio": F}`, `{"semitones": I}`, `{"offset": F}`, `{"constant": F}`
#[derive(Debug, Deserialize, Default)]
#[serde(untagged)]
pub enum FrequencyRelationSpec {
    #[default]
    Identity,
    Tagged(String),
    Object(HashMap<String, serde_json::Value>),
}
