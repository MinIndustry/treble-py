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

fn default_attack() -> (f32, f32, f32, f32) {
    (0.01, 1.0, 0.01, 0.0)
}

fn default_decay() -> (f32, f32, f32, f32) {
    (0.1, 0.8, 0.1, 1.0)
}

fn default_sustain() -> f32 {
    0.8
}

fn default_release() -> (f32, f32, f32, f32) {
    (0.2, 0.0, 0.0, 0.0)
}

#[derive(Debug, Deserialize)]
pub enum ConnectionType {
    SourceFilter { source: usize, filter: usize },
    SourceSink { source: usize, sink: usize },
    FilterFilter { filter_out: usize, filter_in: usize },
    FilterSink { filter: usize, sink: usize },
}

/// Top-level render request from Python.
#[derive(Debug, Deserialize)]
pub struct GraphSpec {
    /// MIDI Note number (0-127)
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
    /// A Single mutli-source, with each sub-source having its own parameters
    pub sources: Vec<MultiSourceSpec>,
    /// Zero or more filters to be added to the graph
    #[serde(default)]
    pub filters: Vec<FilterSpec>,
    /// All the connections in the graph
    pub connections: Vec<ConnectionType>,
}

#[derive(Debug, Deserialize)]
pub struct ADSRSpec {
    /// Attack description: duration, peak, control_time (x), control_peak (y)
    #[serde(default = "default_attack")]
    pub attack: (f32, f32, f32, f32),
    /// Decay description:
    #[serde(default = "default_decay")]
    pub decay: (f32, f32, f32, f32),
    /// Sustain is a single value, duration depends on note_off.
    #[serde(default = "default_sustain")]
    pub sustain: f32,
    #[serde(default = "default_release")]
    pub release: (f32, f32, f32, f32),
}

/// Describes the monophonic source (one oscillator voice).
#[derive(Debug, Deserialize)]
pub struct SourceSpec {
    /// Waveform:
    /// "sine" | "square" | "sawtooth" | "triangle"
    /// "whitenoise" | "pinknoise" | "blank"
    #[serde(default = "default_waveform")]
    pub waveform: String,
    /// How this tone's frequency relates to the MIDI note frequency.
    #[serde(default)]
    pub frequency_relation: FrequencyRelationSpec,
    /// Envelope spec
    pub envelope: ADSRSpec,
}

#[derive(Debug, Deserialize)]
pub struct MultiSourceSpec {
    /// The sources within this multi-source
    pub sources: Vec<SourceSpec>,
    /// The base frequency of the source
    pub base_frequency: f32,
    /// The mix mode of the sources
    pub mix_mode: rustic::core::generator::prelude::MixMode,
    /// The global amplitude envelope (over all sub-sources)
    pub glob_ampl: ADSRSpec,
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
